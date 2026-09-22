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

  property var marketplace: ({ plugins: [], checkedAt: null })
  property string marketplaceError: ""
  property bool marketplaceTimedOut: false
  readonly property bool loadingMarketplace: catalogCollector.running
  readonly property string marketplacePath: decodeURIComponent(Qt.resolvedUrl("scripts/marketplace.py").toString().replace(/^file:\/\//, ""))

  function loadMarketplace(force) {
    if (catalogCollector.running) return
    if (!force && marketplace.checkedAt && Date.now() / 1000 - marketplace.checkedAt < 900) return
    marketplaceError = ""
    marketplaceTimedOut = false
    catalogCollector.running = true
    catalogWatchdog.restart()
  }
  Timer {
    id: catalogWatchdog
    interval: 30000
    onTriggered: {
      root.marketplaceTimedOut = true
      root.marketplaceError = "Marketplace timed out. Check your connection and refresh to retry."
      catalogCollector.running = false
    }
  }
  Process {
    id: catalogCollector
    command: ["python3", root.marketplacePath, "catalog"]
    stdout: StdioCollector { id: catalogOutput; waitForEnd: true }
    stderr: StdioCollector { id: catalogErrors; waitForEnd: true }
    onExited: function(exitCode) {
      catalogWatchdog.stop()
      if (root.marketplaceTimedOut) return
      if (exitCode !== 0) {
        root.marketplaceError = catalogErrors.text.trim() || "Marketplace unavailable. Refresh to retry."
        return
      }
      try {
        var value = JSON.parse(catalogOutput.text)
        if (value.schemaVersion !== 1 || !Array.isArray(value.plugins)) throw new Error("Invalid marketplace response")
        root.marketplace = value
      } catch (exception) { root.marketplaceError = String(exception) }
    }
  }

  property string pendingPlugin: ""
  property string actionError: ""
  property bool refreshAgain: false
  readonly property string togglePath: decodeURIComponent(Qt.resolvedUrl("scripts/set_enabled.py").toString().replace(/^file:\/\//, ""))

  function setPluginEnabled(item, enabled) {
    if (pendingPlugin || item.canDisable !== true || item.id === "mateus.omaplug") return
    actionError = ""
    pendingPlugin = item.id
    toggleProcess.command = ["python3", togglePath, item.id, enabled ? "on" : "off"]
    toggleProcess.running = true
  }
  Process {
    id: toggleProcess
    stdout: StdioCollector { id: toggleOutput; waitForEnd: true }
    stderr: StdioCollector { id: toggleErrors; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.actionError = toggleErrors.text.trim() || "Could not change this plugin. Refresh and try again."
      else {
        try {
          var result = JSON.parse(toggleOutput.text)
          var next = Object.assign({}, root.snapshot)
          next.plugins = next.plugins.map(function(p) {
            return p.id === result.id ? Object.assign({}, p, {enabled: result.enabled}) : p
          })
          root.snapshot = next
        } catch (exception) { root.actionError = "Could not confirm the change. Refresh to check." }
      }
      root.pendingPlugin = ""
      root.refresh()
    }
  }

  function refresh() {
    if (collector.running) { refreshAgain = true; return }
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
      if (root.pendingPlugin) return
      if (root.refreshAgain) {
        root.refreshAgain = false
        Qt.callLater(root.refresh)
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
    function marketplaceRefresh(): void { root.loadMarketplace(true) }
    function status(): string {
      return JSON.stringify({ refreshing: root.refreshing, error: root.error,
        checkedAt: root.snapshot.checkedAt || null,
        packages: root.snapshot.packages.length, plugins: root.snapshot.plugins.length,
        history: root.snapshot.history.length, errors: root.snapshot.errors,
        marketplacePlugins: root.marketplace.plugins.length, marketplaceError: root.marketplaceError,
        loadingMarketplace: root.loadingMarketplace })
    }
  }
}
