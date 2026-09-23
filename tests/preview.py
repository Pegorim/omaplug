#!/usr/bin/env python3
"""Launch the real panel in an isolated Quickshell host with a saved snapshot."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

project = Path(__file__).resolve().parents[1]
shell = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "omarchy/omaplug/history.sqlite3"

with sqlite3.connect(state.as_uri() + "?mode=ro", uri=True) as db:
    values = {key: json.loads(value) for key, value in db.execute("SELECT key,value FROM state")}
    snapshot = {"packages": values.get("packages", []), "plugins": values.get("plugins", []),
                "history": [json.loads(row[0]) for row in db.execute("SELECT data FROM events ORDER BY at DESC LIMIT 500")],
                "baselineAt": values.get("baselineAt"), "errors": [],
                "sources": {key: {"checkedAt": values.get(key + "CheckedAt")} for key in ("packages", "plugins", "history")}}

with tempfile.TemporaryDirectory(prefix="omaplug-preview-") as temporary:
    root = Path(temporary)
    for name in ("Commons", "Ui"):
        (root / name).symlink_to(shell / name)
    (root / "plugin").symlink_to(project)
    (root / "shell.qml").write_text((project / "tests/Preview.qml").read_text())
    (root / "snapshot.json").write_text(json.dumps(snapshot))
    updates = os.environ.get("OMAPLUG_PREVIEW_UPDATES")
    (root / "updates.json").write_text(Path(updates).read_text() if updates else "{}")
    catalog = os.environ.get("OMAPLUG_PREVIEW_CATALOG")
    (root / "catalog.json").write_text(Path(catalog).read_text() if catalog else '{"plugins":[],"checkedAt":null}')
    print(f"Preview IPC: quickshell ipc -p {root} call preview <tab|expand|light|position|size|geometry|close>", flush=True)
    try:
        subprocess.run(["quickshell", "-p", str(root)], check=True)
    except KeyboardInterrupt:
        pass
