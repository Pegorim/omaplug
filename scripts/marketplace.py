#!/usr/bin/env python3
"""Browse the official catalog and hand approved install actions to Omarchy."""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request

CATALOG_URL = "https://plugins.omarchy.org/catalog.json"
MAX_BYTES = 32 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
REPO = re.compile(r"https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9._-]*/?\Z")


def clean(value, limit=2000):
    return "".join(c for c in str(value or "") if c.isprintable() or c == "\n")[:limit]


def repository_url(value):
    if not isinstance(value, str) or not REPO.fullmatch(value):
        return ""
    value = value.rstrip("/")
    return value[:-4] if value.endswith(".git") else value


def normalize_catalog(data):
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        raise ValueError("Invalid marketplace catalog")
    result, seen = [], set()
    for entry in data["plugins"]:
        if not isinstance(entry, dict) or not ID.fullmatch(str(entry.get("id", ""))):
            raise ValueError("Invalid marketplace plugin identifier")
        plugin_id = entry["id"]
        if plugin_id in seen:
            raise ValueError("Duplicate marketplace plugin identifier")
        seen.add(plugin_id)
        repo = repository_url(entry.get("repo"))
        bundled = entry.get("sourceType") == "builtin"
        installable = (entry.get("sourceType") == "community" and
                       entry.get("repositoryLayout") == "root-plugin" and
                       entry.get("installAvailable") is True and
                       entry.get("status") == "Available" and bool(repo))
        reason = "" if installable else (
            "Included with Omarchy; manage it in the Plugins tab." if bundled else
            clean(entry.get("installNote")) or "Installation unavailable; check the repository instructions.")
        coverage = entry.get("verificationCoverage")
        verification = ("Update unverified" if coverage == "update-unverified" else
                        "Snapshot verified" if coverage == "snapshot-verified" and
                        entry.get("verificationStatus") == "verified" else "Unverified")
        result.append({"id": plugin_id, "name": clean(entry.get("name") or plugin_id, 200),
                       "description": clean(entry.get("description")), "author": clean(entry.get("author"), 200),
                       "version": clean(entry.get("version"), 100), "category": clean(entry.get("category"), 100),
                       "tags": [clean(t, 100) for t in entry.get("tags", []) if isinstance(t, str)],
                       "repo": repo, "bundled": bundled, "installable": installable,
                       "installNote": reason, "verification": verification,
                       "status": clean(entry.get("status"), 100)})
    return {"schemaVersion": 1, "checkedAt": time.time(),
            "plugins": sorted(result, key=lambda x: (x["name"].lower(), x["id"]))}


def fetch_catalog():
    request = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "Omaplug/1.1", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if not response.url.startswith("https://plugins.omarchy.org/"):
            raise ValueError("Unexpected marketplace redirect")
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Marketplace catalog exceeds size limit")
    return normalize_catalog(json.loads(payload))


def install_command(catalog, plugin_id, expected_repo, installed):
    item = next((p for p in catalog["plugins"] if p["id"] == plugin_id), None)
    if not item or not item["installable"]:
        raise ValueError("This plugin is no longer available for automatic installation")
    if item["repo"] != expected_repo:
        raise ValueError("The repository changed. Refresh Discover and review the plugin again")
    if not isinstance(installed, list) or any(not isinstance(p, dict) or not isinstance(p.get("id"), str) for p in installed):
        raise ValueError("Cannot verify the installed plugin inventory")
    if any(p["id"] == plugin_id for p in installed):
        raise ValueError("This plugin is already installed; manage it in the Plugins tab")
    # Never evaluate installCommand or any other command supplied by the catalog.
    return ["omarchy", "plugin", "add", item["repo"] + ".git", "--enable"]


def install(plugin_id, expected_repo):
    catalog = fetch_catalog()
    inventory = subprocess.run(["omarchy", "plugin", "list", "--json"],
                               capture_output=True, text=True, timeout=15, check=True)
    command = install_command(catalog, plugin_id, expected_repo, json.loads(inventory.stdout))
    result = subprocess.run(command)  # Interactive native confirmation and placement chooser.
    try:
        subprocess.run(["omarchy-shell", "omaplug-monitor", "refresh"],
                       capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
    print("\nInstallation completed." if result.returncode == 0 else
          "\nInstallation cancelled or failed. Review the output above.")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["catalog", "install"])
    parser.add_argument("plugin_id", nargs="?")
    parser.add_argument("repo", nargs="?")
    args = parser.parse_args()
    code = 0
    try:
        if args.action == "catalog":
            print(json.dumps(fetch_catalog()))
        else:
            if not args.plugin_id or not args.repo:
                raise ValueError("A plugin ID and repository are required")
            code = install(args.plugin_id, args.repo)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Marketplace: {error}", file=sys.stderr)
        code = 1
    if args.action == "install" and sys.stdin.isatty():
        input("\nPress Enter to close.")
    return code


if __name__ == "__main__":
    sys.exit(main())
