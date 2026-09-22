import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess
import json

spec = importlib.util.spec_from_file_location('marketplace', Path(__file__).parents[1] / 'scripts/marketplace.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def plugin(**changes):
    return dict(id='example.plugin', name='Example', repo='https://github.com/user/example',
                sourceType='community', repositoryLayout='root-plugin', installAvailable=True,
                status='Available', **changes)


class MarketplaceTests(unittest.TestCase):
    def catalog(self, **changes):
        p = plugin()
        p.update(changes)
        return m.normalize_catalog({'plugins': [p]})

    def test_builds_native_command_not_catalog_command(self):
        c = self.catalog(installCommand='touch /tmp/should-never-run')
        self.assertEqual(m.install_command(c, 'example.plugin', 'https://github.com/user/example', []),
                         ['omarchy', 'plugin', 'add', 'https://github.com/user/example.git', '--enable'])

    def test_unsafe_repositories_cannot_install(self):
        for repo in ['https://github.com.evil/user/repo', 'https://github.com/user/repo;echo',
                     'ext::sh -c whoami', '--help', 'https://user@github.com/user/repo',
                     'https://github.com/user/repo?x=1', 'https://github.com/user/../repo']:
            with self.subTest(repo=repo):
                self.assertFalse(self.catalog(repo=repo)['plugins'][0]['installable'])

    def test_unavailable_and_manual_plugins_are_browsable_but_not_installable(self):
        for changes in [{'installAvailable': False}, {'repositoryLayout': 'monorepo'},
                        {'status': 'Compatibility failed'}, {'sourceType': 'builtin'},
                        {'status': 'Status unknown'}]:
            c = self.catalog(**changes)
            self.assertEqual(len(c['plugins']), 1)
            with self.assertRaises(ValueError):
                m.install_command(c, 'example.plugin', 'https://github.com/user/example', [])

    def test_inventory_and_changed_repository_block_install(self):
        c = self.catalog()
        for installed in [[{'id':'example.plugin'}], {}, [{}]]:
            with self.assertRaises(ValueError):
                m.install_command(c, 'example.plugin', 'https://github.com/user/example', installed)
        with self.assertRaisesRegex(ValueError, 'repository changed'):
            m.install_command(c, 'example.plugin', 'https://github.com/other/repo', [])

    def test_duplicate_ids_and_invalid_catalog_rejected(self):
        for data in [{}, {'plugins':[plugin(), plugin()]}, {'plugins':[{'id':'../../bad'}]}]:
            with self.assertRaises(ValueError): m.normalize_catalog(data)

    def test_updated_snapshot_never_inherits_verified_label(self):
        row = self.catalog(verificationStatus='verified', verificationCoverage='update-unverified')['plugins'][0]
        self.assertEqual(row['verification'], 'Update unverified')

    def test_fetch_failure_never_runs_installer(self):
        with patch.object(m, 'fetch_catalog', side_effect=OSError('offline')), patch.object(m.subprocess,'run') as run:
            with self.assertRaises(OSError): m.install('example.plugin', 'https://github.com/user/example')
            run.assert_not_called()

    def test_install_reloads_catalog_and_keeps_native_confirmation(self):
        with patch.object(m, 'fetch_catalog', return_value=self.catalog()) as fetch, patch.object(m.subprocess, 'run',
            side_effect=[subprocess.CompletedProcess([],0,stdout='[]'), subprocess.CompletedProcess([],1), subprocess.CompletedProcess([],0)]) as run:
            self.assertEqual(m.install('example.plugin', 'https://github.com/user/example'), 1)
            fetch.assert_called_once()
            self.assertEqual(run.call_args_list[1].args[0], ['omarchy','plugin','add','https://github.com/user/example.git','--enable'])
            self.assertNotIn('shell',run.call_args_list[1].kwargs)
