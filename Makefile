.PHONY: setup check
setup:
	uv tool run --no-env-file pre-commit install --hook-type pre-commit --hook-type pre-push
check:
	repo-docs check
	bash -n bin/agent-fork
	uv tool run --no-env-file --from shellcheck-py==0.11.0.1 shellcheck -S warning -s bash bin/agent-fork
	python3 tests/test-agent-fork.py

	python3 tests/test-session-recovery.py
	python3 tests/test-herdr-session-titles.py
	python3 tests/test-herdr-overview.py
	python3 skills/external-pr-checkin/scripts/test_discovery.py
	@for script in skills/*/scripts/*.sh herdr/overview/bin/herdr-overview; do bash -n "$$script" || exit; done
	uv tool run --no-env-file --from shellcheck-py==0.11.0.1 shellcheck -S warning -s bash skills/takeover/scripts/find-session.sh skills/revive-tmux-session/scripts/*.sh herdr/overview/bin/herdr-overview
