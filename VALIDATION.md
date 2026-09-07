# Omaplug validation

Verified locally on September 7, 2026. This records the checks actually performed, not a guarantee of upstream compatibility.

## Automated and data checks

- 16 Python collector tests passed, including state recovery, partial log lines, rotation, same-second transactions, plugin revisions, baseline handling, and uncertain registry snapshots.
- JavaScript model checks passed with 10,000 packages, including combined search/filter behavior and empty results.
- Every one of the 1,495 installed package names and versions matched `pacman -Q` exactly.
- A fresh collector imported 215 package transaction groups. Repeating collection produced no duplicates.
- One local timing sample measured 0.376 seconds for fresh collection and 0.034 seconds for an unchanged collection. These are local measurements, not performance guarantees.
- The installed service reported 1,495 packages, 45 plugins, and 217 history entries with no source errors after the final history rebuild. The two additional entries recorded a new user plugin and a bundled plugin becoming disabled during development.
- The monitor continued refreshing with its panel closed and survived shell restarts without losing its plugin baseline.
- `bash -n install.sh` passed. Rerunning the installer reported that Omaplug was already enabled and retained its existing placement.
- Qt 6 qmllint found no syntax, import, required-property, unresolved-type, or inheritance-cycle diagnostics with the native shell import mapping. It still reports dynamic QObject property metadata warnings from the shared shell components and the Quickshell process signal type. Runtime loading and visual tests supplement this incomplete static type information.

## Visual and interaction checks

- Inspected the running package, plugin, and history tabs using real local data.
- Verified search, Ctrl+F focus, Ctrl+1 tab selection, Down, Enter to expand a package, and Escape to dismiss on the installed plugin.
- Inspected expanded transaction details with old/new versions.
- Inspected dark styling and an isolated light palette using the same shared components. The preview changed no desktop theme files.
- Inspected a 500 × 600 logical-pixel panel at the left edge. Checked right and bottom positioning numerically against the screen bounds. These checks do not cover every monitor scale or custom theme.
- Captured panel-only screenshots in `screenshots/`. Their counts reflect the inventory at capture time.

## Known limitations

Symlink discovery works, but the tested shell sometimes retained compiled QML after a plugin rescan. Restarting the shell reliably loaded the edits. Automatic source hot reload through this symlink is not claimed as passing.

The shared native Panel IPC handler registers once per output, producing the same duplicate-target warning as other native panels on this multi-monitor desktop. Bar clicks work per output; the named IPC open command uses the registered instance. Focused-monitor IPC routing is not implemented separately in Omaplug.

History is observational. Plugin changes between checks and activity while the monitor is disabled can be missed. Package history is limited by available logs; identical transactions within one timestamp can be indistinguishable. SQLite corruption is surfaced and preserved for manual recovery rather than repaired automatically.

No upstream development-branch integration or submission was performed. Publication of this standalone repository does not constitute an upstream Omarchy contribution.
