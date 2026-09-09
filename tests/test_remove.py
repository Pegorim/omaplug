import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_monitor import monitor, PACKAGE

spec = importlib.util.spec_from_file_location("remove", Path(__file__).parents[1] / "scripts/remove.py")
remove = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"monitor": monitor}):
    spec.loader.exec_module(remove)


class RemovalTests(unittest.TestCase):
    def test_critical_dependency_providers_and_bundled_apps(self):
        packages = [dict(name=name, depends=deps, provides=provides, requiredBy=[])
                    for name, deps, provides in [("omarchy", ["virtual-shell>=1"], []),
                                                 ("shell-provider", ["library"], ["virtual-shell=2"]),
                                                 ("library", [], []), ("app", [], [])]]
        with patch.object(Path, "read_text", return_value="app\n"), patch.object(Path, "glob", return_value=[]):
            monitor.package_safety(packages)
        self.assertTrue(all(p["critical"] and p["removalBlock"] for p in packages[:3]))
        self.assertTrue(packages[3]["bundled"])
        self.assertEqual(packages[3]["removalBlock"], "")

    def test_multiline_dependencies_are_preserved(self):
        item = monitor.parse_packages(PACKAGE + "Depends On      : one\n                  two>=2\nRequired By     : owner\n                  another\n", set())[0]
        self.assertEqual(item["depends"], ["one", "two>=2"])
        self.assertEqual(item["requiredBy"], ["owner", "another"])

    def test_package_command_keeps_dependency_checks_after_gum_confirmation(self):
        with patch.object(monitor, "run", return_value=PACKAGE), patch.object(monitor, "package_safety"):
            _, command = remove.removal_command("packages", "example")
        self.assertEqual(command, ["sudo", "-A", "pacman", "-R", "--noconfirm", "--", "example"])

    def test_no_or_escape_never_removes_anything(self):
        from types import SimpleNamespace
        for code in (1, 130):
            with patch.object(remove, "removal_command", return_value=({"name": "Example"}, ["remove-command"])) as check, patch.object(remove.subprocess, "run", side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=code)]) as run:
                self.assertIsNone(remove.confirm_removal("packages", "example"))
                self.assertEqual(run.call_count, 2)
                self.assertEqual(check.call_count, 1)
                self.assertEqual(run.call_args.args[0], ["gum", "confirm", "--default=false", "Remove example?"])

    def test_yes_rechecks_eligibility_before_running_removal(self):
        from types import SimpleNamespace
        with patch.object(remove, "removal_command", side_effect=[({"name": "Example"}, []), ValueError("Now protected")]) as check, patch.object(remove.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            with self.assertRaisesRegex(ValueError, "Now protected"):
                remove.confirm_removal("packages", "example")
            self.assertEqual(check.call_count, 2)
            self.assertEqual(run.call_count, 2)

    def test_yes_runs_only_revalidated_command(self):
        from types import SimpleNamespace
        with patch.object(remove, "removal_command", return_value=({"name": "Example"}, ["native-removal"])) as check, patch.object(remove.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(remove.confirm_removal("plugins", "user.example").returncode, 0)
            self.assertEqual(check.call_count, 2)
            self.assertEqual(run.call_count, 3)
            self.assertEqual(run.call_args.args[0], ["native-removal"])

    def test_critical_package_blocked_at_action_time(self):
        def protect(items):
            items[0]["removalBlock"] = "Critical component"
        with patch.object(monitor, "run", return_value=PACKAGE), patch.object(monitor, "package_safety", side_effect=protect):
            with self.assertRaisesRegex(ValueError, "Critical"):
                remove.removal_command("packages", "example")

    def test_bundled_and_required_plugins_are_protected(self):
        items = [{"id": "omarchy.test", "name": "Test", "version": "1", "path": "/usr/share/omarchy/shell/plugins/test", "enabled": True, "kinds": [], "firstParty": True},
                 {"id": "user.test", "name": "Test", "version": "1", "path": "/nonexistent", "enabled": True, "kinds": [], "canDisable": False}]
        normalized = monitor.normalize_plugins(items)
        self.assertTrue(all(item["removalBlock"] for item in normalized))
        self.assertTrue(normalized[0]["bundled"])
        self.assertTrue(normalized[1]["critical"])

    def test_invalid_identifiers_never_run_commands(self):
        with patch.object(monitor, "run") as runner:
            for name in ("--noconfirm", "../base", "app;reboot", "$(reboot)"):
                with self.assertRaises(ValueError):
                    remove.removal_command("packages", name)
            runner.assert_not_called()

    def test_plugin_local_changes_block_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            target = home / ".config/omarchy/plugins/user.test"
            (target / ".git").mkdir(parents=True)
            item = {"id": "user.test", "name": "Test", "version": "1", "path": str(target), "enabled": True, "kinds": []}
            with patch.object(Path, "home", return_value=home), patch.object(monitor, "read_plugins", return_value=[item]), patch.object(monitor, "run", side_effect=["abc", " M Panel.qml"]):
                with self.assertRaisesRegex(ValueError, "local changes"):
                    remove.removal_command("plugins", "user.test")
