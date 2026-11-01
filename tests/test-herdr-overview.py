#!/usr/bin/env python3
"""Exercise overview launch/filter contracts without real Herdr or SSH sessions."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'herdr/overview/bin/herdr-overview'

MOCK = r'''
import json
import os
from pathlib import Path
import sys

root = Path(os.environ['FIXTURE_ROOT'])
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps({'tool': tool, 'args': args}) + '\n')
if tool == 'hostname':
    print('fixture-host')
    sys.exit(0)
if tool == 'setsid':
    temporary = root / 'controller.tmp'
    temporary.write_text(json.dumps(args))
    temporary.replace(root / 'controller.json')
    sys.exit(0)
if tool in ('ssh', 'tmux'):
    sys.exit('Forbidden live-system operation: ' + tool)

def out(value):
    print(json.dumps(value))

if args == ['machine', 'list', '--json']:
    out([{'label': 'remote-fixture', 'enabled': True,
          'target': 'invalid.example'}])
elif args[:2] == ['tab', 'create']:
    out({'result': {'tab': {'tab_id': 'ws-launch:t-overview'},
                    'root_pane': {'pane_id': 'root'}}})
elif args[:2] == ['tab', 'get']:
    counter = root / 'polls'
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    sys.exit(0 if count == 0 else 1)
elif args == ['agent', 'list']:
    out({'result': {'agents': [
        {'pane_id': 'a1', 'workspace_id': 'ws-project', 'name': 'agent-one'},
        {'pane_id': 'a2', 'workspace_id': 'ws-other', 'name': 'excluded-agent'},
        {'pane_id': 'a3', 'workspace_id': 'ws-project', 'name': 'agent-three'}]}})
elif args == ['workspace', 'list']:
    out({'result': {'workspaces': [
        {'workspace_id': 'ws-project', 'label': 'Project-A'},
        {'workspace_id': 'ws-other', 'label': 'other'}]}})
elif args[:2] == ['pane', 'list']:
    out({'result': {'panes': [
        {'pane_id': 'root', 'tab_id': 'ws-launch:t-overview'}]}})
elif args[:2] == ['pane', 'layout']:
    out({'result': {'layout': {'area': {'height': 40}}}})
elif args[:2] == ['pane', 'split']:
    counter = root / 'splits'
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    out({'result': {'pane': {'pane_id': 'cell-' + str(count)}}})
elif args[:2] in (['pane', 'run'], ['pane', 'rename']):
    # Record commands, never start terminal cells or log-tail processes.
    out({'result': {}})
else:
    sys.exit('Unexpected mocked command: ' + repr(args))
'''


class OverviewTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='herdr-overview-test-')
        self.addCleanup(temporary.cleanup)
        self.fixture = Path(temporary.name)
        self.bin = self.fixture / 'bin'
        self.bin.mkdir()
        home = self.fixture / 'home'
        (home / '.config/herdr').mkdir(parents=True)
        (home / '.config/herdr/config.toml').write_text('prefix = "ctrl+b"\n')
        (self.fixture / 'tmp').mkdir()
        # This allowlist is the whole child PATH. In particular, unlinking
        # setsid below cannot fall through to a host installation.
        for name in ('awk', 'bash', 'comm', 'cut', 'date', 'expand', 'grep',
                     'jq', 'mkdir', 'mktemp', 'mv', 'nohup', 'readlink', 'rm',
                     'sed', 'sleep', 'sort', 'tail', 'timeout', 'tput', 'uniq'):
            target = shutil.which(name, path=os.defpath)
            self.assertIsNotNone(target, 'Missing test prerequisite: ' + name)
            (self.bin / name).symlink_to(target)
        for name in ('herdr', 'hostname', 'setsid', 'ssh', 'tmux'):
            path = self.bin / name
            path.write_text('#!' + sys.executable + '\n' + MOCK)
            path.chmod(0o755)
        # Do not inherit BASH_ENV, shell functions, credentials, or real sockets.
        self.env = {
            'HOME': str(home), 'PATH': str(self.bin), 'LC_ALL': 'C',
            'TMPDIR': str(self.fixture / 'tmp'),
            'XDG_STATE_HOME': str(self.fixture / 'state'),
            'HERDR_ENV': '1', 'HERDR_WORKSPACE_ID': 'ws-launch',
            'HERDR_PANE_ID': 'invoker',
            'HERDR_BIN_PATH': str(self.bin / 'herdr'),
            'HERDR_MAIN_SOCKET': str(self.fixture / 'fixture.sock'),
            'HERDR_OVERVIEW_SCAN': '0.01',
            'FIXTURE_ROOT': str(self.fixture),
        }

    def run_script(self, *args):
        # Execute the shipped file directly: its executable bit is part of the
        # plugin contract, and a copied/chmodded script would hide regressions.
        return subprocess.run([str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True, timeout=5)

    def calls(self):
        path = self.fixture / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] \
            if path.exists() else []

    def test_local_named_workspace_is_read_only_and_preserves_focus(self):
        launch = self.run_script('--machine', 'local', '--workspace',
                                 'project-a', '--no-focus')
        self.assertEqual(launch.returncode, 0, launch.stderr)
        controller_path = self.fixture / 'controller.json'
        deadline = time.monotonic() + 3
        while not controller_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(controller_path.exists(), 'Controller was not dispatched')
        controller = json.loads(controller_path.read_text())
        self.assertEqual(controller[:3], ['nohup', str(SCRIPT), '--controller'])
        # The setsid mock only records startup. Run the captured controller in
        # the foreground with a deadline; tab get ends it after one scan.
        result = subprocess.run(controller[1:], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('2 agents: fixture-host=2', result.stdout)
        calls = self.calls()
        herdr = [call['args'] for call in calls if call['tool'] == 'herdr']
        create = next(args for args in herdr if args[:2] == ['tab', 'create'])
        self.assertIn('--no-focus', create)
        self.assertNotIn('--focus', create)
        splits = [args for args in herdr if args[:2] == ['pane', 'split']]
        self.assertTrue(splits)
        self.assertTrue(all('--no-focus' in args for args in splits))
        self.assertFalse(any(args and args[0] == '--machine' for args in herdr))
        self.assertFalse(any(args[:2] in (['agent', 'attach'], ['agent', 'focus'])
                             for args in herdr))
        cells = [args[3] for args in herdr
                 if args[:2] == ['pane', 'run'] and '--cell' in args[3]]
        self.assertEqual(len(cells), 2)
        self.assertTrue(all('--view' not in cell and 'fixture-host' in cell
                            for cell in cells))
        self.assertTrue(any('a1' in cell for cell in cells))
        self.assertTrue(any('a3' in cell for cell in cells))
        self.assertTrue(all('excluded-agent' not in cell for cell in cells))
        self.assertFalse(any(call['tool'] in ('ssh', 'tmux') for call in calls))

    def test_missing_setsid_fails_before_creating_a_tab(self):
        (self.bin / 'setsid').unlink()
        self.assertIsNone(shutil.which('setsid', path=self.env['PATH']))
        result = self.run_script('--machine', 'local', '--workspace',
                                 'project-a', '--no-focus')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('setsid', result.stderr)
        self.assertFalse(any(call['tool'] == 'herdr' and
                             call['args'][:2] == ['tab', 'create']
                             for call in self.calls()))


if __name__ == '__main__':
    unittest.main()
