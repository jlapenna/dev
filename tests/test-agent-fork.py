"""Verify forks after workspace moves without creating live panes or agents."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

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
elif args[:2] not in [['agent', 'start'], ['agent', 'prompt']]:
    sys.exit('Unexpected command: ' + repr(args))
'''

def run(topology, inherited, missing=False, title=None, taken=None, kind=None):
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
        fixture = d / 'pane.json'
        fixture.write_text(json.dumps(pane))
        log = d / 'calls.jsonl'
        # Do not inherit exported shell functions or BASH_ENV: they can bypass
        # the mock PATH and contact the real Herdr server.
        env = dict(PATH=str(d) + ':' + os.environ['PATH'],
                   HERDR_ENV='1', HERDR_PANE_ID=inherited,
                   HERDR_WORKSPACE_ID=inherited.split(':')[0],
                   PANE_FIXTURE=str(fixture), CALL_LOG=str(log))
        argv = ['bash', str(SCRIPT), topology] + ([title] if title is not None else [])
        result = subprocess.run(argv, env=env,
                                input='Debug task\n', text=True, capture_output=True,
                                timeout=5)
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
