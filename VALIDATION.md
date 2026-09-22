# Omaplug validation

Verified locally on September 7, 2026. This records the checks actually performed, not a guarantee of upstream compatibility.

## Automated and data checks

- Confirmation update: 34 Python tests passed. No and Escape never invoke removal; Yes revalidates eligibility before invoking the native command. A harmless terminal preview visually verified Omarchy's themed Gum Yes/No prompt with No selected by default. No software was removed.

- Removal controls: 31 Python tests passed, including critical dependency providers, wrapped pacman metadata, action-time protection, identifier validation, native confirmation flags, bundled plugin protection, and preservation of locally modified plugin repositories. No real package or plugin was removed during testing.

- September 9 compatibility fix: all 24 Python tests and the JavaScript model checks passed. Omarchy's native validator passed. After reloading the corrected service, it reported 1,501 packages, 45 plugins, and 226 history entries with no source errors. Collection uses native commands instead of the removed registry `inBar` method.

- 21 Python tests passed, including state recovery, partial log lines, rotation, same-second transactions, plugin revisions, baseline handling, and uncertain registry snapshots. Five storage tests cover XDG defaults, legacy history migration, private permissions, existing-destination preservation, corrupt legacy state, and fresh installations.
- Omarchy's native plugin validator passed for version 1.0.1. Runtime history now defaults to `~/.local/state/omarchy/omaplug/history.sqlite3` and honors `XDG_STATE_HOME`.
- JavaScript model checks passed with 10,000 packages, including combined search/filter behavior and empty results.
- Every one of the 1,495 installed package names and versions matched `pacman -Q` exactly.
- A fresh collector imported 215 package transaction groups. Repeating collection produced no duplicates.
- One local timing sample measured 0.376 seconds for fresh collection and 0.034 seconds for an unchanged collection. These are local measurements, not performance guarantees.
- The installed service reported 1,495 packages, 45 plugins, and 217 history entries with no source errors after the final history rebuild. The two additional entries recorded a new user plugin and a bundled plugin becoming disabled during development.
- The monitor continued refreshing with its panel closed and survived shell restarts without losing its plugin baseline.
- The original development symlink installer was checked in 1.0.0. It was removed in 1.0.1; installation now uses only Omarchy's native plugin manager.
- Qt 6 qmllint found no syntax, import, required-property, unresolved-type, or inheritance-cycle diagnostics with the native shell import mapping. It still reports dynamic QObject property metadata warnings from the shared shell components and the Quickshell process signal type. Runtime loading and visual tests supplement this incomplete static type information.

## Visual and interaction checks

- Inspected the running package, plugin, and history tabs using real local data.
- Verified search, Ctrl+F focus, Ctrl+1 tab selection, Down, Enter to expand a package, and Escape to dismiss on the installed plugin.
- Inspected expanded transaction details with old/new versions.
- Inspected dark styling and an isolated light palette using the same shared components. The preview changed no desktop theme files.
- Inspected a 500 × 600 logical-pixel panel at the left edge. Checked right and bottom positioning numerically against the screen bounds. These checks do not cover every monitor scale or custom theme.
- Captured panel-only screenshots in `screenshots/`. Their counts reflect the inventory at capture time.

## Known limitations

During development, the tested shell sometimes retained compiled QML after a plugin rescan. Restarting the shell reliably loaded the edits. Automatic source hot reload is not claimed as passing.

The shared native Panel IPC handler registers once per output, producing the same duplicate-target warning as other native panels on this multi-monitor desktop. Bar clicks work per output; the named IPC open command uses the registered instance. Focused-monitor IPC routing is not implemented separately in Omaplug.

History is observational. Plugin changes between checks and activity while the monitor is disabled can be missed. Package history is limited by available logs; identical transactions within one timestamp can be indistinguishable. SQLite corruption is surfaced and preserved for manual recovery rather than repaired automatically.

No upstream development-branch integration or submission was performed. Publication of this standalone repository does not constitute an upstream Omarchy contribution.

## Marketplace feature — September 22, 2026

- Version 1.1.0 adds Discover, backed by the official `plugins.omarchy.org/catalog.json` feed. The live fetch loaded 3,948 entries; 3,381 met automatic-install eligibility at the time of testing.
- All 42 Python tests passed, including native command construction, rejected repository transports, manual/unavailable entries, duplicate IDs, installed-plugin blocking, repository-change checks, offline failure, and preservation of native confirmation. JavaScript inventory and Discover filter tests passed.
- Omarchy's native manifest validator and `git diff --check` passed. Qt 6 lint reported dynamic shell QObject metadata and QProcess signal-type warnings, but no syntax errors.
- The actual panel rendered Discover with the live catalog in an isolated Quickshell host. Inspected expanded installed-plugin state, including disabled installation. The running installed service loaded 3,948 entries with no inventory or marketplace errors after a shell restart.
- No third-party plugin was installed for this check. Installer invocation and cancellation were tested with subprocess mocks; a complete real install remains untested.
- Local runtime files were backed up before deployment. Existing removal and monitoring changes were preserved. This feature has not been published to GitHub or submitted to the marketplace.

## Simplified layout — September 22, 2026

- Plugins is the initial view. Main navigation is Plugins / Discover / Packages, with History reduced to an H button on the far right. Ctrl+H toggles History and returns to the previous main view; the existing Ctrl+1/2/3/4 bindings remain unchanged.
- Replaced the large inventory header and repeated result row with a compact title and one filter-adjacent count. Collapsed rows show descriptions; protection notices and technical details stay in expanded rows. Footer copy is shorter, with installation verification context next to the action.
- Verified search and filter preservation through the live preview IPC: Plugins + `audio` + Enabled returned the same one result after visiting History. Exercised Ctrl+H in the real isolated panel and confirmed History → Plugins through IPC.
- Inspected full-size Plugins and a 500 × 600 Discover layout. No clipped navigation or filters were observed. Captured `screenshots/plugins-redesigned.png`.
- All 42 Python tests, JavaScript model tests, native manifest validation, and whitespace checks passed. The installed copy was backed up and updated, preserving existing backend behavior. No publication was performed.

## Switch-row UX — September 22, 2026

- Always-visible On/Off switches invoke a separate helper which rechecks eligibility, runs native Omarchy enable/disable, and verifies the resulting registry state. No optimistic success is reported. Required components, replacement bars, and Omaplug itself are protected; pending and failed actions are shown.
- All 47 Python tests and JavaScript tests passed. Additional coverage exercises protected/missing IDs, native failures, state-confirmation failure, grouping, and On/Off filters. Native plugin validation and whitespace checks passed. Qt lint has the existing dynamic shell metadata/QProcess warnings, with no syntax errors.
- Real native integration test: created a temporary no-op service plugin, verified Off → On → Off through `set_enabled.py`, then removed the fixture and its configuration entries. Existing plugin states were not changed.
- UI interaction test: focused the actual switch in an isolated preview and used Space to toggle simulated Market Pulse state off and back on. Verified the model response through IPC. This preview never changed the real Market Pulse plugin.
- Inspected light and dark previews and a 500 × 600 layout. Saved `screenshots/plugins-ux-light.png` and `screenshots/plugins-ux-dark.png`. Palette overrides were confined to the preview process; desktop theme and font settings were unchanged.
- Local runtime deployment preserves existing files via a timestamped backup and restarts the shell. GitHub and the marketplace remain unpublished.
