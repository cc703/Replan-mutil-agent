"""Build and run the three local P7 services, with optional managed PostgreSQL."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import BinaryIO
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
FRONTEND = ROOT / "apps" / "frontend"
STATE = ROOT / "artifacts" / "tmp" / "p7-stack"
OWNER = STATE / "owner"
STOP = STATE / "stop"


@dataclass(frozen=True)
class Ports:
    """Addresses chosen for the loopback-only P7 stack."""

    scheduler: int
    spring: int
    frontend: int
    database: int

    @classmethod
    def from_env(cls) -> Ports:
        variables = (
            ("P7_SCHEDULER_PORT", "8000"),
            ("SERVER_PORT", "8080"),
            ("P7_FRONTEND_PORT", "5173"),
            ("P7_DB_PORT", "5432"),
        )
        scheduler, spring, frontend, database = (
            int(os.environ.get(name, default)) for name, default in variables
        )
        for port in (scheduler, spring, frontend, database):
            if not 1 <= port <= 65535:
                raise ValueError("Ports must be between 1 and 65535")
        if len({scheduler, spring, frontend}) != 3:
            raise ValueError("The scheduler, Spring and Vite ports must differ")
        return cls(scheduler, spring, frontend, database)

    def endpoints(self) -> dict[str, str]:
        return {
            "scheduler": f"http://127.0.0.1:{self.scheduler}/internal/v1/health",
            "spring": f"http://127.0.0.1:{self.spring}/api/v1/health",
            "frontend": f"http://127.0.0.1:{self.frontend}/",
            "frontend_proxy": f"http://127.0.0.1:{self.frontend}/api/v1/health",
        }


def _reachable(address: str) -> bool:
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(address, timeout=1) as response:
            return bool(200 <= response.status < 300)
    except (URLError, OSError):
        return False


def _report(ports: Ports) -> bool:
    statuses = {name: _reachable(url) for name, url in ports.endpoints().items()}
    for name, ready in statuses.items():
        print(f"{name}: {'ready' if ready else 'unavailable'}")
    return all(statuses.values())


def _require_env(ports: Ports, external_db: bool) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("P7_LLM", "fake")
    env["P7_SCHEDULER_PORT"] = str(ports.scheduler)
    env["SERVER_PORT"] = str(ports.spring)
    env["P7_DB_PORT"] = str(ports.database)
    env["P7_SCHEDULER_URL"] = f"http://127.0.0.1:{ports.scheduler}"
    env["P7_SPRING_URL"] = f"http://127.0.0.1:{ports.spring}"
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONUTF8"] = "1"
    if not external_db:
        env.setdefault("P7_DB_USER", "p7_local")
        env.setdefault("P7_DB_URL", f"jdbc:postgresql://127.0.0.1:{ports.database}/p7_demo")
    missing = [name for name in ("P7_DB_URL", "P7_DB_USER", "P7_DB_PASSWORD") if not env.get(name)]
    if missing:
        raise ValueError("Set " + ", ".join(missing))
    db_url = env["P7_DB_URL"]
    database = urlsplit(db_url.removeprefix("jdbc:"))
    if (
        not db_url.startswith("jdbc:")
        or database.scheme != "postgresql"
        or database.hostname not in {"localhost", "127.0.0.1"}
        or database.username is not None
    ):
        raise ValueError("P7_DB_URL must name a local PostgreSQL JDBC database")
    return env


def _executable(name: str, override: str | None = None) -> str:
    target = os.environ.get(override) if override else None
    resolved = shutil.which(target or name)
    if resolved is None:
        raise ValueError(f"Executable not found: {target or name}")
    return resolved


def _build(env: dict[str, str]) -> None:
    wrapper = BACKEND / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    maven = _executable("mvn", "P7_MAVEN") if env.get("P7_MAVEN") else str(wrapper)
    npm = _executable("npm.cmd" if os.name == "nt" else "npm")
    subprocess.run(
        [maven, "-q", "-Dmaven.test.skip=true", "package"], cwd=BACKEND, env=env, check=True
    )
    subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONTEND, env=env, check=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, env=env, check=True)


def _start(
    command: list[str], cwd: Path, env: dict[str, str], log: BinaryIO
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def _wait_services(ports: Ports, seconds: float, children: list[subprocess.Popen[bytes]]) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if STOP.exists() or any(child.poll() is not None for child in children):
            return False
        if all(_reachable(url) for url in ports.endpoints().values()):
            return True
        time.sleep(0.25)
    return False


def _cleanup(children: list[subprocess.Popen[bytes]]) -> None:
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def _serve(ports: Ports, env: dict[str, str], startup_timeout: float) -> int:
    for port in (ports.scheduler, ports.spring, ports.frontend):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise ValueError(
                    f"Local port {port} is unavailable; choose a different port"
                ) from exc
    java = _executable("java")
    node = _executable("node")
    jar = BACKEND / "target" / "p7-backend.jar"
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if not jar.is_file() or not vite.is_file() or not (FRONTEND / "dist" / "index.html").is_file():
        raise ValueError("The Spring JAR and Vue build are required; run up without --no-build")
    # Windows keeps the launched JAR open. Run from a local runtime copy so verification can rebuild.
    runtime_jar = STATE / "p7-backend-runtime.jar"
    shutil.copyfile(jar, runtime_jar)
    commands = (
        ("scheduler", [sys.executable, "-m", "service"], ROOT),
        ("spring", [java, "-jar", str(runtime_jar)], BACKEND),
        (
            "frontend",
            [
                node,
                str(vite),
                "preview",
                "--host",
                "127.0.0.1",
                "--port",
                str(ports.frontend),
                "--strictPort",
            ],
            FRONTEND,
        ),
    )
    children: list[subprocess.Popen[bytes]] = []
    try:
        for name, command, cwd in commands:
            with (STATE / f"{name}.log").open("wb") as log:
                children.append(_start(command, cwd, env, log))
        if not _wait_services(ports, startup_timeout, children):
            if STOP.exists():
                return 0
            raise RuntimeError(f"Stack not ready; inspect logs in {STATE}")
        print(f"P7 ready: http://127.0.0.1:{ports.frontend}", flush=True)
        while not STOP.exists():
            if any(child.poll() is not None for child in children):
                raise RuntimeError(f"A P7 service exited; inspect logs in {STATE}")
            time.sleep(0.3)
        return 0
    finally:
        _cleanup(children)


def _up(ports: Ports, args: argparse.Namespace) -> int:
    env = _require_env(ports, args.external_db)
    STATE.mkdir(parents=True, exist_ok=True)
    compose: list[str] | None = None
    started_db = False
    try:
        with OWNER.open("x", encoding="ascii") as owner:
            owner.write(str(os.getpid()))
    except FileExistsError as exc:
        raise ValueError("A P7 stack owns this workspace; run down first") from exc
    try:
        STOP.unlink(missing_ok=True)
        if not args.external_db:
            compose = [_executable("docker"), "compose", "-f", str(ROOT / "docker-compose.yml")]
            subprocess.run(
                [*compose, "up", "-d", "--wait", "postgres"], cwd=ROOT, env=env, check=True
            )
            started_db = True
        if not args.no_build:
            _build(env)
        if STOP.exists():
            return 0
        return _serve(ports, env, args.timeout)
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            if compose is not None and started_db:
                subprocess.run([*compose, "stop", "postgres"], cwd=ROOT, env=env, check=True)
        finally:
            STOP.unlink(missing_ok=True)
            OWNER.unlink(missing_ok=True)


def main() -> int:
    """Manage the local P7 stack from separate up and client terminals."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "down", "health", "wait"))
    parser.add_argument("--external-db", action="store_true", help="Use an existing real database")
    parser.add_argument("--no-build", action="store_true", help="Reuse local verified builds")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    try:
        ports = Ports.from_env()
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        if args.action == "up":
            return _up(ports, args)
        if args.action == "down":
            if OWNER.is_file():
                STOP.touch()
                print("Stop requested.")
            else:
                print("No stack started by this workspace.")
            return 0
        if args.action == "wait":
            _wait_services(ports, args.timeout, [])
        return int(not _report(ports))
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"P7 stack: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
