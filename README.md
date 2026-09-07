# Omaplug
`~/Work/omarchy-plugs/omaplug/README.md`

A native Omarchy panel for installed packages, shell plugins, and recent changes. Click the package icon in the bar to open it. Everything stays on your computer.

This repository contains the current **1.0.0** community plugin, including its tests, screenshots, and known limitations. It is not an official Omarchy component or an accepted upstream contribution.

![Omaplug package inventory](screenshots/packages-dark.png)

## Install

Clone the repository, then run the included installer:

```bash
mkdir -p ~/Work/omarchy-plugs
git clone https://github.com/Pegorim/omaplug.git ~/Work/omarchy-plugs/omaplug
cd ~/Work/omarchy-plugs/omaplug
bash install.sh
```

The checkout can live elsewhere; the installer links its actual location into `~/.config/omarchy/plugins/mateus.omaplug`. The original development installation remains at `/home/mateus/Work/omarchy-plugs/omaplug`.

If you already have this checkout, run `bash install.sh` from its directory instead of cloning it again.

The installer leaves an existing, different installation untouched. It preserves an already-enabled widget's position. On first enable it places Omaplug after the update indicator, or in the center section when that indicator is absent. No root access or package installation is needed.

Verified with Omarchy **4.0.2-1**, Quickshell **0.3.1-1**, Python **3.14.7**, and the native Omarchy shell components on this machine. Older Waybar-based installations are not supported. Omaplug uses Python's standard library, pacman, pacman-conf, and Git for local plugin revisions. The installer also uses Omarchy's existing jq dependency.

## Browse your software

- **Packages:** search names, descriptions, and versions. Filter by explicit packages, dependencies, or foreign packages. Expand a row for installed size and package metadata.
- **Plugins:** inspect enabled status, bundled/user origin, manifest version, local revision, and source location. This includes Omarchy shell plugins, not editor or AI extensions.
- **History:** browse grouped package transactions and detected plugin changes. Expand a transaction for individual changes and old/new versions. The panel displays the most recent 500 entries; older recorded entries remain in SQLite.

Foreign means absent from the currently available sync databases. Such packages can come from AUR or local package files. Repository classification does not prove the original installation source. Pacman's installation date describes the most recent install or upgrade, not necessarily the first install.

Search receives focus when the panel opens. Use **Down/Up** to browse results, **Enter** or **Space** to expand, **Ctrl+F** to return to search, **Ctrl+1/2/3** to switch tabs, **Tab/Shift+Tab** to move between controls, and **Escape** to close. Click Refresh, or middle-click the bar icon, for a fresh observation.

![Omaplug plugins](screenshots/plugins-dark.png)

## What history can tell you

Package history is imported from the configured pacman log. Transactions without a completion marker are explicitly marked as unconfirmed. Log rotation preserves already-recorded history, but activity in unavailable older logs cannot be recovered. Identical transactions within the same timestamp may be indistinguishable in pacman's second-resolution log.

Plugin history begins with Omaplug's first observation. Existing plugins are a baseline, not newly installed software. Changes are checked every 30 seconds while the enabled plugin's shell service runs, and when the panel opens or the registry changes. Detection times are not exact installation times. Short-lived changes between observations can be missed; disabling Omaplug or closing the desktop stops observation. A gap longer than two minutes is noted in the history footer.

The monitor does not fetch Git repositories or check available upgrades. A revision change is a change of the local Git HEAD; uncommitted source edits are not installation events. A missing registry entry whose files remain is treated as an uncertain scan, preserving the previous plugin inventory instead of claiming removal.

Source failures retain previous results and display a stale notice. Corrupt SQLite state is left intact and reported, never silently replaced. Inventory collection is read-only; only Omaplug's private history is written.

![Expanded history in an isolated light palette](screenshots/history-light.png)

## State and diagnostics

State is stored at `${XDG_STATE_HOME:-~/.local/state}/omaplug/history.sqlite3`, outside the checkout, with private file permissions. There is no separate daemon or system service. All monitors share one shell service.

```bash
omarchy-shell omaplug-monitor status
omarchy-shell omaplug-monitor refresh
omarchy-shell mateus.omaplug open
omarchy-shell mateus.omaplug close
```

The helper reads a single JSON line containing a `plugins` array from stdin, and emits a `schemaVersion: 1` JSON snapshot with `packages`, `plugins`, `history`, source freshness, and errors. The shell service supplies authoritative registry state plus manifest metadata. Helper calls are serialized, commands have timeouts, and package metadata is rescanned only when the local database signature changes.

To disable the monitor:

```bash
omarchy plugin disable mateus.omaplug
```

To remove the registration afterward, unlink `~/.config/omarchy/plugins/mateus.omaplug`, then run `omarchy-shell shell rescanPlugins`. The project and its history remain available. Delete either separately only if no longer needed.

## Development and checks

```bash
python3 -m unittest discover -s tests -v
node tests/test_model.cjs
bash -n install.sh
```

Node is only used for the model tests, not at runtime. The tests cover package parsing, transaction grouping, partial lines, rotation, repeated timestamps, replay deduplication, plugin baselines and changes, uncertain scans, source failures, database locking, state preservation, and filtering 10,000 packages.

`tests/Preview.qml` is an isolated Quickshell preview using a supplied snapshot. It supports light-palette, tab, and size/position checks without touching desktop theme settings. Run `python3 tests/preview.py` after the installed monitor has collected its first snapshot. Preview IPC is scoped to its temporary config; it is not loaded by the installed plugin.

**Source reload limitation:** discovery through the project symlink works. On the tested shell, a plugin rescan sometimes retained compiled QML from before an edit. Use `omarchy restart shell` after editing source if the panel does not update. Python helper changes take effect on the next observation. History survives shell restarts.

Visual checks covered the native dark palette, an isolated light palette, the three tabs, expanded history, keyboard search, and a narrow panel. See [VALIDATION.md](VALIDATION.md) for the precise results and remaining limitations.

The [upstream proposal draft](UPSTREAM.md) records the idea for a future Omarchy contribution. Publishing this standalone repository does not imply an upstream submission, acceptance, or release inclusion.
