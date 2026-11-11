from pathlib import Path
import stat

import pytest

from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import ArtifactError, UnsafePathError


def test_cache_roundtrip_no_overwrite(tmp_path: Path) -> None:
    area = ArtifactStore(tmp_path).cache("instances")
    assert area.get("example") is None
    assert not area.parent.exists()
    path = area.put("example", {"instance.json": b"first"})
    assert not (path / "instance.json").stat().st_mode & stat.S_IWRITE
    assert area.get("example") == {"instance.json": b"first"}
    with pytest.raises(FileExistsError):
        area.put("example", {"instance.json": b"second"})
    assert (path / "instance.json").read_bytes() == b"first"
    assert sorted(p.name for p in area.parent.iterdir()) == ["example"]


def test_unsafe_cache_entry_and_key(tmp_path: Path) -> None:
    area = ArtifactStore(tmp_path).cache("instances")
    with pytest.raises(UnsafePathError):
        area.get("../escape")
    entry = area.put("entry", {"ok": b"x"})
    (entry / "nested").mkdir()
    with pytest.raises((UnsafePathError, ArtifactError)):
        area.get("entry")


def test_publish_failure_removes_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    area = ArtifactStore(tmp_path).cache("instances")

    def fail(source: Path, destination: Path) -> None:
        raise PermissionError("injected")

    monkeypatch.setattr("scheduler_core.io.cache_area.publish_noreplace", fail)
    with pytest.raises(PermissionError):
        area.put("entry", {"ok": b"x"})
    assert list(area.parent.iterdir()) == []


def _compete(root: str, barrier: object, queue: object, value: bytes) -> None:
    from multiprocessing.synchronize import Barrier
    from multiprocessing.queues import Queue
    from typing import cast

    area = ArtifactStore(Path(root)).cache("instances")
    cast(Barrier, barrier).wait()
    try:
        area.put("race", {"data": value})
        cast("Queue[str]", queue).put("winner")
    except FileExistsError:
        cast("Queue[str]", queue).put("exists")


def test_multi_process_publication(tmp_path: Path) -> None:
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_compete, args=(str(tmp_path), barrier, queue, value))
        for value in (b"a", b"b")
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(20)
        assert process.exitcode == 0
    assert sorted([queue.get(timeout=2), queue.get(timeout=2)]) == ["exists", "winner"]
    area = ArtifactStore(tmp_path).cache("instances")
    assert area.get("race") in ({"data": b"a"}, {"data": b"b"})
    assert [p.name for p in area.parent.iterdir()] == ["race"]


def test_windows_junctions_rejected(tmp_path: Path) -> None:
    import os
    import subprocess

    if os.name != "nt":
        return
    target = tmp_path / "outside"
    target.mkdir()
    root = tmp_path / "root"
    area = ArtifactStore(root).cache("instances")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(area.parent), str(target)],
        check=True,
        capture_output=True,
    )
    with pytest.raises(UnsafePathError):
        area.get("item")
    area.parent.rmdir()
    area.parent.mkdir()
    junction = area.parent / "item"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)], check=True, capture_output=True
    )
    with pytest.raises(UnsafePathError):
        area.put("item", {"data": b"x"})


def test_write_and_chmod_failures_remove_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    area = ArtifactStore(tmp_path).cache("instances")

    def fail_write(path: Path, data: bytes, *, readonly: bool = False) -> None:
        raise OSError("write failure")

    monkeypatch.setattr("scheduler_core.io.cache_area.atomic_write", fail_write)
    with pytest.raises(OSError, match="write failure"):
        area.put("entry", {"data": b"x"})
    assert list(area.parent.iterdir()) == []


def test_existing_file_and_directory_untouched(tmp_path: Path) -> None:
    area = ArtifactStore(tmp_path).cache("instances")
    area.parent.mkdir()
    existing_file = area.parent / "file"
    existing_file.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        area.put("file", {"data": b"x"})
    assert existing_file.read_bytes() == b"original"
    existing_dir = area.parent / "empty"
    existing_dir.mkdir()
    with pytest.raises(FileExistsError):
        area.put("empty", {"data": b"x"})
    assert not list(existing_dir.iterdir())


def test_chmod_failure_removes_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    original = os.chmod
    calls = 0

    def fail_once(path: Path, mode: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("chmod failure")
        original(path, mode)

    area = ArtifactStore(tmp_path).cache("instances")
    monkeypatch.setattr(os, "chmod", fail_once)
    with pytest.raises(PermissionError, match="chmod failure"):
        area.put("entry", {"data": b"x"})
    assert list(area.parent.iterdir()) == []
