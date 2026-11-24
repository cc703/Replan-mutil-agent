# P7 HTTP contract

The browser uses /api/v1 exclusively. Spring invokes the scheduler at /internal/v1.
UTF-8 JSON, 8 MiB bodies, unknown fields rejected. Every response carries X-Trace-Id.
Every browser POST sends Idempotency-Key (1–128 characters). Replay is scoped by lab,
method, path and body and returns Idempotent-Replay: true. A conflicting use of the same
lab/key returns 409 IDEMPOTENCY_KEY_REUSED. Error envelope is
`{"error":{"code":"CODE","message":"message","details":{},"trace_id":"id"}}`.

L2 plan previews are revalidated before replays. If the base version or current facts
invalidate the preview, the service returns the current 409/422 error without returning
cached assignments, differences or passed-validation metadata. Successful write replays
still return the original result and do not consume a confirmation again.

## Browser endpoints

Paths below except /health are relative to /labs/{lab_id} after lab creation.
Lab collection GET returns an array, POST {name,instance} returns 201 with
lab_id, name, instance_sha256, summary and active_version_no. Individual GET adds
running_job_id, undecided_job_id, pending_event_count. GET /instance returns the active
instance or imported instance before v1. GET /health is at /api/v1/health.

- POST /plans/initial {params?} returns 202 {job_id,status}. Initial is queued at version 0.
- GET /plans returns version metadata array. GET /plans/{n} returns metadata, plan,
  plan_sha256 and view. An active version unsafe in current facts returns metadata with
  status NEEDS_REPLAN and no plan/view. Historical versions validate against archived
  evidence. GET /plans/{n}/instance returns archived instance; GET /plans/{n}/diff?base={m}
  returns {changes}; it returns 422 VALIDATION_FAILED without changes if either compared
  plan is active and invalid in current facts. Version metadata includes version_no,
  parent_version_no, status and created_at.
- POST /confirmations {action,level,payload,actor,ttl_s?} returns 201
  {confirmation_id,action,level,payload_hash,preview,expires_at,status}.
  POST /confirmations/{id}/confirm {actor,payload_hash} and /reject {actor,payload_hash}
  return {status}. Level/action pairs are L1/EVENT_INJECT, L1/CONSTRAINT_CHANGE,
  L2/PLAN_COMMIT and L2/PLAN_ROLLBACK. Confirm then consume once in the action transaction.
  Payload is respectively the event, {ir_item_id}, {job_id,candidate_id,base_version_no,plan_sha256}
  or {target_version_no,base_version_no}. Bind confirmation to lab, current version and payload.
- POST /events {client_event_id,event,confirmation_id,actor} returns 202 {event_id,status}.
  GET /events?status= returns an array. Duplicate client_event_id with identical event
  returns the existing event; divergent reuse is 409 DUPLICATE_EVENT_CONFLICT.
- POST /constraints {ir_item_id,confirmation_id,actor} returns 202 {event_id,status}.
  Only a P6 DEADLINE proposal is a constraint. P6 outage and urgent proposals use /events
  with the server-issued event payload. TASK_OVERRUN is unsupported.
- GET /jobs and GET /jobs/{id} return job array and job respectively. Job carries
  job_id, kind, status, result_status, base_version_no, event_ids, created_at, started_at,
  finished_at, error, candidates, conflict, relaxations and solver. Eligible candidates
  have candidate_id,label,level,weights,f1,f2,f3,validation,diff,view,explanation,plan_sha256.
  Hide evidence and invalid, stale or currently unusable candidates from this response.
- POST /jobs/{id}/discard {reason,actor} releases batched facts; POST /jobs/retry {actor}
  explicitly queues released work. Current succeeded results (including INFEASIBLE and
  TIMEOUT) block claim until discarded, committed or invalidated by a version change.
- POST /plans/commit {job_id,candidate_id,base_version_no,confirmation_id,actor} and
  POST /plans/rollback {target_version_no,base_version_no,confirmation_id,actor}
  return 201 with version metadata.
- POST /agent/turn {session_id?,text,actor} returns {session_id,assistant_message,
  clarifications,pending_items}. Items contain item_id,ir,back_translation,ambiguities,
  optional event (for EVENT_INJECT), and action. The browser confirms through the same
  endpoints above. Model text cannot confirm an operation.
- GET /decisions returns an array of audit entries.

Errors use 400 for VALIDATION_ERROR, TIME_NOT_ALIGNED, UNKNOWN_ENTITY, UNSUPPORTED_EVENT,
UNSUPPORTED_CONSTRAINT_TYPE, INVALID_EVENT and INVALID_INSTANCE; 404 NOT_FOUND; 409 for
STALE_BASE_VERSION, IDEMPOTENCY_KEY_REUSED, DUPLICATE_EVENT_CONFLICT, JOB_NOT_COMMITTABLE,
CANDIDATE_NOT_FOUND, CONFIRMATION_NOT_CONFIRMED, CONFIRMATION_CONSUMED, CONFIRMATION_EXPIRED,
CONFIRMATION_MISMATCH, CONFIRMATION_LEVEL_INSUFFICIENT and LAB_BUSY; 413 PAYLOAD_TOO_LARGE;
422 VALIDATION_FAILED, ROLLBACK_INFEASIBLE and PLAN_INTEGRITY_ERROR; 428 CONFIRMATION_REQUIRED;
502 SCHEDULER_UNAVAILABLE, LLM_UNAVAILABLE and LLM_OUTPUT_INVALID; 504 SCHEDULER_TIMEOUT;
500 INTERNAL_ERROR.

## Internal endpoints

Paths are relative to /internal/v1. Use this contract during integration and the generated
OpenAPI for complete input schemas. JSON model values use core Pydantic schema.
Each candidate carries internal `evidence` with keys
`instance,plan,base_plan,free,context,revision`. Persist the exact evidence as issued.
The instance hash uses canonical instance bytes (ordered keys and set values); plan and
payload hashes use compact sorted UTF-8 JSON. Never substitute Java JSON ordering for these.

- GET /health returns {status,versions}.
- POST /hash {payload} returns {sha256}. Use payload hash from here in confirmations.
- POST /instances/check {instance} returns {ok,instance_sha256,summary}.
- POST /initial {instance,params?,revision?} returns {result_status,instance_post,
  instance_post_sha256,candidates,solver,plan?,plan_sha256?,view?,validation?}.
  Initial candidates use identical shape to replan, with null parent, free and context.
- POST /events/preview {instance,base_plan,event,context?,pending_events?} returns
  {ok,back_translation,event_normalized,warnings}. Pass active archived instance and
  all currently unincorporated confirmed facts first, in sequence, as pending_events.
  An event is DEVICE_OUTAGE with device_id/start/end; URGENT_INSERT with tasks and
  optional precedences; TASK_OVERRUN is rejected; a Spring-authored CONSTRAINT_CHANGE
  fact is {type:"CONSTRAINT_CHANGE",ir:<P6 Deadline>}. Dates use ISO 8601 with offset;
  durations and lags use integer minutes and are exactly aligned. UTC is used in core
  and storage. View returns Asia/Shanghai ISO strings for browser display.
- POST /replan {instance,base_plan,events,context?,params?,max_candidates?,explain?,
  budget_s?,revision?} returns {result_status,instance_post,instance_post_sha256,candidates,
  impact,conflict,relaxations,solver,warnings}. Compile events in given order. An
  INVALID_EVENT response may include zero-based details.index. Each candidate includes
  its own independent validation evidence.
- POST /validate accepts an expanded evidence object and optional expected_plan_sha256,
  additional_events (confirmed facts outside the original batch), and current_base_plan
  (required if evidence has no base and additional_events is nonempty).
  Returns {passed,violations,plan_sha256_ok}. Always recheck archived evidence first.
  When additional_events is supplied, apply these to the evidence's post-world and
  validate in the augmented world using its original base/free/context. For an initial
  plan, the trusted plan itself supplies the parent context for the current-world check.
  Failure to reconstruct evidence is a refusal. The augmented world is a validation
  input, not a change to what the saved batch covers.
- POST /rollback {instance,base_plan,target_plan,events?,context?,revision?} returns
  {evidence,instance_post_sha256,plan_sha256,view,changes,validation} after applying
  pending events and validating target assignments against current-world freeze rules.
  Failure returns 422 ROLLBACK_INFEASIBLE.
- POST /diff {instance,base_plan,plan} returns {changes}.
- POST /view {instance,plan,base_plan?,free?,context?,revision?} returns
  {devices,assignments,blocked} and validates first. Assignment and window rows carry
  start/end UTC-axis slots and start_iso/end_iso display timestamps.
- POST /agent/turn {session_id?,text,actor,instance,base_plan,lab_id,revision?,events?}.
  Returns the browser DTO. The Python model process supplies proposals only. Spring
  persists draft item identity and body and owns all action preview and confirmation
  state. For edited event fields submit the edited event via the ordinary L1 event flow.

Queue locks the lab row and claims eligible jobs with SKIP LOCKED. Claim snapshots the
base version, archived instance and ordered participating event IDs. The DB distinct
world revision changes whenever an L1 fact is confirmed. Commit verifies archived
evidence and any additional currently confirmed facts, then locks lab and verifies
base version, latest world revision and confirmation in the same transaction. Mark only
the participating events applied. Rollback applies pending facts and never restores
the old physical instance. Epoch/version races cannot consume approval on failure.

Infeasibility and uncertainty are distinct. TIMEOUT never carries an infeasibility
core. Hypothetical alternatives are only for NEGOTIABLE deadlines, in units of
任务权重×截止期延后槽数. There is no adoption action. f3 is the sum of urgent end slots.
