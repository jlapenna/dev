"""Verify fork targets without creating live panes, terminals or agents."""
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

# --- herdr-core (`hc`) backend ------------------------------------------------
HC_MOCK = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps(args) + '\\n')
if args[:1] == ['get']:
    get = json.loads(Path(os.environ['HC_GET_FIXTURE']).read_text())
    if args[1] not in get:
        sys.exit('unknown terminal ' + args[1])
    print(json.dumps(get[args[1]]))
elif args[:1] == ['ls']:
    print(Path(os.environ['HC_LS_FIXTURE']).read_text())
elif args[:1] == ['connect']:
    req = json.loads(sys.stdin.read())
    with open(os.environ['CALL_LOG'], 'a') as f:
        f.write('REQ ' + json.dumps(req) + '\\n')
    p = req['params']
    taken = json.loads(Path(os.environ['HC_LS_FIXTURE']).read_text())
    if p['name'] in {t['name'] for t in taken['terminals']}:
        sys.exit(1)
    sent = len(p['argv']) > 1
    print(json.dumps({'jsonrpc': '2.0', 'id': 1, 'result':
                      {'address': 't99', 'first_message': {'sent': sent}}}))
elif args[:1] in [['send'], ['wait'], ['keys'], ['read'], ['rm']]:
    pass
else:
    sys.exit('Unexpected hc command: ' + repr(args))
'''

def run_hc(topology='pane', title='', kind='codex', fg_agent='codex', taken=(),
           exit_term=None, exit_status=None, home=None, extra_env=()):
    with tempfile.TemporaryDirectory(prefix='agent-fork-hc-') as d:
        d = Path(d)
        hc = d / 'hc'
        hc.write_text(HC_MOCK)
        hc.chmod(0o700)
        self_term = {'address': 't1k', 'name': 'src', 'agent': fg_agent,
                     'cwd': '/repo',
                     'created_ms': int(time.time() * 1000) - 60000,
                     'foreground': (None if fg_agent is None else
                                    {'name': fg_agent, 'pid': 0})}
        got = {'t1k': self_term if not exit_term else
               {'address': exit_term, 'cwd': '/repo',
                'foreground': {'name': 'codex', 'pid': 0}}}
        if exit_term:
            got[exit_term] = {'address': exit_term, 'agent': 'codex',
                              'status': exit_status,
                              'foreground': {'name': 'codex'}}
        ls = {'terminals': [{'address': 't1k', 'name': 'src'}] +
              [{'address': 'tx%d' % n, 'name': n_} for n, n_ in enumerate(taken)]}
        (d / 'get.json').write_text(json.dumps(got))
        (d / 'ls.json').write_text(json.dumps(ls))
        log = d / 'calls.jsonl'
        env = dict(PATH=str(d) + ':' + os.environ['PATH'],
                   HC_TERMINAL_ID='t1k', HC_TERMINAL_SOCKET=str(d / 'core.sock'),
                   CALL_LOG=str(log), HC_GET_FIXTURE=str(d / 'get.json'),
                   HC_LS_FIXTURE=str(d / 'ls.json'), FORK_TEST_VAR='keep=me',
                   AGENT_EXIT_DELAY='0', HOME=str(home or d))
        env.update(dict(extra_env))
        # A child started with this env models the agent process: /proc/<pid>/
        # environ then holds exactly what the fork should inherit.
        model = None
        if got['t1k']['foreground'] is not None:
            model = subprocess.Popen(['sleep', '30'], env=env, close_fds=False)
            got['t1k']['foreground']['pid'] = model.pid
            if exit_term:
                got[exit_term]['foreground']['pid'] = model.pid
            (d / 'get.json').write_text(json.dumps(got))
        argv = ['bash', str(SCRIPT), topology] + ([title] if title else [])
        try:
            result = subprocess.run(argv, env=env, input='Debug task\n',
                                    text=True, capture_output=True, timeout=10)
        finally:
            if model:
                model.terminate()
        if topology == 'exit':
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                n = log.read_text().count('\n') if log.exists() else 0
                if n >= (5 if exit_status == 'idle' else 3):
                    break
                time.sleep(0.05)
            time.sleep(0.2)
        calls, request = [], None
        if log.exists():
            for line in log.read_text().splitlines():
                if line.startswith('REQ '):
                    request = json.loads(line[4:])
                else:
                    calls.append(json.loads(line))
        return result, calls, request

def codex_home(tmp, sid='sid-1', cwd='/repo', offset_ms=0):
    home = Path(tmp) / 'home'
    day = time.strftime('%Y-%m-%d')
    sess = home / '.codex' / 'sessions' / day
    sess.mkdir(parents=True)
    (sess / 'rollout-fixture.jsonl').write_text(json.dumps(
        {'timestamp': '2026-01-01T00:00:00Z', 'type': 'session_meta',
         'payload': {'id': sid, 'cwd': cwd}}) + '\n')
    ts = time.time() - offset_ms / 1000
    os.utime(sess / 'rollout-fixture.jsonl', (ts, ts))
    return home

with tempfile.TemporaryDirectory() as tmp:
    home = codex_home(tmp)
    result, calls, req = run_hc(title='Investigate cache misses', home=home)
    assert result.returncode == 0, result.stderr
    assert req is not None, calls
    p = req['params']
    assert req['method'] == 'terminal.run'
    assert p['name'] == 'investigate-cache-misses'
    assert p['caller'] == 't1k' and p['cwd'] == '/repo'
    assert p['bg'] is True and p['outlive_parent'] is True
    assert p['argv'][:4] == ['codex', 'fork',
                            '--dangerously-bypass-approvals-and-sandbox', 'sid-1'], p['argv']
    notice = p['argv'][-1]
    assert 'fork of Codex session sid-1' in notice and 'herdr terminal t1k' in notice
    assert 'run `agent-fork exit` as your last command' in notice
    assert 'Leave user-facing sessions open' in notice
    assert 'Debug task' in notice
    assert 'Your session title is "Investigate cache misses".' in notice
    assert p['env'].get('FORK_TEST_VAR') == 'keep=me', p['env']
    assert not [k for k in p['env'] if k.startswith('HC_')], p['env']
    assert 't99' in result.stdout and 't1k' in result.stdout
    assert not [c for c in calls if c[:1] == ['run']], calls
    print('PASS: hc fork asks the core to run the agent fork command with the notice and the agent env')

with tempfile.TemporaryDirectory() as tmp:
    home = codex_home(tmp)
    result, calls, req = run_hc(home=home)
    assert result.returncode == 0, result.stderr
    assert req['params']['name'].startswith('fork-codex-'), req['params']['name']
    print('PASS: hc fork without a title keeps a placeholder name')

with tempfile.TemporaryDirectory() as tmp:
    home = codex_home(tmp)
    result, calls, req = run_hc(title='Inbox cold load', taken=('inbox-cold-load',), home=home)
    assert result.returncode == 0, result.stderr
    assert req['params']['name'] == 'inbox-cold-load-2', req['params']['name']
    print('PASS: a taken hc terminal name gets a numeric suffix')

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / 'home'
    (home / '.codex' / 'sessions').mkdir(parents=True)
    result, calls, req = run_hc(title='No session', home=home)
    assert result.returncode != 0 and 'could not resolve' in result.stderr, result.stderr
    assert req is None
    print('PASS: hc fork refuses before spawning when the session id is unresolved')

result, calls, req = run_hc(title='No agent', fg_agent=None,
                            home=str(Path('/nonexistent')))
assert result.returncode != 0 and 'no supported coding agent' in result.stderr, result.stderr
print('PASS: hc fork refuses when the terminal foreground is not a coding agent')

with tempfile.TemporaryDirectory() as tmp:
    home = codex_home(tmp)
    result, calls, req = run_hc(title='Spaced  unicode 任务', home=home)
    assert result.returncode == 0, result.stderr
    assert req['params']['name'] == 'spaced-unicode', req['params']['name']
    print('PASS: hc fork slugifies spaced and unicode titles')

with tempfile.TemporaryDirectory() as tmp:
    home = codex_home(tmp, sid='sid-1')
    oc = home / '.local' / 'share' / 'opencode'
    oc.mkdir(parents=True)
    db = oc / 'opencode.db'
    subprocess.run(['sqlite3', str(db),
                    'create table session (id text, title text, time_created integer)'],
                   check=True)
    subprocess.run(['sqlite3', str(db),
                    "insert into session values ('oc-sid-1', 't', %d)"
                    % (int(time.time() * 1000) - 30000)], check=True)
    result, calls, req = run_hc(title='Opencode fork', fg_agent='opencode',
                                kind='opencode', home=home)
    assert result.returncode == 0, result.stderr
    assert req['params']['argv'][:3] == ['opencode', '--session', 'oc-sid-1'], req['params']['argv']
    assert '--fork' in req['params']['argv'] and '--auto' in req['params']['argv']
    assert len(req['params']['argv']) == len(req['params']['argv']), None
    sent = next(c for c in calls if c[:1] == ['send'])
    assert sent[1] == 't99' and 'fork of OpenCode session oc-sid-1' in sent[2], sent
    assert 'Debug task' in sent[2]
    print('PASS: hc fork sends the OpenCode notice separately because opencode takes no positional task')

result, calls, req = run_hc('exit', exit_term='t99', exit_status='idle')
assert result.returncode == 0, result.stderr
get_wait = [c for c in calls if c[:1] == ['wait']]
assert get_wait and get_wait[0][:2] == ['wait', 't99'], calls
final_gets = [c for c in calls if c[:1] == ['get'] and c[1] == 't99']
assert final_gets, calls
assert ['send', 't99', '/exit'] in calls, calls
assert ['rm', 't99'] not in calls  # hc kill/rm only when it exits on its own
print('PASS: hc exit waits for the turn, then sends /exit')

result, calls, req = run_hc('exit', exit_term='t99', exit_status='working')
assert result.returncode == 0, result.stderr
assert ['send', 't99', '/exit'] not in calls, calls
print('PASS: hc exit stands down when the session is busy again')

print('ALL hc BACKEND TESTS PASSED')
