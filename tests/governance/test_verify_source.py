from __future__ import annotations
import hashlib
import json
from pathlib import Path
from tools.verify_source import CANONICAL, verify


def fixture(root: Path) -> list[Path]:
    folder = root / "docs/source"
    folder.mkdir(parents=True)
    entries = []
    paths = []
    for name in sorted(CANONICAL):
        path = root / name
        data = b"alpha\nbeta\n"
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        entries.append(
            {
                "path": name,
                "original_name": "source.md",
                "encoding": "UTF-8",
                "newline": "LF",
                "source": "test",
                "verified_at": "test",
                "bytes": len(data),
                "lines": 2,
                "sha256": digest,
                "batches": [{"start": 1, "end": 2, "bytes": len(data), "sha256": digest}],
            }
        )
        paths.append(path)
    (folder / "manifest.json").write_text(json.dumps({"files": entries}), encoding="utf-8")
    return paths


def test_valid(tmp_path: Path) -> None:
    fixture(tmp_path)
    assert verify(tmp_path)


def test_tamper(tmp_path: Path) -> None:
    fixture(tmp_path)[0].write_bytes(b"AlphA\nbeta\n")
    assert not verify(tmp_path)


def test_missing(tmp_path: Path) -> None:
    fixture(tmp_path)[0].unlink()
    assert not verify(tmp_path)


def test_crlf(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    data = b"alpha\r\nbeta\r\n"
    paths[0].write_bytes(data)
    manifest_path = tmp_path / "docs/source/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["files"][0]
    entry["bytes"] = len(data)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    entry["batches"][0].update(bytes=len(data), sha256=entry["sha256"])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not verify(tmp_path)


def test_batch_mismatch(tmp_path: Path) -> None:
    fixture(tmp_path)
    path = tmp_path / "docs/source/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"][0]["batches"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not verify(tmp_path)


def mutate(root: Path, change: object) -> None:
    path = root / "docs/source/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert callable(change)
    change(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_duplicate_and_empty_batches(tmp_path: Path) -> None:
    fixture(tmp_path)
    mutate(tmp_path, lambda m: m["files"].__setitem__(1, m["files"][0]))
    assert not verify(tmp_path)
    fixture_manifest = tmp_path / "docs/source/manifest.json"
    fixture_manifest.unlink()
    # Restore only the manifest via a fresh fixture.
    import shutil

    shutil.rmtree(tmp_path / "docs/source")
    fixture(tmp_path)
    mutate(tmp_path, lambda m: m["files"][0].update(batches=[]))
    assert not verify(tmp_path)


def test_gap_or_overlap(tmp_path: Path) -> None:
    fixture(tmp_path)

    def change(m: dict) -> None:
        b = m["files"][0]["batches"][0]
        b["end"] = 1
        m["files"][0]["batches"].append(dict(b, start=1, end=2))

    mutate(tmp_path, change)
    assert not verify(tmp_path)


def test_unsafe_paths(tmp_path: Path) -> None:
    fixture(tmp_path)
    for name in ("../outside", str((tmp_path / "outside").resolve())):
        mutate(tmp_path, lambda m: m["files"][0].update(path=name))
        assert not verify(tmp_path)


def test_bad_types(tmp_path: Path) -> None:
    fixture(tmp_path)
    mutate(tmp_path, lambda m: m["files"][0].update(lines=True))
    assert not verify(tmp_path)


def test_gap(tmp_path: Path) -> None:
    fixture(tmp_path)
    mutate(tmp_path, lambda m: m["files"][0]["batches"][0].update(start=2))
    assert not verify(tmp_path)


def test_symlink_escape(tmp_path: Path) -> None:
    import pytest

    paths = fixture(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_bytes(paths[0].read_bytes())
    paths[0].unlink()
    try:
        paths[0].symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert not verify(tmp_path)
