import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("monitor", Path(__file__).parents[1] / "scripts/monitor.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

PACKAGE = """Name            : example
Version         : 2:1.0-3
Description     : An example with : punctuation
Architecture    : x86_64
Installed Size  : 20.00 MiB
Install Date    : Mon Sep  7 09:10:00 2026
Install Reason  : Explicitly installed
"""


class StateMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)
        self.legacy = self.root / "omaplug/history.sqlite3"
        self.destination = self.root / "omarchy/omaplug/history.sqlite3"

    def test_state_root_honors_xdg_and_empty_fallback(self):
        self.assertEqual(monitor.state_root(), self.root)
        with patch.dict(os.environ, {"XDG_STATE_HOME": ""}):
            self.assertEqual(monitor.state_root(), Path.home() / ".local/state")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(monitor.state_root(), Path.home() / ".local/state")

    def seed_legacy(self):
        db = monitor.connect(self.legacy)
        try:
            monitor.put(db, "baselineAt", 123)
            db.execute("INSERT INTO events VALUES (?, ?, ?)", ("saved", 123, '{"id":"saved"}'))
            db.commit()
        finally:
            db.close()

    def test_migration_preserves_baseline_events_and_original(self):
        self.seed_legacy()
        original = self.legacy.read_bytes()
        monitor.migrate_state(self.destination)
        db = monitor.connect(self.destination)
        try:
            self.assertEqual(monitor.get(db, "baselineAt"), 123)
            self.assertEqual(db.execute("SELECT id FROM events").fetchall(), [("saved",)])
        finally:
            db.close()
        self.assertEqual(self.legacy.read_bytes(), original)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_existing_destination_is_never_replaced(self):
        self.seed_legacy()
        db = monitor.connect(self.destination)
        monitor.put(db, "baselineAt", 456)
        db.commit()
        db.close()
        original = self.destination.read_bytes()
        monitor.migrate_state(self.destination)
        self.assertEqual(self.destination.read_bytes(), original)

    def test_corrupt_legacy_is_preserved_without_partial_destination(self):
        self.legacy.parent.mkdir()
        self.legacy.write_bytes(b"not a sqlite database")
        with self.assertRaises(sqlite3.DatabaseError):
            monitor.migrate_state(self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.legacy.read_bytes(), b"not a sqlite database")
        self.assertEqual(list(self.destination.parent.iterdir()), [])

    def test_fresh_install_needs_no_migration(self):
        monitor.migrate_state(self.destination)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.legacy.parent.exists())


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = monitor.connect(self.root / "history.sqlite3")
        self.addCleanup(self.db.close)

    def events(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM events ORDER BY at")]

    def line(self, text, second=0):
        return f"[2026-09-07T09:10:{second:02d}-0300] [ALPM] {text}\n"

    def plugin(self, **changes):
        return dict({"id": "test.example", "name": "Example", "version": "1.0", "enabled": True,
                     "path": str(self.root / "example"), "kinds": ["bar-widget"], "firstParty": False}, **changes)

    def test_packages_preserve_epoch_description_and_foreign_classification(self):
        row = monitor.parse_packages(PACKAGE, {"example"})[0]
        self.assertEqual(row["version"], "2:1.0-3")
        self.assertEqual(row["description"], "An example with : punctuation")
        self.assertTrue(row["explicit"])
        self.assertEqual(row["origin"], "Foreign")
        row = monitor.parse_packages(PACKAGE.replace("Explicitly installed", "Installed as a dependency for another package"), set())[0]
        self.assertFalse(row["explicit"])
        self.assertEqual(row["origin"], "Repository")

    def test_incomplete_package_output_rejected(self):
        with self.assertRaises(ValueError):
            monitor.parse_packages("Name : bad", set())

    def test_partial_log_line_and_transaction_complete_once(self):
        path = self.root / "pacman.log"
        path.write_text(self.line("transaction started") + self.line("installed example (1.0)", 1) + "[2026-")
        monitor.collect_log(self.db, path)
        self.assertFalse(self.events()[0]["complete"])
        with path.open("a") as stream:
            stream.write("09-07T09:10:02-0300] [ALPM] transaction completed\n")
        monitor.collect_log(self.db, path)
        monitor.collect_log(self.db, path)
        self.assertEqual(len(self.events()), 1)
        self.assertTrue(self.events()[0]["complete"])
        self.assertEqual(len(self.events()[0]["changes"]), 1)

    def test_rotation_retains_history_and_deduplicates_replayed_log(self):
        path = self.root / "pacman.log"
        contents = self.line("transaction started") + self.line("upgraded example (1 -> 2)", 1) + self.line("transaction completed", 2)
        path.write_text(contents)
        monitor.collect_log(self.db, path)
        path.rename(self.root / "pacman.log.1")
        path.write_text(contents + self.line("transaction started", 3) + self.line("removed other (4)", 4) + self.line("transaction completed", 5))
        monitor.collect_log(self.db, path)
        self.assertEqual(len(self.events()), 2)
        self.assertEqual(self.events()[0]["changes"][0]["old"], "1")
        self.assertIn("rotated", monitor.get(self.db, "logNotice"))

    def test_copytruncate_with_larger_replacement_detected(self):
        path = self.root / "pacman.log"
        path.write_text(self.line("transaction started") + self.line("installed a (1)", 1) + self.line("transaction completed", 2))
        monitor.collect_log(self.db, path)
        path.write_text(self.line("transaction started", 3) + self.line("installed longer-name (2)", 4) + self.line("transaction completed", 5))
        monitor.collect_log(self.db, path)
        self.assertEqual(len(self.events()), 2)

    def test_different_transactions_in_the_same_second_are_preserved(self):
        lines = [self.line("transaction started"), self.line("installed a (1)"),
                 self.line("transaction completed"), self.line("transaction started"),
                 self.line("installed b (1)"), self.line("transaction completed")]
        monitor.consume_lines(self.db, lines)
        self.assertEqual(len(self.events()), 2)

    def test_git_revision_change_is_recorded_without_a_version_bump(self):
        (self.root / "example" / ".git").mkdir(parents=True)
        with patch.object(monitor, "run", return_value="a" * 40):
            monitor.collect_plugins(self.db, [self.plugin()], 100)
        with patch.object(monitor, "run", return_value="b" * 40):
            monitor.collect_plugins(self.db, [self.plugin()], 130)
        self.assertEqual(self.events()[0]["changes"][0]["action"], "revision changed")

    def test_baseline_is_not_installation_history(self):
        monitor.collect_plugins(self.db, [self.plugin()], 100)
        monitor.collect_plugins(self.db, [self.plugin()], 130)
        self.assertEqual(self.events(), [])
        self.assertEqual(monitor.get(self.db, "baselineAt"), 100)

    def test_plugin_changes_add_remove_enable_and_version(self):
        anchor = self.plugin(id="test.anchor")
        monitor.collect_plugins(self.db, [self.plugin(), anchor], 100)
        monitor.collect_plugins(self.db, [self.plugin(enabled=False, version="2.0"), anchor], 130)
        monitor.collect_plugins(self.db, [anchor], 160)
        monitor.collect_plugins(self.db, [self.plugin(), anchor], 190)
        self.assertEqual(len(self.events()), 3)
        self.assertEqual(len(self.events()[0]["changes"]), 2)
        self.assertEqual(self.events()[1]["changes"][0]["action"], "removed")
        self.assertEqual(self.events()[2]["changes"][0]["action"], "added")

    def test_missing_registry_entry_with_files_does_not_claim_removal(self):
        (self.root / "example").mkdir()
        anchor = self.plugin(id="test.anchor", path=str(self.root / "anchor"))
        monitor.collect_plugins(self.db, [self.plugin(), anchor], 100)
        with self.assertRaises(ValueError):
            monitor.collect_plugins(self.db, [anchor], 130)
        self.assertEqual(len(monitor.get(self.db, "plugins")), 2)
        self.assertEqual(self.events(), [])

    def test_empty_registry_not_accepted_as_mass_removal(self):
        monitor.collect_plugins(self.db, [self.plugin()], 100)
        with self.assertRaises(ValueError):
            monitor.collect_plugins(self.db, [], 130)
        self.assertEqual(self.events(), [])

    def test_failed_source_preserves_snapshot_and_freshness(self):
        monitor.put(self.db, "packages", [{"name": "old"}])
        monitor.put(self.db, "packagesCheckedAt", 100)
        errors = []
        def fail():
            monitor.put(self.db, "packages", [])
            raise RuntimeError("unavailable")
        monitor.source(self.db, "packages", fail, 200, errors)
        self.assertEqual(monitor.get(self.db, "packages"), [{"name": "old"}])
        self.assertEqual(monitor.get(self.db, "packagesCheckedAt"), 100)
        self.assertEqual(errors[0]["source"], "packages")

    def test_unchanged_package_database_skips_pacman_query(self):
        (self.root / "local").mkdir()
        monitor.put(self.db, "packageSignature", monitor.signature(self.root))
        with patch.object(monitor, "run") as runner:
            monitor.collect_packages(self.db, self.root)
            runner.assert_not_called()

    def test_lock_does_not_collect_inconsistent_inventory(self):
        (self.root / "db.lck").touch()
        with self.assertRaisesRegex(RuntimeError, "in progress"):
            monitor.collect_packages(self.db, self.root)

    def test_state_survives_reopen(self):
        monitor.collect_plugins(self.db, [self.plugin()], 100)
        self.db.commit()
        other = monitor.connect(self.root / "history.sqlite3")
        self.addCleanup(other.close)
        monitor.collect_plugins(other, [self.plugin()], 130)
        self.assertEqual(other.execute("SELECT count(*) FROM events").fetchone()[0], 0)

    def test_corrupt_state_is_not_replaced(self):
        path = self.root / "broken.sqlite3"
        path.write_bytes(b"not a sqlite database")
        with self.assertRaises(sqlite3.DatabaseError):
            monitor.connect(path)
        self.assertEqual(path.read_bytes(), b"not a sqlite database")


if __name__ == "__main__":
    unittest.main()
