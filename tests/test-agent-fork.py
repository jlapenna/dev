"""Verify forks after workspace moves without creating live panes or agents."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'bin/agent-fork'
PANE = {'pane_id': 'wE:p7', 'workspace_id': 'wE', 'agent': 'codex',
        'agent_session': {'agent': 'codex', 'kind': 'id', 'value': 'parent-session'}}
MOCK = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps(args) + '\\n')
pane = json.loads(Path(os.environ['PANE_FIXTURE']).read_text())['result']['pane']
if args[:2] == ['pane', 'get']:
    print(json.dumps({'result': {'pane': pane}}))
elif args[:2] == ['agent', 'list']:
    print(json.dumps({'result': {'agents': [pane]}}))
elif args[:2] == ['tab', 'create']:
    print(json.dumps({'result': {'root_pane': {'pane_id': 'wE:pNEW'}}}))
elif args[:2] == ['pane', 'split']:
    print(json.dumps({'result': {'pane': {'pane_id': 'wE:pNEW'}}}))
elif args[:2] not in [['agent', 'start'], ['agent', 'prompt'], ['agent', 'wait'],
                      ['pane', 'close']]:
    sys.exit('Unexpected command: ' + repr(args))
'''

def run(topology, inherited, missing=False, title=None, taken=None, kind=None,
        status=None):
    with tempfile.TemporaryDirectory(prefix='agent-fork-fixture-') as d:
        d = Path(d)
        mock = d / 'herdr'
        mock.write_text(MOCK)
        mock.chmod(0o700)
        pane = {'result': {'pane': dict(PANE)}}
        if kind:
            pane['result']['pane']['agent'] = kind
            pane['result']['pane']['agent_session']['agent'] = kind
        if taken:
            pane['result']['pane']['name'] = taken
        if missing:
            pane['result']['pane'].pop('agent_session', None)
        if status:
            pane['result']['pane']['agent_status'] = status
        fixture = d / 'pane.json'
        fixture.write_text(json.dumps(pane))
        log = d / 'calls.jsonl'
        # Do not inherit exported shell functions or BASH_ENV: they can bypass
        # the mock PATH and contact the real Herdr server.
        env = dict(PATH=str(d) + ':' + os.environ['PATH'],
                   HERDR_ENV='1', HERDR_PANE_ID=inherited,
                   HERDR_WORKSPACE_ID=inherited.split(':')[0],
                   PANE_FIXTURE=str(fixture), CALL_LOG=str(log),
                   AGENT_EXIT_DELAY='0')
        argv = ['bash', str(SCRIPT), topology] + ([title] if title is not None else [])
        result = subprocess.run(argv, env=env,
                                input='Debug task\n', text=True, capture_output=True,
                                timeout=5)
        if topology == 'exit':
            # The waiter is detached; give it time to finish against the mock.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                done = log.exists() and log.read_text().count('\n') >= (5 if status == 'idle' else 3)
                if done:
                    break
                time.sleep(0.05)
            time.sleep(0.2)
        calls = [json.loads(s) for s in log.read_text().splitlines()] if log.exists() else []
        return result, calls

sid = PANE['agent_session']['value']
for topology, inherited in [('tab', 'wA:p15'), ('pane', 'wA:p15'), ('tab', 'wE:p7')]:
    result, calls = run(topology, inherited)
    assert result.returncode == 0, result.stderr
    creation = next(c for c in calls if c[:2] in [['tab', 'create'], ['pane', 'split']])
    option, expected = ('--workspace', 'wE') if topology == 'tab' else ('--pane', 'wE:p7')
    assert creation[creation.index(option)+1] == expected, creation
    assert '--no-focus' in creation
    start = next(c for c in calls if c[:2] == ['agent', 'start'])
    assert sid in start and '--dangerously-bypass-approvals-and-sandbox' in start
    prompt = next(c for c in calls if c[:2] == ['agent', 'prompt'])[-1]
    assert 'herdr pane wE:p7.' in prompt and 'Debug task' in prompt
    assert 'run `agent-fork exit` as your last command' in prompt
    assert 'Leave user-facing sessions open' in prompt
    assert 'parent Codex session parent-session in herdr pane wE:p7' in prompt
    assert 'Verify the recipient is still that parent session' in prompt
    assert 'confirm successful delivery' in prompt
    assert 'stay open and report the blocker' in prompt
    assert 'continues in pane wE:p7.' in result.stdout
    print(f'PASS: {topology} from {inherited} uses canonical pane/workspace/session')

result, calls = run('tab', 'wA:p15', missing=True)
assert result.returncode != 0 and 'could not resolve the session id' in result.stderr
assert len(calls) == 1
print('PASS: missing session refuses before creating a tab')

result, calls = run('tab', 'wE:p7')
start = next(c for c in calls if c[:2] == ['agent', 'start'])
assert start[2].startswith('fork-codex-'), start
prompts = [c[-1] for c in calls if c[:2] == ['agent', 'prompt']]
assert len(prompts) == 1 and '/rename <title>' in prompts[0], prompts
print('PASS: untitled fork keeps a placeholder name and is told to retitle itself')

result, calls = run('tab', 'wE:p7', title='  #2082 Toolchain   Validate split timing ')
assert result.returncode == 0, result.stderr
start = next(c for c in calls if c[:2] == ['agent', 'start'])
assert start[2] == 'fork-2082-toolchain-validate', start
prompts = [c for c in calls if c[:2] == ['agent', 'prompt']]
assert prompts[0][2:] == [start[2], '/rename #2082 Toolchain Validate split timing'], prompts
assert 'Your session title is "#2082 Toolchain Validate split timing".' in prompts[1][-1]
print('PASS: title becomes the agent name slug and is applied with /rename before the notice')

result, calls = run('pane', 'wE:p7', title='Inbox cold load', taken='inbox-cold-load')
start = next(c for c in calls if c[:2] == ['agent', 'start'])
assert start[2] == 'inbox-cold-load-2', start
print('PASS: a taken agent name gets a numeric suffix')

result, calls = run('tab', 'wE:p7', title='Spam triage', kind='opencode')
assert result.returncode == 0, result.stderr
prompts = [c for c in calls if c[:2] == ['agent', 'prompt']]
assert prompts[0][-1] == '/rename Spam triage', prompts
print('PASS: OpenCode forks are retitled with /rename too')

result, calls = run('tab', 'wE:p7', title='Agy task', kind='agy')
assert result.returncode == 0, result.stderr
start = next(c for c in calls if c[:2] == ['agent', 'start'])
assert '--dangerously-skip-permissions' in start and '--conversation' in start and sid in start, start
prompts = [c for c in calls if c[:2] == ['agent', 'prompt']]
assert prompts[0][-1] == '/fork', prompts
assert prompts[1][-1] == '/rename Agy task', prompts
assert 'parent Antigravity session parent-session in herdr pane wE:p7' in prompts[2][-1], prompts
print('PASS: Antigravity forks branch with /fork and retitle with /rename')

result, calls = run('exit', 'wA:p15', status='idle')
assert result.returncode == 0, result.stderr
assert 'pane wE:p7 closes' in result.stdout
assert calls == [['pane', 'get', 'wA:p15'],
                 ['agent', 'wait', 'wE:p7', '--until', 'idle', '--until', 'done', '--timeout', '1800000'],
                 ['pane', 'get', 'wE:p7'],
                 ['agent', 'prompt', 'wE:p7', '/exit'],
                 ['pane', 'close', 'wE:p7']], calls
print('PASS: exit waits for the turn, sends /exit, then closes the canonical pane')

result, calls = run('exit', 'wE:p7', status='working')
assert result.returncode == 0, result.stderr
assert ['agent', 'prompt', 'wE:p7', '/exit'] not in calls and ['pane', 'close', 'wE:p7'] not in calls, calls
print('PASS: exit stands down when the session is busy again')
