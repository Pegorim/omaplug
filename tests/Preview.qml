import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import "plugin" as Omaplug

// Isolated visual harness. No real shell services or desktop theme changes.
ShellRoot {
  id: harness
  FileView { id: data; path: Qt.resolvedUrl("snapshot.json"); blockLoading: true }
  FileView { id: catalog; path: Qt.resolvedUrl("catalog.json"); blockLoading: true }
  Item {
    id: monitor
    property var snapshot: JSON.parse(data.text())
    property string error: ""
    property bool refreshing: false
    property var marketplace: JSON.parse(catalog.text())
    property string marketplaceError: ""
    property bool loadingMarketplace: false
    function loadMarketplace(force) {}
    function refresh() {}
  }
  QtObject {
    id: host
    function serviceFor(id) { return monitor }
  }
  QtObject {
    id: fakeBar
    property var shell: host
    property color barForeground: Color.foreground
    property color foreground: Color.foreground
    property color urgent: Color.urgent
    property string fontFamily: Style.font.family
    property bool foregroundAnimationEnabled: false
    property string position: Quickshell.env("OMAPLUG_PREVIEW_POSITION") || "top"
    property bool vertical: position === "left" || position === "right"
    property int barSize: 35
    property var activePopout: null
    property var clickTargets: []
    function requestPopout(owner) { activePopout = owner }
    function releasePopout(owner) { activePopout = null }
    function registerClickTarget(target) {}
    function unregisterClickTarget(target) {}
    function hideTooltip(target) {}
    function showTooltip(target, text) {}
  }
  PanelWindow {
    id: anchor
    screen: Quickshell.screens[0]
    anchors.top: fakeBar.position !== "bottom"
    anchors.bottom: fakeBar.position === "bottom" || fakeBar.vertical
    anchors.left: fakeBar.position !== "right"
    anchors.right: fakeBar.position === "right" || !fakeBar.vertical
    implicitHeight: 35
    implicitWidth: 35
    exclusionMode: ExclusionMode.Ignore
    color: Color.background
    Omaplug.Panel {
      id: preview
      bar: fakeBar
      manageIpc: false
      anchors.centerIn: parent
    }
  }
  Timer {
    interval: 500
    running: true
    onTriggered: {
      if (Quickshell.env("OMAPLUG_PREVIEW_THEME") === "light") {
        Color.foreground = "#343b58"
        Color.background = "#e1e2e7"
        Color.accent = "#34548a"
        Style.styleOverrides = ({})
        Color.shellValues = ({"popups.background": "#e1e2e7", "popups.text": "#343b58", "popups.border": "#34548a"})
      }
      preview.selectTab(Quickshell.env("OMAPLUG_PREVIEW_TAB") || "packages")
      preview.open()
    }
  }
  IpcHandler {
    target: "preview"
    function geometry(): string {
      for (var i = 0; i < preview.data.length; i++) {
        var item = preview.data[i]
        if ("cardOrigin" in item) return JSON.stringify({ x: item.cardOrigin.x, y: item.cardOrigin.y,
          width: item.contentWidth, height: item.contentHeight, screen: item.screen.name,
          rows: preview.visibleRows.length, tab: preview.tab })
      }
      return "{}"
    }
    function light(): void {
      Color.foreground = "#343b58"
      Color.background = "#e1e2e7"
      Color.accent = "#34548a"
      Style.styleOverrides = ({})
      Color.shellValues = ({"popups.background": "#e1e2e7", "popups.text": "#343b58", "popups.border": "#34548a"})
    }
    function position(value: string): void { fakeBar.position = value }
    function size(width: int, height: int): void {
      for (var i = 0; i < preview.data.length; i++) {
        var item = preview.data[i]
        if ("cardOrigin" in item) { item.contentWidth = width; item.contentHeight = height }
      }
    }
    function query(value: string): void { preview.searchText = value }
    function state(): string {
      return JSON.stringify({tab: preview.tab, query: preview.searchText,
        filter: preview.filter, expanded: preview.expandedId, rows: preview.visibleRows.length})
    }
    function filter(value: string): void { preview.filter = value }
    function tab(value: string): void { preview.selectTab(value); preview.open() }
    function expand(): void { preview.moveRow(0); preview.activateRow() }
    function inspect(kind: string, id: string): void {
      preview.selectTab(kind)
      preview.refreshRows()
      preview.visibleRows = preview.visibleRows.filter(function(item) { return item.id === id })
      preview.expandedId = id
      preview.open()
    }
    function close(): void { Quickshell.quit() }
  }
}
