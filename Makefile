.PHONY: setup check
setup:
	uv tool run --no-env-file pre-commit install --hook-type pre-commit --hook-type pre-push
check:
	repo-docs check
	bash -n bin/agent-fork
	uv tool run --no-env-file --from shellcheck-py==0.11.0.1 shellcheck -S warning -s bash bin/agent-fork
	python3 tests/test-agent-fork.py
