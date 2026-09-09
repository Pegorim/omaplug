#!/usr/bin/env python3
"""Recheck removal eligibility, then hand off to an interactive native command."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import monitor


def removal_command(kind, name):
    if not re.fullmatch(r"[A-Za-z0-9@_+][A-Za-z0-9@_.+-]*", name) or ".." in name:
        raise ValueError("Invalid software identifier")
    if kind == "packages":
        packages = monitor.parse_packages(monitor.run(["pacman", "-Qi"]), set())
        monitor.package_safety(packages)
        item = next((item for item in packages if item["name"] == name), None)
        command = ["sudo", "-A", "pacman", "-R", "--noconfirm", "--", name]
    else:
        items = monitor.normalize_plugins(monitor.read_plugins())
        item = next((item for item in items if item["id"] == name), None)
        command = ["omarchy", "plugin", "remove", name, "--yes"]
        if item:
            target = Path.home() / ".config/omarchy/plugins" / name
            if Path(item["path"]).absolute() != target or target.is_symlink():
                raise ValueError("Only regular installations in Omarchy's plugin folder can be removed here")
            if (target / ".git").exists() and monitor.run(["git", "-C", str(target), "status", "--porcelain"]).strip():
                raise ValueError("This plugin has local changes. Save them before removing it")
    if item is None:
        raise ValueError("This item is no longer installed")
    if item.get("removalBlock"):
        raise ValueError(item["removalBlock"])
    return item, command


def confirm_removal(kind, name):
    item, _ = removal_command(kind, name)
    detail = "Bundled with Omarchy." if item.get("bundled") else "Installed on this computer."
    summary = subprocess.run(["gum", "style", "--border", "normal", "--padding", "1 2",
                              f"Remove {item['name']}?", "", detail,
                              "The selected " + ("package" if kind == "packages" else "plugin") + " will be removed."])
    if summary.returncode != 0:
        return None
    answer = subprocess.run(["gum", "confirm", "--default=false", f"Remove {name}?"])
    if answer.returncode != 0:
        return None
    # The user may leave the prompt open while the installed inventory changes.
    _, command = removal_command(kind, name)
    env = {**os.environ, "SUDO_ASKPASS": str(Path.home() / ".local/bin/omarchy-askpass")}
    return subprocess.run(command, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["packages", "plugins"])
    parser.add_argument("name")
    args = parser.parse_args()
    try:
        result = confirm_removal(args.kind, args.name)
        if result is None:
            print("Removal cancelled.")
            return
        print("\nRemoval completed." if result.returncode == 0 else "\nRemoval cancelled or failed. Review the output above.")
        subprocess.run(["omarchy-shell", "omaplug-monitor", "refresh"], timeout=5, capture_output=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"\nCannot remove: {error}")
    input("\nPress Enter to close.")


if __name__ == "__main__":
    main()
