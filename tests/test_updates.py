import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import updates


class UpdatesTests(unittest.TestCase):
    def test_parse_versions(self):
        self.assertEqual(updates.parse_updates('pkg 1:2-1 -> 1:3-1', 'Repository')[0]['new'], '1:3-1')
        with self.assertRaises(ValueError):
            updates.parse_updates('network error', 'Repository')

    def test_repository_no_updates_and_failure(self):
        with patch.object(updates.subprocess, 'run', return_value=subprocess.CompletedProcess([], 2, '', '')):
            self.assertEqual(updates.repositories()['items'], [])
        with patch.object(updates.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'offline')):
            self.assertEqual(updates.guarded(updates.repositories)['state'], 'error')

    def test_omarchy_independent_of_other_packages(self):
        for omarchy_update in (False, True):
            for package_update in (False, True):
                items = ([{'id': 'omarchy', 'new': '5'}] if omarchy_update else []) + ([{'id': 'firefox', 'new': '2'}] if package_update else [])
                with patch.dict(updates.os.environ, {'OMARCHY_PATH': '/usr/share/omarchy'}), patch.object(updates, 'run', side_effect=['4', 'omarchy']):
                    status = updates.omarchy_status(updates.result(items))
                    self.assertEqual(bool(status['items']), omarchy_update)
                    self.assertEqual(status['version'], '4')

    def test_omarchy_check_failure_is_not_current(self):
        with patch.dict(updates.os.environ, {'OMARCHY_PATH': '/usr/share/omarchy'}), patch.object(updates, 'run', side_effect=['4', 'omarchy']):
            self.assertEqual(updates.omarchy_status({'state': 'error'})['state'], 'error')

    def test_dev_fetch_error_and_updates(self):
        with patch.dict(updates.os.environ, {'OMARCHY_PATH': '/tmp/dev'}), patch.object(updates, 'run', side_effect=['dev (abc)', '', '2']):
            self.assertEqual(len(updates.omarchy_status({})['items']), 1)
        with patch.dict(updates.os.environ, {'OMARCHY_PATH': '/tmp/dev'}), patch.object(updates, 'run', side_effect=['dev', RuntimeError('offline')]):
            self.assertEqual(updates.guarded(lambda: updates.omarchy_status({}))['state'], 'error')

    def test_aur_unknown_and_versions(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({'type': 'multiinfo', 'results': [{'Name': 'aurpkg', 'Version': '2'}]}).encode()
        with patch.object(updates, 'run', side_effect=['aurpkg 1\nlocalpkg 1', '1']), patch.object(updates.urllib.request, 'urlopen', return_value=Response()):
            status = updates.aur()
            self.assertEqual(status['unknown'], ['localpkg'])
            self.assertEqual(status['items'][0]['source'], 'AUR')

    def test_plugin_modified_and_fast_forward(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(updates.Path, 'home', return_value=Path(tmp)):
            p = Path(tmp) / '.config/omarchy/plugins/test'
            (p / '.git').mkdir(parents=True)
            item = {'id': 'test', 'path': str(p)}
            with patch.object(updates, 'run', return_value=' M Panel.qml'):
                self.assertFalse(updates.plugin_check(item)['canUpdate'])
            with patch.object(updates, 'run', side_effect=['', 'https://github.com/a/b.git', 'abc', '', 'def']), patch.object(updates.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                self.assertTrue(updates.plugin_check(item)['canUpdate'])
            with patch.object(updates, 'run', side_effect=['', 'https://github.com/a/b.git', 'abc', '', 'def']), patch.object(updates.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
                self.assertEqual(updates.plugin_check(item)['state'], 'diverged')
            with patch.object(updates, 'run', side_effect=['', 'https://github.com/a/b.git', 'abc', RuntimeError('offline')]):
                self.assertEqual(updates.plugin_check(item)['state'], 'error')

    def test_plugin_non_git_and_invalid_id(self):
        self.assertFalse(updates.plugin_check({'id': 'x', 'path': '/tmp/x'})['canUpdate'])
        with self.assertRaises(ValueError): updates.update('plugin', '../x')

    def test_cache_ttl_and_repeated_failure_preserves_last_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(updates, 'STATE', Path(tmp)), patch.object(updates, 'CACHE', Path(tmp) / 'updates.json'):
            good = updates.result([{'id': 'pkg', 'old': '1', 'new': '2'}])
            with patch.object(updates, 'repositories', return_value=good), patch.object(updates, 'aur', return_value=updates.result()), patch.object(updates, 'plugins', return_value=updates.result()), patch.object(updates, 'omarchy_status', return_value=updates.result(version='4')):
                updates.check(True)
            with patch.object(updates, 'repositories', side_effect=RuntimeError('offline')) as repo, patch.object(updates, 'aur', return_value=updates.result()), patch.object(updates, 'plugins', return_value=updates.result()), patch.object(updates, 'omarchy_status', return_value=updates.result(version='4')):
                updates.check(False)
                repo.assert_not_called()
                for _ in range(2):
                    value = updates.check(True)
                    self.assertEqual(value['repositories']['lastSuccess']['items'][0]['new'], '2')

    def test_plugin_action_rechecks_and_keeps_native_review(self):
        import monitor
        with patch.object(monitor, 'read_plugins', return_value=[{'id': 'test'}]), patch.object(updates, 'plugin_check', return_value={'canUpdate': False, 'message': 'Local changes'}), patch.object(updates.subprocess, 'call') as call:
            with self.assertRaises(ValueError): updates.perform_update('plugin', 'test')
            call.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp, patch.object(updates, 'CACHE', Path(tmp) / 'cache'), patch.object(monitor, 'read_plugins', return_value=[{'id': 'test'}]), patch.object(updates, 'plugin_check', return_value={'canUpdate': True}), patch.object(updates.subprocess, 'call', return_value=0) as call, patch.object(updates.subprocess, 'run'):
            updates.perform_update('plugin', 'test')
            call.assert_called_once_with(['omarchy', 'plugin', 'update', 'test'])

    def test_duplicate_action_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(updates, 'STATE', Path(tmp)), patch.object(updates.fcntl, 'flock', side_effect=BlockingIOError), patch.object(updates.subprocess, 'call') as call:
            with self.assertRaises(ValueError): updates.update('system')
            call.assert_not_called()

    def test_system_handoff_preserves_prompt_and_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(updates, 'CACHE', Path(tmp) / 'cache'), patch.object(updates.subprocess, 'call', return_value=1) as call, patch.object(updates.subprocess, 'run'):
            updates.CACHE.write_text('{}')
            self.assertEqual(updates.update('system'), 1)
            call.assert_called_once_with(['omarchy', 'update'])
            self.assertFalse(updates.CACHE.exists())


if __name__ == '__main__': unittest.main()
