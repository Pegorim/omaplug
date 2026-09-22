import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('set_enabled', Path(__file__).parents[1] / 'scripts/set_enabled.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def item(**changes):
    return dict({'id':'user.example','enabled':False,'canDisable':True,'kinds':['service']}, **changes)


class ToggleTests(unittest.TestCase):
    def test_native_commands(self):
        self.assertEqual(m.command_for([item()], 'user.example', True), ['omarchy','plugin','enable','user.example'])
        self.assertEqual(m.command_for([item()], 'user.example', False), ['omarchy','plugin','disable','user.example'])

    def test_protected_missing_invalid_and_self(self):
        for row, plugin_id in [(item(canDisable=False),'user.example'),
                               (item(kinds=['bar']),'user.example'),
                               (item(id='mateus.omaplug'),'mateus.omaplug'),
                               (item(),'--bad'), (item(),'missing')]:
            with self.assertRaises(ValueError): m.command_for([row],plugin_id,False)

    def test_success_requires_observed_state(self):
        with patch.object(m,'inventory',side_effect=[[item()], [item(enabled=True)]]), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)):
            self.assertEqual(m.set_enabled('user.example',True), {'id':'user.example','enabled':True})

    def test_failed_native_command_does_not_report_success(self):
        with patch.object(m,'inventory',return_value=[item()]), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stdout='',stderr='permission denied')):
            with self.assertRaisesRegex(ValueError,'permission denied'): m.set_enabled('user.example',True)

    def test_unconfirmed_state_is_error(self):
        with patch.object(m,'inventory',return_value=[item()]), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)), patch.object(m.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'not confirmed'): m.set_enabled('user.example',True)
