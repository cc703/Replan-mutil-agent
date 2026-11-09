.PHONY: check check-layout test-governance clean-tmp
check:
	uv run --python 3.11 --group dev python tools/check.py
check-layout:
	uv run --python 3.11 --group dev python tools/check_repo_layout.py
test-governance:
	uv run --python 3.11 --group dev python -m pytest -q
clean-tmp:
	uv run --python 3.11 --group dev python tools/check.py --list-tmp
