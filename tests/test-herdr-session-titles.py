#!/usr/bin/env python3
"""Protect the saved-title-to-Herdr contract without changing real sessions."""

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SCRIPT = ROOT / 'bin/herdr-session-titles'
loader = importlib.machinery.SourceFileLoader('titles', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
titles = importlib.util.module_from_spec(spec)
loader.exec_module(titles)


def agent(kind, sid):
    return {'agent': kind, 'pane_id': 'w1:p1', 'agent_session': {
        'agent': kind, 'kind': 'id', 'value': sid, 'source': 'herdr:' + kind}}


def write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(r) for r in records) + '\n')


class TitlesTest(unittest.TestCase):
    def test_saved_renames_win_and_malformed_lines_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            write(home / '.codex/session_index.jsonl', [
                {'id': 'codex-id', 'thread_name': 'Old'},
                {'id': 'codex-id', 'thread_name': 'Renamed Codex'}])
            index = home / '.codex/session_index.jsonl'
            with index.open('a') as stream:
                stream.write('null\n{"partial":\n')
            claude = agent('claude', 'claude-id')
            claude['terminal_title_stripped'] = 'Chosen Claude'
            codex = agent('codex', 'codex-id')
            codex['terminal_title_stripped'] = 'Old terminal title'
            agy = agent('agy', 'agy-id')
            agy['terminal_title_stripped'] = 'Terminal Agy Title'
            original_open = Path.open

            def metadata_only(path, *args, **kwargs):
                self.assertEqual(path, index, 'must never open a transcript')
                return original_open(path, *args, **kwargs)

            with patch.dict(os.environ, {'CODEX_HOME': str(home / '.codex'),
                                         'CLAUDE_CONFIG_DIR': str(home / '.claude')}), \
                    patch.object(Path, 'open', metadata_only), \
                    patch.object(Path, 'glob', side_effect=AssertionError('no transcript scans')):
                found = titles.saved_titles([
                    codex, claude, agy,
                    agent('claude', '../outside'), agent('claude', 'missing')], home)
            self.assertEqual(found, {('codex', 'codex-id'): 'Renamed Codex',
                                     ('claude', 'claude-id'): 'Chosen Claude',
                                     ('agy', 'agy-id'): 'Terminal Agy Title'})

    def test_changed_session_is_not_given_the_previous_title(self):
        original, replacement = agent('codex', 'old'), agent('codex', 'new')
        for current, expected_writes in [(original, 2), (replacement, 0)]:
            with self.subTest(current=current), patch.object(titles, 'call') as call:
                call.side_effect = [{'result': {'agents': [original]}},
                                    {'result': {'pane': current}}, {}, {}]
                with patch.object(titles, 'saved_titles', return_value={
                        ('codex', 'old'): 'Saved title'}):
                    titles.sync()
                writes = [c.args for c in call.call_args_list
                          if c.args[:2] not in [('agent', 'list'), ('pane', 'get')]]
                self.assertEqual(len(writes), expected_writes)
                if writes:
                    self.assertEqual(writes[0], ('pane', 'rename', 'w1:p1', 'Saved title'))
                    self.assertEqual(writes[1][:2], ('pane', 'report-metadata'))
                    self.assertIn('Saved title', writes[1])

    def test_help_never_contacts_herdr_or_reads_sessions(self):
        with patch.object(sys, 'argv', [str(SCRIPT), '--help']), \
                patch('subprocess.run', side_effect=AssertionError('help must be inert')), \
                patch.object(Path, 'open', side_effect=AssertionError('no session reads')), \
                patch('sys.stdout'), self.assertRaises(SystemExit) as result:
            runpy.run_path(str(SCRIPT), run_name='__main__')
        self.assertEqual(result.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
