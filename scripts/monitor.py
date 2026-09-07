#!/usr/bin/env python3
"""Read-only software collection. Only Omaplug's private state is written."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime


def run(args, empty_ok=False):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15,
                            env={**os.environ, "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"})
    if result.returncode and not (empty_ok and result.returncode == 1 and not result.stderr.strip()):
        raise RuntimeError(result.stderr.strip() or f"{args[0]} returned {result.returncode}")
    return result.stdout


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=2)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, at REAL NOT NULL, data TEXT NOT NULL)")
        db.commit()
    except BaseException:
        db.close()
        raise
    return db


def get(db, key, default=None):
    row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def put(db, key, value):
    db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, json.dumps(value)))


def event(db, item):
    db.execute("INSERT OR REPLACE INTO events VALUES (?, ?, ?)",
               (item["id"], item["at"], json.dumps(item)))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def parse_packages(text, foreign):
    packages = []
    for block in text.strip().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            match = re.match(r"^(\S[^:]*?)\s+: (.*)$", line)
            if match:
                fields[match[1].strip()] = match[2].strip()
        if not fields.get("Name") or not fields.get("Version"):
            raise ValueError("Incomplete pacman package information")
        packages.append({"id": fields["Name"], "name": fields["Name"],
                         "version": fields["Version"], "description": fields.get("Description", ""),
                         "size": fields.get("Installed Size", "Unknown"),
                         "explicit": fields.get("Install Reason") == "Explicitly installed",
                         "origin": "Foreign" if fields["Name"] in foreign else "Repository",
                         "installedAt": fields.get("Install Date", "Unknown"),
                         "architecture": fields.get("Architecture", "")})
    return sorted(packages, key=lambda item: item["name"].lower())


def signature(dbpath):
    """Stat local metadata, without repeatedly asking pacman to format the inventory."""
    paths = sorted((dbpath / "local").glob("*/desc")) + sorted((dbpath / "sync").glob("*.db"))
    if not (dbpath / "local").is_dir():
        raise RuntimeError("Pacman local database is unavailable")
    return digest([(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths])


def collect_packages(db, dbpath):
    if (dbpath / "db.lck").exists():
        raise RuntimeError("Package transaction in progress; showing the last inventory")
    stamp = signature(dbpath)
    if get(db, "packageSignature") == stamp:
        return
    foreign = set(run(["pacman", "-Qmq"], empty_ok=True).splitlines())
    packages = parse_packages(run(["pacman", "-Qi"]), foreign)
    if stamp != signature(dbpath) or (dbpath / "db.lck").exists():
        raise RuntimeError("Package database changed during collection; retrying next refresh")
    put(db, "packages", packages)
    put(db, "packageSignature", stamp)


LOG = re.compile(r"^\[([^]]+)\] \[ALPM\] (.*)$")
CHANGE = re.compile(r"^(installed|removed|upgraded|downgraded|reinstalled) (\S+) \((.*)\)$")


def parse_time(value):
    return datetime.fromisoformat(value).timestamp()


def save_transaction(db, pending, complete):
    if not pending or not pending["changes"]:
        return
    existing = db.execute("SELECT data FROM events WHERE id=?", (pending["id"],)).fetchone()
    if existing and json.loads(existing[0])["changes"][0] != pending["changes"][0]:
        # Pacman timestamps have second precision; separate fast transactions
        # can start at the same time. Keep stable IDs when replaying rotated logs.
        pending["id"] += ":" + digest(pending["changes"][0])
    event(db, {"id": pending["id"], "at": pending["at"], "kind": "packages",
               "name": "Package transaction", "complete": complete,
               "changes": pending["changes"]})


def consume_lines(db, lines, pending=None):
    for line in lines:
        match = LOG.match(line)
        if not match:
            continue
        timestamp, message = match.groups()
        try:
            at = parse_time(timestamp)
        except ValueError:
            continue
        if message == "transaction started":
            save_transaction(db, pending, False)
            pending = {"id": "pacman:" + digest(line), "at": at, "changes": []}
        elif message == "transaction completed":
            save_transaction(db, pending, True)
            pending = None
        else:
            change = CHANGE.match(message)
            if not change:
                continue
            action, name, versions = change.groups()
            old, new = (versions.split(" -> ", 1) if " -> " in versions else
                        (versions, "") if action == "removed" else ("", versions))
            if pending is None:
                pending = {"id": "pacman:" + digest(line), "at": at, "changes": []}
            pending["changes"].append({"name": name, "action": action, "old": old, "new": new})
    save_transaction(db, pending, False)
    return pending


def collect_log(db, path):
    checkpoint = get(db, "logCheckpoint", {})
    with path.open("rb") as stream:
        stat = os.fstat(stream.fileno())
        identity = [stat.st_dev, stat.st_ino]
        offset = checkpoint.get("offset", 0)
        same = checkpoint.get("identity") == identity and stat.st_size >= offset
        if same and offset:
            stream.seek(max(0, offset - 128))
            same = digest(stream.read(min(128, offset)).hex()) == checkpoint.get("anchor")
        if not same:
            offset = 0
        stream.seek(offset)
        raw = stream.read()
        # Do not checkpoint a partially written line.
        complete = raw[:raw.rfind(b"\n") + 1]
        pending = consume_lines(db, complete.decode("utf-8", errors="replace").splitlines(),
                                checkpoint.get("pending") if same else None)
        offset += len(complete)
        stream.seek(max(0, offset - 128))
        anchor = digest(stream.read(min(128, offset)).hex())
    put(db, "logCheckpoint", {"identity": identity, "offset": offset, "anchor": anchor, "pending": pending})
    if checkpoint and not same:
        put(db, "logNotice", "Package log rotated or was replaced. Previously recorded history is retained; gaps may remain.")


def normalize_plugins(items):
    if not isinstance(items, list) or not items:
        raise ValueError("Shell registry is not ready")
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict) or not all(key in item for key in ("id", "name", "version", "path", "enabled", "kinds")):
            raise ValueError("Incomplete shell registry snapshot")
        if item["id"] in seen or not isinstance(item["enabled"], bool):
            raise ValueError("Invalid shell registry snapshot")
        seen.add(item["id"])
        entry = dict(item)
        entry["revision"] = ""
        if not entry.get("firstParty") and (Path(entry["path"]) / ".git").exists():
            entry["revision"] = run(["git", "-C", entry["path"], "rev-parse", "--verify", "--quiet", "HEAD"], empty_ok=True).strip()
        result.append(entry)
    return sorted(result, key=lambda item: item["name"].lower())


def collect_plugins(db, items, now):
    current = normalize_plugins(items)
    old = get(db, "plugins")
    previous = {item["id"]: item for item in old or []}
    present = {item["id"]: item for item in current}
    # A disappeared registry entry with files still present is not proof of removal.
    for key in previous.keys() - present.keys():
        if Path(previous[key]["path"]).exists():
            raise ValueError("A plugin is missing from the registry but its files remain. Waiting for a valid scan.")
    if old is not None:
        for key in sorted(previous.keys() | present.keys()):
            before, after = previous.get(key), present.get(key)
            changes = []
            if before is None:
                changes = [{"name": after["name"], "action": "added", "old": "", "new": after["version"]}]
            elif after is None:
                changes = [{"name": before["name"], "action": "removed", "old": before["version"], "new": ""}]
            else:
                for field, action in (("version", "version changed"), ("revision", "revision changed"), ("enabled", "state changed")):
                    if before.get(field) != after.get(field):
                        left, right = before.get(field, ""), after.get(field, "")
                        if field == "enabled":
                            left, right = ("Enabled" if left else "Disabled"), ("Enabled" if right else "Disabled")
                        if field == "revision":
                            left, right = left[:12], right[:12]
                        changes.append({"name": after["name"], "action": action, "old": left, "new": right})
            if changes:
                event(db, {"id": "plugin:" + digest([key, now, changes]), "at": now,
                           "kind": "plugins", "name": (after or before)["name"],
                           "complete": True, "changes": changes})
    else:
        put(db, "baselineAt", now)
    put(db, "plugins", current)


def source(db, name, callback, now, errors):
    db.execute("SAVEPOINT collect_source")
    try:
        callback()
        put(db, name + "CheckedAt", now)
        db.execute("RELEASE collect_source")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        db.execute("ROLLBACK TO collect_source")
        db.execute("RELEASE collect_source")
        errors.append({"source": name, "message": str(error)})


def collect(db, plugins, now=None):
    now = now or time.time()
    errors = []
    db.execute("BEGIN IMMEDIATE")
    try:
        last = get(db, "lastObservedAt")
        if last and now - last > 120:
            put(db, "lastGap", {"from": last, "to": now})
        def packages():
            collect_packages(db, Path(run(["pacman-conf", "DBPath"]).strip()))
        def history():
            collect_log(db, Path(run(["pacman-conf", "LogFile"]).strip()))
        source(db, "packages", packages, now, errors)
        source(db, "history", history, now, errors)
        source(db, "plugins", lambda: collect_plugins(db, plugins, now), now, errors)
        put(db, "lastObservedAt", now)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    total = db.execute("SELECT count(*) FROM events").fetchone()[0]
    return {"schemaVersion": 1, "checkedAt": now, "packages": get(db, "packages", []),
            "plugins": get(db, "plugins", []),
            "history": [json.loads(row[0]) for row in db.execute("SELECT data FROM events ORDER BY at DESC, id DESC LIMIT 500")],
            "historyTotal": total, "baselineAt": get(db, "baselineAt"),
            "lastGap": get(db, "lastGap"), "logNotice": get(db, "logNotice", ""),
            "sources": {key: {"checkedAt": get(db, key + "CheckedAt"),
                              "stale": any(error["source"] == key for error in errors)}
                        for key in ("packages", "plugins", "history")}, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "omaplug")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        payload = json.loads(sys.stdin.readline())
        with connect(args.state_dir / "history.sqlite3") as db:
            print(json.dumps(collect(db, payload.get("plugins")), separators=(",", ":")))
    except (OSError, ValueError, sqlite3.DatabaseError) as error:
        print(f"Omaplug could not read its state: {error}. Existing state has been preserved.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
