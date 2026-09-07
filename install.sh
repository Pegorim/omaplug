#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
plugin_dir="$HOME/.config/omarchy/plugins/mateus.omaplug"
mkdir -p -- "$(dirname -- "$plugin_dir")"
if [[ -e $plugin_dir || -L $plugin_dir ]]; then
  [[ $(readlink -f -- "$plugin_dir") == "$source_dir" ]] || {
    echo "A different installation already exists at $plugin_dir. It has been left untouched." >&2
    exit 1
  }
else
  ln -s -- "$source_dir" "$plugin_dir"
fi

omarchy-shell shell rescanPlugins
for attempt in {1..25}; do
  plugins=$(omarchy plugin list --json)
  if jq -e 'any(.[]; .id == "mateus.omaplug")' <<<"$plugins" >/dev/null; then
    if jq -e 'any(.[]; .id == "mateus.omaplug" and .enabled)' <<<"$plugins" >/dev/null; then
      echo "Omaplug is already enabled at $source_dir"
      exit 0
    fi
    if jq -e 'any(.[]; .id == "omarchy.system-update" and .enabled)' <<<"$plugins" >/dev/null; then
      omarchy plugin enable mateus.omaplug --after omarchy.system-update
    else
      omarchy plugin enable mateus.omaplug --section center
    fi
    echo "Omaplug installed from $source_dir"
    exit 0
  fi
  sleep 0.2
done
echo "Omaplug is linked, but the shell has not discovered it. Check the shell logs." >&2
exit 1
