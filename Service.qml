import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root
  property var shell: null
  property var pluginRegistry: null
  property var snapshot: ({ packages: [], plugins: [], history: [], errors: [] })
  property string error: ""
  property bool timedOut: false
  readonly property bool refreshing: collector.running
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("scripts/monitor.py").toString().replace(/^file:\/\//, ""))

  function refresh() {
    if (collector.running) return
    timedOut = false
    collector.running = true
    watchdog.restart()
  }

  onPluginRegistryChanged: debounce.restart()
  Connections {
    target: root.pluginRegistry
    ignoreUnknownSignals: true
    function onPluginsChanged() { debounce.restart() }
    function onScanFinished() { debounce.restart() }
  }
  Timer { id: debounce; interval: 800; onTriggered: root.refresh() }
  Timer { interval: 30000; running: true; repeat: true; onTriggered: root.refresh() }
  Timer {
    id: watchdog
    interval: 45000
    onTriggered: {
      root.timedOut = true
      root.error = "Refresh timed out. Showing the last available information."
      collector.running = false
    }
  }
  Process {
    id: collector
    command: ["python3", root.helperPath]
    stdinEnabled: true
    onStarted: write("{}\n")
    stdout: StdioCollector { id: output; waitForEnd: true }
    stderr: StdioCollector { id: errors; waitForEnd: true }
    onExited: function(exitCode) {
      watchdog.stop()
      if (root.timedOut) return
      if (exitCode !== 0) {
        root.error = errors.text.trim() || "Refresh failed. Showing the last available information."
        return
      }
      try {
        var value = JSON.parse(output.text)
        if (value.schemaVersion !== 1 || !Array.isArray(value.packages) || !Array.isArray(value.plugins))
          throw new Error("Unrecognized monitor response")
        root.snapshot = value
        root.error = ""
      } catch (exception) { root.error = String(exception) }
    }
  }
  IpcHandler {
    target: "omaplug-monitor"
    function refresh(): void { root.refresh() }
    function status(): string {
      return JSON.stringify({ refreshing: root.refreshing, error: root.error,
        checkedAt: root.snapshot.checkedAt || null,
        packages: root.snapshot.packages.length, plugins: root.snapshot.plugins.length,
        history: root.snapshot.history.length, errors: root.snapshot.errors })
    }
  }
}
