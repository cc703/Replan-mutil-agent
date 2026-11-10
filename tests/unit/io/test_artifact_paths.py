"""Path safety acceptance checks."""

from pathlib import Path

import pytest

from scheduler_core.io import ArtifactStore, GitInfo, UnsafePathError


@pytest.mark.parametrize(
    "value",
    [
        "../x",
        "/x",
        "c:x",
        "a\\b",
        "con.txt",
        "a.",
        "FOO",
        "a//b",
        "manifest.json",
        "config.yaml",
        "foo~1",
    ],
)
def test_unsafe_paths_are_rejected(tmp_path: Path, value: str) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    with pytest.raises(UnsafePathError):
        run.path(value)


def test_directory_junction_is_rejected(tmp_path: Path) -> None:
    import os
    import subprocess

    run = ArtifactStore(tmp_path / "root").new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    link = run.dir / "linked"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(UnsafePathError):
            run.path("linked/output.json")
        with pytest.raises(UnsafePathError):
            run.write_json("linked/output.json", {})
        with pytest.raises(UnsafePathError):
            run.finish("completed")
        assert run.manifest.status == "running"
    finally:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()


def test_root_rejects_junction_before_parent_component(tmp_path: Path) -> None:
    import os
    import subprocess

    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(UnsafePathError):
            ArtifactStore(link / ".." / "root")
    finally:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()


@pytest.mark.parametrize("layer", ["runs", "kind"])
def test_new_run_rejects_junction_in_layout(tmp_path: Path, layer: str) -> None:
    import os
    import subprocess

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "runs" if layer == "runs" else root / "runs" / "sim"
    if layer == "kind":
        link.parent.mkdir()
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(UnsafePathError):
            ArtifactStore(root).new_run(
                "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
            )
    finally:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()


@pytest.mark.parametrize(
    "value",
    [
        "manifest.json",
        "MANIFEST.JSON",
        "manifest.json.",
        "config.yaml",
        "Config.yaml",
        "config.yaml.",
    ],
)
def test_reserved_aliases_rejected_by_all_mutations(tmp_path: Path, value: str) -> None:
    run = ArtifactStore(tmp_path).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    for action in (
        lambda: run.path(value),
        lambda: run.write_json(value, {}),
        lambda: run.finish("completed", outputs=[value]),
    ):
        with pytest.raises(UnsafePathError):
            action()
    assert run.manifest.status == "running"


@pytest.mark.parametrize("internal", [True, False])
def test_finish_rejects_output_directory_replaced_with_junction(
    tmp_path: Path, internal: bool
) -> None:
    import os
    import subprocess

    root = tmp_path / "root"
    run = ArtifactStore(root).new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    output = run.write_json("nested/out.json", {})
    before = (run.dir / "manifest.json").read_bytes()
    target = root / "other" if internal else tmp_path / "outside"
    target.mkdir()
    (target / "out.json").write_text("{}", encoding="utf-8")
    output.unlink()
    output.parent.rmdir()
    link = run.dir / "nested"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True
        )
    else:
        link.symlink_to(target, target_is_directory=True)
    try:
        with pytest.raises(UnsafePathError):
            run.finish("completed", outputs=["nested/out.json"])
        assert (run.dir / "manifest.json").read_bytes() == before
    finally:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()


def test_file_link_rejected_with_real_or_simulated_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler_core.io.paths as paths

    run = ArtifactStore(tmp_path / "root").new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    link = run.dir / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        link.write_text("{}", encoding="utf-8")
        original = paths._is_link
        monkeypatch.setattr(paths, "_is_link", lambda path: path == link or original(path))
    with pytest.raises(UnsafePathError):
        run.path("linked.json")


def test_hard_link_cannot_change_external_file(tmp_path: Path) -> None:
    import os
    import stat

    outside = tmp_path / "outside.txt"
    outside.write_text("original", encoding="utf-8")
    original_mode = os.stat(outside).st_mode
    run = ArtifactStore(tmp_path / "root").new_run(
        "sim", "sample", "tag", git=GitInfo(commit="abcdef0", dirty=False)
    )
    link = run.dir / "linked.txt"
    os.link(outside, link)
    before = (run.dir / "manifest.json").read_bytes()
    for action in (
        lambda: run.path("linked.txt"),
        lambda: run.write_json("linked.txt", {}),
        lambda: run.finish("completed", outputs=["linked.txt"]),
    ):
        with pytest.raises(UnsafePathError):
            action()
    assert (run.dir / "manifest.json").read_bytes() == before
    assert outside.read_text(encoding="utf-8") == "original"
    assert os.stat(outside).st_mode & stat.S_IWRITE == original_mode & stat.S_IWRITE
    link.unlink()
    assert run.finish("completed").status == "completed"
