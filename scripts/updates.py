#!/usr/bin/env python3
"""On-demand update checks and native, interactive update handoff."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

STATE = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'omarchy/omaplug'
CACHE = STATE / 'updates.json'
TTL = 900


def run(args, timeout=30, accepted=(0,), **kwargs):
    env = dict(os.environ, LC_ALL='C', GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -oBatchMode=yes')
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env, **kwargs)
    if result.returncode not in accepted or (result.returncode == 1 and result.stderr.strip()):
        raise RuntimeError(result.stderr.strip() or f'{args[0]} check failed ({result.returncode})')
    return result.stdout.strip()


def result(items=None, **extra):
    return dict(state='ok', items=items or [], checkedAt=int(time.time()), **extra)


def guarded(fn):
    try:
        return fn()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        return dict(state='error', items=[], error=str(error), checkedAt=None)


def parse_updates(text, source):
    items = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 4 or fields[2] != '->':
            raise ValueError('Unrecognized package update response')
        items.append(dict(id=fields[0], old=fields[1], new=fields[3], source=source))
    return items


def repositories():
    # checkupdates uses its own temporary sync database, never pacman -Sy.
    return result(parse_updates(run(['checkupdates', '--nocolor'], timeout=90, accepted=(0, 2)), 'Repository'))


def aur():
    foreign = run(['pacman', '-Qm'], accepted=(0, 1))
    installed = dict(line.split(maxsplit=1) for line in foreign.splitlines())
    available = {}
    names = list(installed)
    for start in range(0, len(names), 100):
        query = urllib.parse.urlencode([('arg[]', name) for name in names[start:start + 100]])
        request = urllib.request.Request('https://aur.archlinux.org/rpc/v5/info?' + query,
                                         headers={'User-Agent': 'Omaplug/1.2'})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read(4 * 1024 * 1024))
        if data.get('type') != 'multiinfo' or not isinstance(data.get('results'), list):
            raise ValueError('AUR returned an invalid response')
        available.update({p['Name']: p['Version'] for p in data['results']})
    items = [dict(id=name, old=installed[name], new=version, source='AUR')
             for name, version in available.items() if name in installed
             and int(run(['vercmp', version, installed[name]])) > 0]
    return result(items, unknown=sorted(set(installed) - set(available)),
                  note='AUR release versions only; VCS rebuilds are not checked.')


def omarchy_status(repo):
    version = run(['omarchy', 'version'])
    path = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy'))
    if path != Path('/usr/share/omarchy'):
        run(['git', '-C', str(path), 'fetch', '--quiet'], timeout=25)
        behind = int(run(['git', '-C', str(path), 'rev-list', '--count', 'HEAD..@{upstream}']))
        return result([dict(new=f'{behind} upstream commits')] if behind else [], version=version)
    installed = run(['pacman', '-Qq', 'omarchy-dev', 'omarchy'], accepted=(0, 1)).splitlines()
    if not installed:
        raise ValueError('Installed Omarchy package could not be identified')
    if repo['state'] != 'ok':
        return dict(state='error', version=version, items=[], checkedAt=None, error='Repository check failed')
    return result([p for p in repo['items'] if p['id'] in installed], version=version)


def plugin_check(item):
    data = dict(id=item['id'], state='unsupported', message='Bundled with Omarchy', canUpdate=False)
    if item.get('firstParty'):
        return data
    try:
        path = Path(item['path'])
        expected = Path.home() / '.config/omarchy/plugins' / item['id']
        if path.is_symlink() or path.resolve() != expected or (path / '.git').is_symlink() or not (path / '.git').is_dir():
            return dict(data, message='Local or linked development plugin')
        git = ['git', '-C', str(path)]
        if run(git + ['status', '--porcelain']):
            return dict(data, state='modified', message='Local changes; update blocked')
        remote = run(git + ['remote', 'get-url', 'origin'])
        if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', remote):
            return dict(data, message='Only HTTPS GitHub origins are checked')
        current = run(git + ['rev-parse', 'HEAD'])
        # Fetch changes Git metadata only, not installed source or working files.
        run(git + ['fetch', '--quiet', 'origin', 'HEAD'], timeout=25)
        target = run(git + ['rev-parse', 'FETCH_HEAD'])
        data.update(current=current, target=target)
        if current == target:
            return dict(data, state='current', message='Up to date')
        ancestor = subprocess.run(git + ['merge-base', '--is-ancestor', current, target], timeout=10).returncode
        if ancestor != 0:
            return dict(data, state='diverged', message='Local history differs; update blocked')
        return dict(data, state='available', message='Update available', canUpdate=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        return dict(data, state='error', message=str(error))


def plugins():
    import monitor
    entries = monitor.read_plugins()
    with ThreadPoolExecutor(max_workers=4) as pool:
        return result(list(pool.map(plugin_check, entries)))


def check(force=False):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / 'updates.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            cached = json.loads(CACHE.read_text())
            if not force and time.time() - cached.get('checkedAt', 0) < TTL:
                return cached
        except (OSError, ValueError):
            pass
        with ThreadPoolExecutor(max_workers=3) as pool:
            rf, af, pf = [pool.submit(guarded, fn) for fn in (repositories, aur, plugins)]
            repo, aur_data, plugin_data = rf.result(), af.result(), pf.result()
        data = dict(schemaVersion=1, checkedAt=int(time.time()), repositories=repo,
                    aur=aur_data, plugins=plugin_data, omarchy=guarded(lambda: omarchy_status(repo)))
        try:
            previous = json.loads(CACHE.read_text())
        except (OSError, ValueError):
            previous = {}
        for key in ('repositories', 'aur', 'plugins', 'omarchy'):
            if data[key]['state'] == 'error' and (previous.get(key, {}).get('checkedAt') or previous.get(key, {}).get('lastSuccess')):
                data[key]['lastSuccess'] = previous[key].get('lastSuccess', previous[key])
        temporary = CACHE.with_suffix('.tmp')
        temporary.write_text(json.dumps(data))
        temporary.chmod(0o600)
        temporary.replace(CACHE)
        return data


def update(kind, plugin_id=None):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / 'update-action.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('An Omaplug update action is already running')
        return perform_update(kind, plugin_id)


def perform_update(kind, plugin_id=None):
    if kind == 'system':
        command = ['omarchy', 'update']
    else:
        if not plugin_id or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', plugin_id) or '..' in plugin_id:
            raise ValueError('Invalid plugin ID')
        import monitor
        item = next((p for p in monitor.read_plugins() if p['id'] == plugin_id), None)
        state = plugin_check(item) if item else {}
        if not state.get('canUpdate'):
            raise ValueError(state.get('message', 'Plugin unavailable'))
        command = ['omarchy', 'plugin', 'update', plugin_id]
    try:
        return subprocess.call(command)  # Interactive native review/authentication; no --yes.
    finally:
        CACHE.unlink(missing_ok=True)
        subprocess.run(['omarchy-shell', '-q', 'omaplug-monitor', 'updatesRefresh'], timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'system', 'plugin'])
    parser.add_argument('plugin_id', nargs='?')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            print(json.dumps(check(args.force)))
            return 0
        return update(args.action, args.plugin_id)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        if sys.stdin.isatty():
            input('Press Enter to close…')
        return 1


if __name__ == '__main__':
    sys.exit(main())
