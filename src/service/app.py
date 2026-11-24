"""Loopback-only scheduler application and stable error envelopes."""

from importlib.metadata import version
import logging
import platform
import re
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .conversation import turn
from .errors import ErrorEnvelope, ServiceError
from .hashing import digest
from .plan_evidence import changes, plan_view, validate_current
from .schemas import (
    DiffRequest,
    Evidence,
    HashRequest,
    InitialRequest,
    InstanceRequest,
    PreviewRequest,
    ReplanRequest,
    RollbackRequest,
    TurnRequest,
    ValidateRequest,
)
from .schemas_events import apply_fact, apply_facts, execution_context
from .scheduling import check_instance, initial, replan, rollback

MAX_BODY = 8 * 1024 * 1024
PREFIX = "/internal/v1"
LOG = logging.getLogger("uvicorn.error")
app = FastAPI(
    title="Replan Scheduler Service",
    version="1.0.0",
    responses={
        400: {"model": ErrorEnvelope, "description": "Invalid input"},
        404: {"model": ErrorEnvelope, "description": "Unknown endpoint"},
        413: {"model": ErrorEnvelope, "description": "Request exceeds body limit"},
        422: {"model": ErrorEnvelope, "description": "Independent validation or evidence failure"},
        500: {"model": ErrorEnvelope, "description": "Unexpected scheduler failure"},
        502: {"model": ErrorEnvelope, "description": "LLM transport or envelope failure"},
    },
)


class RequestBoundary:
    """Bound complete request bodies before decoding and propagate trace identifiers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"x-trace-id", b"").decode("latin-1")
        trace_id = supplied if re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", supplied) else uuid4().hex
        scope.setdefault("state", {})["trace_id"] = trace_id

        async def add_trace(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-trace-id", trace_id.encode("ascii")),
                ]
                LOG.info(
                    "trace_id=%s method=%s path=%s status=%s",
                    trace_id,
                    scope["method"],
                    scope["path"],
                    message["status"],
                )
            await send(message)

        data = bytearray()
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                data.extend(message.get("body", b""))
                if len(data) > MAX_BODY:
                    error = ServiceError("PAYLOAD_TOO_LARGE", "Body exceeds 8 MiB", 413)
                    await JSONResponse(error.envelope(trace_id), status_code=413)(
                        scope, receive, add_trace
                    )
                    return
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(data), "more_body": False}
                return await receive()

            await self.app(scope, replay, add_trace)
        else:
            await self.app(scope, receive, add_trace)


app.add_middleware(RequestBoundary)


@app.exception_handler(ServiceError)
async def service_error(request: Request, error: ServiceError) -> JSONResponse:
    return JSONResponse(error.envelope(request.state.trace_id), status_code=error.status)


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException) -> JSONResponse:
    code = "NOT_FOUND" if error.status_code == 404 else "VALIDATION_ERROR"
    body = ServiceError(code, str(error.detail), error.status_code)
    return JSONResponse(
        body.envelope(request.state.trace_id), error.status_code, headers=error.headers
    )


@app.exception_handler(RequestValidationError)
async def request_error(request: Request, error: RequestValidationError) -> JSONResponse:
    rows = [{"loc": list(item["loc"]), "type": item["type"]} for item in error.errors()]
    code = "VALIDATION_ERROR"
    if request.url.path == PREFIX + "/instances/check" and any(
        row["loc"][:2] == ["body", "instance"] for row in rows
    ):
        code = "INVALID_INSTANCE"
    return await service_error(request, ServiceError(code, "Invalid request fields", fields=rows))


@app.exception_handler(Exception)
async def internal_error(request: Request, error: Exception) -> JSONResponse:
    trace = request.state.trace_id
    LOG.error("trace_id=%s error_type=%s", trace, type(error).__name__)
    body = ServiceError("INTERNAL_ERROR", "Internal scheduler error", 500)
    return JSONResponse(body.envelope(trace), 500, headers={"X-Trace-Id": trace})


@app.get(PREFIX + "/health")
def health() -> dict[str, Any]:
    return {
        "status": "UP",
        "versions": {"python": platform.python_version(), "ortools": version("ortools")},
    }


@app.post(PREFIX + "/hash")
def payload_hash(req: HashRequest) -> dict[str, str]:
    try:
        return {"sha256": digest(req.payload)}
    except (TypeError, ValueError) as exc:
        raise ServiceError("VALIDATION_ERROR", "Payload has no canonical JSON encoding") from exc


@app.post(PREFIX + "/instances/check")
def instance_check(req: InstanceRequest) -> dict[str, Any]:
    return check_instance(req.instance)


@app.post(PREFIX + "/initial")
def initial_plan(req: InitialRequest) -> dict[str, Any]:
    return initial(req)


@app.post(PREFIX + "/events/preview")
def preview(req: PreviewRequest) -> dict[str, Any]:
    context = req.context or execution_context(req.instance, req.base_plan)
    instance, _, context = apply_facts(req.instance, req.base_plan, req.pending_events, context)
    try:
        post, normalized, _ = apply_fact(instance, req.base_plan, req.event, context)
    except ValueError as exc:
        raise ServiceError("INVALID_EVENT", "Event fields conflict with the current facts") from exc
    if normalized is None:
        translation = "变更任务截止期"
        event = req.event.model_dump(mode="json")
    else:
        event = normalized.model_dump(mode="json")
        translation = (
            f"设备 {normalized.device_id} 停用 {post.axis.to_dt(normalized.start).isoformat()} "
            f"至 {post.axis.to_dt(normalized.end).isoformat()}"
            if normalized.type == "DEVICE_OUTAGE"
            else f"插入 {len(normalized.tasks)} 个紧急任务"
        )
    return {"ok": True, "back_translation": translation, "event_normalized": event, "warnings": []}


@app.post(PREFIX + "/replan")
def replan_plans(req: ReplanRequest) -> dict[str, Any]:
    return replan(req)


@app.post(PREFIX + "/validate")
def validate_plan(req: ValidateRequest) -> dict[str, Any]:
    return validate_current(req)


@app.post(PREFIX + "/rollback")
def rollback_plan(req: RollbackRequest) -> dict[str, Any]:
    return rollback(req)


@app.post(PREFIX + "/view")
def view_plan(req: Evidence) -> dict[str, Any]:
    return plan_view(req)


@app.post(PREFIX + "/diff")
def diff_plan(req: DiffRequest) -> dict[str, Any]:
    try:
        return {"changes": changes(req.instance, req.base_plan, req.plan)}
    except ValueError as exc:
        raise ServiceError(
            "VALIDATION_ERROR", "Plan difference is outside the instance horizon"
        ) from exc


@app.post(PREFIX + "/agent/turn")
def agent_turn(req: TurnRequest) -> dict[str, Any]:
    return turn(req)
