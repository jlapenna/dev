#!/usr/bin/env python3
"""Fixture-only contract checks. Never inspect processes or contact tmux."""
import atexit
import tempfile
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

TREE = Path(__file__).resolve().parents[1]
_temporary = tempfile.TemporaryDirectory(prefix="session-recovery-test-")
atexit.register(_temporary.cleanup)
ROOT = Path(_temporary.name)
HOME = ROOT / 'fixture-home'
BIN = ROOT / 'bin'
OUT = ROOT / 'outputs'
RECORDED = ROOT / 'repo'
LINKED = ROOT / 'issue-4821-export'
OTHER = ROOT / 'issue-5932-search'
for p in (HOME, BIN, OUT, RECORDED, LINKED, OTHER):
    p.mkdir(parents=True, exist_ok=True)
(ROOT / 'mock-calls.jsonl').write_text('')

env = {'HOME': str(HOME), 'PATH': str(BIN) + ':' + os.defpath,
       'HERDR_ENV': '0', 'TMUX': 'fixture-only-never-contact-real-server',
       'FIXTURE_ROOT': str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'}
env.pop('REVIVE_WORKTREE', None)
for name in ('git', 'tmux', 'herdr', 'claude', 'codex'):
    body = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
r = Path(os.environ['FIXTURE_ROOT'])
name = Path(sys.argv[0]).name
with (r / 'mock-calls.jsonl').open('a') as f:
    f.write(json.dumps({'command': name, 'argv': sys.argv[1:]}) + '\\n')
if name == 'git':
    cwd = sys.argv[2]
    args = sys.argv[3:]
    if args == ['rev-parse', '--show-toplevel']:
        print(cwd)
    elif args == ['worktree', 'list', '--porcelain']:
        for path, branch in [('repo', 'main'), ('issue-4821-export', 'fix/4821-export'), ('issue-5932-search', 'fix/5932-search')]:
            print('worktree ' + str(r / path) + '\\nHEAD fixture\\nbranch refs/heads/' + branch + '\\n')
    else:
        sys.exit(3)
elif name == 'tmux':
    if sys.argv[1:2] != ['new-window']:
        sys.exit(3)
    print('fixture-window:0')
else:
    print('unexpected command blocked: ' + name, file=sys.stderr)
    sys.exit(99)
'''
    (BIN / name).write_text(body)
    (BIN / name).chmod(0o755)

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return path

def claude_path(sid, cwd=RECORDED):
    return HOME / '.claude/projects' / str(cwd).replace('/', '-').replace('.', '-') / (sid + '.jsonl')

def codex_path(sid):
    return HOME / '.codex/sessions/2026/11/01' / ('rollout-2026-11-01T10-00-00-' + sid + '.jsonl')

def cm(role, text, sid='fixture-claude', cwd=RECORDED, **extra):
    return {'type': role, 'sessionId': sid, 'cwd': str(cwd), 'timestamp': '2026-11-01T10:00:00Z',
            'message': {'role': role, 'content': text}, **extra}

claude = write_jsonl(claude_path('fixture-claude'), [
    {'type': 'summary', 'summary': 'x' * 5000},
    cm('user', '# AGENTS.md\nfixture harness noise'),
    cm('user', 'Finish issue #4821 export validation. Keep going without asking.'),
    cm('user', 'Message Type: MESSAGE\nSender: peer\nPayload: PR #77 merged; use CSV.'),
    cm('user', 'No, keep JSON export. Do not deploy.'),
    cm('assistant', [{'type': 'text', 'text': 'PR #77 is merged. I stopped because quota was exhausted.'}]),
])
subclaude = write_jsonl(claude.parent / 'fixture-claude/subagents/agent-abc123.jsonl', [
    cm('user', 'Check the JSON export.', agentId='abc123')])

topid = '12345678-1111-4111-8111-111111111111'
subid = '23456789-2222-4222-8222-222222222222'
def meta(sid, thread_source='user', **extra):
    return {'type': 'session_meta', 'payload': {'id': sid, 'cwd': str(RECORDED),
            'thread_source': thread_source, 'timestamp': '2026-11-01T10:00:00Z', **extra}}
top = write_jsonl(codex_path(topid), [meta(topid),
    {'type': 'response_item', 'timestamp': '2026-11-01T10:01:00Z', 'payload':
        {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Continue issue #4821 export validation.'}]}},
    {'type': 'response_item', 'payload': {'type': 'function_call', 'call_id': 'a', 'name': 'exec_command', 'arguments': '{}'}},
    {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'a', 'output': 'passed'}},
    {'type': 'event_msg', 'payload': {'type': 'task_complete'}},
])
sub = write_jsonl(codex_path(subid), [meta(subid, 'subagent', source={'subagent': {'thread_spawn': {'parent_thread_id': topid}}}), meta(topid)])

checks = []
commands = []
def run(label, args):
    result = subprocess.run([str(a) for a in args], env=env, cwd=ROOT, text=True, capture_output=True, timeout=15)
    commands.append({'label': label, 'argv': [str(a) for a in args], 'returncode': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr})
    (OUT / (label + '.txt')).write_text('exit=' + str(result.returncode) + '\nSTDOUT\n' + result.stdout + '\nSTDERR\n' + result.stderr)
    return result

def check(label, passed, detail):
    checks.append({'label': label, 'passed': bool(passed), 'detail': detail})

TAKE = TREE / 'skills/takeover/scripts'
REV = TREE / 'skills/revive-tmux-session/scripts'
res = run('resolve-parent', ['bash', TAKE / 'find-session.sh', 'fixture-claude'])
check('resolve parent and nested child', res.returncode == 0 and str(claude) in res.stdout and str(subclaude) in res.stdout, res.stdout)
res = run('extract-claude', [sys.executable, TAKE / 'extract-transcript.py', claude, '--out', OUT / 'claude-extract.txt'])
extract = (OUT / 'claude-extract.txt').read_text()
check('human corrections and peer evidence preserved; harness noise removed', 'No, keep JSON export' in extract and 'Sender: peer' in extract and '# AGENTS.md' not in extract, extract[:500])
res = run('extract-claude-child', [sys.executable, TAKE / 'extract-transcript.py', subclaude])
check('Claude child identity and parent retained', '"id": "abc123"' in res.stdout and '"parent_session": "fixture-claude"' in res.stdout, res.stdout[:500])
res = run('extract-codex', [sys.executable, TAKE / 'extract-transcript.py', top])
check('Codex task and call result retained', 'Continue issue #4821' in res.stdout and 'passed' in res.stdout, res.stdout[:500])
agyid = '45678901-4444-4444-8444-444444444444'
agy = write_jsonl(HOME / '.gemini/antigravity-cli/brain' / agyid / '.system_generated/logs/transcript.jsonl', [
    {'step_index': 0, 'source': 'USER_EXPLICIT', 'type': 'USER_INPUT', 'status': 'DONE',
     'created_at': '2026-11-01T10:00:00Z', 'content': 'Fix agy title sync in Herdr.'},
    {'step_index': 1, 'source': 'MODEL', 'type': 'PLANNER_RESPONSE', 'status': 'DONE',
     'created_at': '2026-11-01T10:01:00Z', 'content': 'Checking herdr-session-titles.',
     'tool_calls': [{'name': 'read_file', 'args': {'Path': '/tmp/x'}}]},
    {'step_index': 2, 'source': 'MODEL', 'type': 'GENERIC', 'status': 'DONE',
     'created_at': '2026-11-01T10:01:05Z', 'content': 'File read ok.'},
])
res = run('resolve-agy', ['bash', TAKE / 'find-session.sh', agyid[:8]])
check('resolve Antigravity session by prefix', res.returncode == 0 and f'agy\t{agyid}\t{agy}' in res.stdout, res.stdout)
res = run('extract-agy', [sys.executable, TAKE / 'extract-transcript.py', agy])
check('Antigravity task and tool call retained', 'Fix agy title sync in Herdr.' in res.stdout and 'CALL read_file' in res.stdout, res.stdout[:500])

res = run('metadata-batch', [sys.executable, REV / 'transcript-meta.py', claude, subclaude, top, sub])
rows = [line.split('\x1f') for line in res.stdout.splitlines()]
check('metadata row has nine fields with empty parent preserved', len(rows) == 4 and all(len(r) == 9 for r in rows) and rows[2][7] == '', repr(rows))
check('Claude compaction header does not hide cwd', rows[0][3] == str(RECORDED), repr(rows[0]))
check('first Codex meta excludes subagent despite replayed parent', rows[3][2] == subid and rows[3][4] == 'no' and rows[3][7] == topid, repr(rows[3]))
check('completed ordinary function call classified completed', rows[2][8] == 'completed', repr(rows[2]))

customid = '34567890-3333-4333-8333-333333333333'
custom = write_jsonl(codex_path(customid), [meta(customid),
    {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'call_id': 'custom-a', 'name': 'apply_patch', 'input': 'fixture'}},
    {'type': 'response_item', 'payload': {'type': 'custom_tool_call_output', 'call_id': 'custom-a', 'output': 'Success'}},
    {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Patch applied.'}]}},
])
res = run('custom-call-completed', [sys.executable, REV / 'transcript-meta.py', custom])
check('completed custom call must not be classified cut off', 'ended mid tool-call' not in res.stdout, res.stdout)

res = run('infer-string-claude', [sys.executable, REV / 'infer-worktree.py', 'claude', 'fixture-claude', RECORDED])
check('plain string Claude task uniquely infers matching worktree', res.returncode == 0 and res.stdout.strip() == str(LINKED), res.stdout + res.stderr)
array = write_jsonl(claude_path('fixture-array'), [cm('user', [{'type': 'text', 'text': 'Finish issue #4821 export validation.'}], sid='fixture-array')])
res = run('infer-array-claude', [sys.executable, REV / 'infer-worktree.py', 'claude', 'fixture-array', RECORDED])
check('Claude text block task infers same matching worktree', res.returncode == 0 and res.stdout.strip() == str(LINKED), 'exit=' + str(res.returncode) + ' ' + res.stdout + res.stderr)
write_jsonl(claude_path('fixture-linked', LINKED), [cm('user', 'Earlier task was issue #5932 search; now continue existing worktree.', sid='fixture-linked', cwd=LINKED)])
res = run('infer-recorded-linked', [sys.executable, REV / 'infer-worktree.py', 'claude', 'fixture-linked', LINKED])
check('already-linked recorded cwd remains authoritative', res.returncode == 0 and res.stdout.strip() == str(LINKED), 'exit=' + str(res.returncode) + ' ' + res.stdout + res.stderr)

res = run('revive-child-refused', ['bash', REV / 'revive-dead.sh', 'codex', subid, RECORDED])
check('dead child refused before tmux launch', res.returncode == 1 and 'sub-agent/non-interactive' in res.stderr, res.stderr)
res = run('revive-top-mocked', ['bash', REV / 'revive-dead.sh', 'codex', topid, RECORDED, 'fixture-export'])
calls = [json.loads(line) for line in (ROOT / 'mock-calls.jsonl').read_text().splitlines()]
tmux_calls = [c for c in calls if c['command'] == 'tmux']
check('mocked top-level revive launches exact id and inferred worktree', res.returncode == 0 and len(tmux_calls) == 1 and str(LINKED) in tmux_calls[0]['argv'] and ('codex resume ' + topid) in tmux_calls[0]['argv'][-1], repr(tmux_calls))
check('no real CLI or Herdr invoked', not any(c['command'] in ('claude', 'codex', 'herdr') for c in calls), repr(calls))

(ROOT / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
(ROOT / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')
for item in checks:
    print(('PASS ' if item['passed'] else 'FAIL ') + item['label'])
print(str(sum(c['passed'] for c in checks)) + '/' + str(len(checks)) + ' passed')
sys.exit(0 if all(c['passed'] for c in checks) else 1)
