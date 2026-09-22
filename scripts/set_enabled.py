#!/usr/bin/env python3
"""Change one installed plugin through Omarchy, then verify the reported state."""
import argparse
import json
import re
import subprocess
import sys
import time


def inventory():
    value = subprocess.run(['omarchy', 'plugin', 'list', '--json'], capture_output=True,
                           text=True, timeout=10, check=True)
    data = json.loads(value.stdout)
    if not isinstance(data, list):
        raise ValueError('Cannot read the plugin inventory')
    return data


def command_for(items, plugin_id, enabled):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', plugin_id):
        raise ValueError('Invalid plugin identifier')
    item = next((p for p in items if p.get('id') == plugin_id), None)
    if item is None or not isinstance(item.get('enabled'), bool):
        raise ValueError('Plugin is no longer available. Refresh and try again')
    if plugin_id == 'mateus.omaplug':
        raise ValueError('Omaplug stays on while you manage plugins')
    if item.get('canDisable') is not True or 'bar' in item.get('kinds', []):
        raise ValueError('This component is managed by the shell')
    return ['omarchy', 'plugin', 'enable' if enabled else 'disable', plugin_id]


def set_enabled(plugin_id, enabled):
    command = command_for(inventory(), plugin_id, enabled)
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or 'Omarchy could not change the plugin')
    for attempt in range(5):
        item = next((p for p in inventory() if p.get('id') == plugin_id), None)
        if item and item.get('enabled') is enabled:
            return {'id': plugin_id, 'enabled': enabled}
        if attempt < 4:
            time.sleep(0.2)
    raise ValueError('Omarchy has not confirmed the change. Refresh to check the current state')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plugin_id')
    parser.add_argument('state', choices=['on', 'off'])
    args = parser.parse_args()
    try:
        print(json.dumps(set_enabled(args.plugin_id, args.state == 'on')))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
