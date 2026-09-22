pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "mateus.omaplug"
  ipcTarget: "mateus.omaplug"
  readonly property var monitor: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
  readonly property var snapshot: monitor ? monitor.snapshot : ({ packages: [], plugins: [], history: [], errors: [] })
  readonly property var marketplace: monitor ? monitor.marketplace : ({ plugins: [], checkedAt: null })
  readonly property bool busy: monitor && (tab === "discover" ? monitor.loadingMarketplace : monitor.refreshing)
  readonly property color foreground: Color.popups.text
  readonly property color muted: Qt.alpha(foreground, 0.72)
  property string tab: "plugins"
  property string previousTab: "plugins"
  property var viewState: ({})
  property bool switchingTab: false
  property alias searchText: search.text
  property string filter: "All"
  property string expandedId: ""
  property var visibleRows: []
  readonly property var filters: tab === "packages" ? ["All", "Explicit", "Dependencies", "Foreign"]
    : tab === "plugins" ? ["All", "Enabled", "Disabled", "User"]
    : tab === "discover" ? ["All", "Installable", "Installed", "Verified"] : ["All", "Packages", "Plugins"]
  readonly property string issue: !monitor ? "Connecting to the software monitor…"
    : tab === "discover" ? monitor.marketplaceError : monitor.error || (snapshot.errors || []).map(function(e) { return e.message }).join("\n")

  function selectTab(value) {
    if (value === tab) return
    viewState[tab] = { query: search.text, filter: filter, expanded: expandedId, index: list.currentIndex }
    if (tab !== "history") previousTab = tab
    switchingTab = true
    tab = value
    var saved = viewState[value] || { query: "", filter: "All", expanded: "", index: 0 }
    filter = saved.filter
    search.text = saved.query
    expandedId = saved.expanded
    switchingTab = false
    refreshRows()
    list.currentIndex = Math.min(saved.index, visibleRows.length - 1)
    list.positionViewAtIndex(Math.max(0, list.currentIndex), ListView.Contain)
    search.forceActiveFocus()
  }
  function installItem(item) {
    if (!item.installable || item.installed) return
    var helper = decodeURIComponent(Qt.resolvedUrl("scripts/marketplace.py").toString().replace(/^file:\/\//, ""))
    Quickshell.execDetached(["omarchy", "launch", "terminal", "python3", helper, "install", item.id, item.repo])
    root.close()
  }
  function refreshCurrent() {
    if (!monitor) return
    if (tab === "discover") monitor.loadMarketplace(true)
    else monitor.refresh()
  }
  function removeItem(item) {
    if (item.removalBlock === undefined || item.removalBlock) return
    var helper = decodeURIComponent(Qt.resolvedUrl("scripts/remove.py").toString().replace(/^file:\/\//, ""))
    Quickshell.execDetached(["omarchy", "launch", "terminal", "python3", helper, tab, item.id])
    root.close()
  }
  function refreshRows() {
    if (!search || !list || switchingTab) return
    var source = tab === "discover" ? { discover: Model.discover(marketplace, snapshot.plugins) } : snapshot
    var next = Model.rows(source, tab, filter, search.text)
    // A freshness-only update must not reset the list or its scroll position.
    if (JSON.stringify(next) !== JSON.stringify(visibleRows)) visibleRows = next
  }
  onSnapshotChanged: refreshRows()
  onMarketplaceChanged: refreshRows()
  onTabChanged: { refreshRows(); if (tab === "discover" && monitor) monitor.loadMarketplace(false) }
  onFilterChanged: refreshRows()
  Component.onCompleted: refreshRows()
  function activateRow() {
    if (list.currentIndex < 0 || list.currentIndex >= visibleRows.length) return
    var id = visibleRows[list.currentIndex].id
    expandedId = expandedId === id ? "" : id
  }
  function moveRow(delta) {
    list.currentIndex = Math.max(0, Math.min(visibleRows.length - 1, list.currentIndex + delta))
    list.positionViewAtIndex(list.currentIndex, ListView.Contain)
    list.forceActiveFocus()
  }
  onVisibleRowsChanged: { list.currentIndex = Math.min(Math.max(0, list.currentIndex), visibleRows.length - 1) }
  onOpenedChanged: if (opened) {
    if (monitor) { monitor.refresh(); if (tab === "discover") monitor.loadMarketplace(false) }
    Qt.callLater(function() { search.forceActiveFocus() })
  }
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰏖"
    tooltipText: "Omaplug\n" + root.snapshot.packages.length + " packages · " + root.snapshot.plugins.length + " plugins"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
      else if (buttonCode === Qt.MiddleButton && root.monitor) root.monitor.refresh()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.opened
    focusTarget: search
    contentWidth: panel.fittedContentWidth(Style.space(620))
    contentHeight: panel.cappedContentHeight(Style.space(640))

    ColumnLayout {
      anchors.fill: parent
      spacing: Style.space(10)
      Keys.onEscapePressed: root.close()
      Keys.onPressed: function(event) {
        if (event.modifiers & Qt.ControlModifier) {
          if (event.key === Qt.Key_F) { search.forceActiveFocus(); event.accepted = true }
          else if (event.key === Qt.Key_H) { root.selectTab(root.tab === "history" ? root.previousTab : "history"); event.accepted = true }
          else if (event.key >= Qt.Key_1 && event.key <= Qt.Key_4) {
            root.selectTab(["packages", "plugins", "history", "discover"][event.key - Qt.Key_1]); event.accepted = true
          }
        }
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(10)
        Text {
          text: "󰏖"
          color: root.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.icon
        }
        Text {
          Layout.fillWidth: true
          text: "Omaplug"
          color: root.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.bold: true
        }
        Button {
          iconText: "󰑐"
          tooltipText: root.tab === "discover" ? "Refresh marketplace" : "Refresh installed software"
          Accessible.name: tooltipText
          focusable: true
          iconSpinning: root.busy
          enabled: root.monitor && !root.busy
          onClicked: root.refreshCurrent()
        }
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(4)
        Repeater {
          model: ["Plugins", "Discover", "Packages"]
          Button {
            required property string modelData
            Layout.fillWidth: true
            text: modelData
            foreground: root.foreground
            selected: root.tab === modelData.toLowerCase()
            focusable: true
            onClicked: root.selectTab(modelData.toLowerCase())
          }
        }
        Button {
          text: "H"
          tooltipText: root.tab === "history" ? "Back to " + root.previousTab + " · Ctrl+H" : "History · Ctrl+H"
          Accessible.name: "History"
          Layout.preferredWidth: implicitHeight
          horizontalPadding: Style.space(8)
          foreground: root.foreground
          selected: root.tab === "history"
          focusable: true
          onClicked: root.selectTab(root.tab === "history" ? root.previousTab : "history")
        }
      }

      TextField {
        id: search
        Layout.fillWidth: true
        placeholderText: root.tab === "discover" ? "Search plugins, authors, or tags…" : "Search " + root.tab + "…"
        foreground: root.foreground
        onTextChanged: if (!root.switchingTab) { root.expandedId = ""; root.refreshRows(); list.currentIndex = 0 }
        Keys.onDownPressed: root.moveRow(0)
        Keys.onReturnPressed: { root.moveRow(0); root.activateRow() }
        Keys.onEscapePressed: root.close()
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(6)
        Flow {
          Layout.fillWidth: true
          Layout.preferredHeight: childrenRect.height
          spacing: Style.space(2)
          Repeater {
            model: root.filters
            Button {
              required property string modelData
              text: modelData
              fontSize: Style.font.caption
              horizontalPadding: Style.space(8)
              verticalPadding: Style.space(4)
              foreground: root.foreground
              selected: root.filter === modelData
              focusable: true
              onClicked: { root.filter = modelData; root.expandedId = ""; list.currentIndex = 0 }
            }
          }
        }
        Text {
          text: root.busy ? "Loading…" : root.visibleRows.length.toLocaleString(Qt.locale(), "f", 0)
          color: root.muted
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          Accessible.name: root.visibleRows.length + " results"
        }
      }

      Text {
        Layout.fillWidth: true
        visible: root.issue !== ""
        text: root.issue
        textFormat: Text.PlainText
        color: root.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        wrapMode: Text.Wrap
        maximumLineCount: 3
        elide: Text.ElideRight
      }

      PanelSeparator { Layout.fillWidth: true; foreground: root.foreground }

      ListView {
        id: list
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: Style.space(60)
        clip: true
        spacing: Style.space(3)
        model: root.visibleRows
        reuseItems: true
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: false
        QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
        Keys.onDownPressed: root.moveRow(1)
        Keys.onUpPressed: root.moveRow(-1)
        Keys.onReturnPressed: root.activateRow()
        Keys.onEnterPressed: root.activateRow()
        Keys.onSpacePressed: root.activateRow()
        Keys.onEscapePressed: root.close()

        delegate: BorderSurface {
          id: entry
          required property var modelData
          required property int index
          readonly property bool expanded: root.expandedId === modelData.id
          readonly property bool selected: list.currentIndex === index && list.activeFocus
          width: list.width - Style.space(12)
          height: contents.implicitHeight + Style.space(20)
          color: selected || expanded ? Style.selectedFillFor(root.foreground, Color.accent)
            : hit.containsMouse ? Style.hoverFillFor(root.foreground, Color.accent) : "transparent"
          borderSpec: selected ? Border.controlSpec("focus", root.foreground, Color.accent) : Border.none()
          radius: Style.cornerRadius

          Column {
            id: contents
            z: 1
            x: Style.space(10)
            y: Style.space(10)
            width: parent.width - Style.space(20)
            spacing: Style.space(5)
            RowLayout {
              width: parent.width
              spacing: Style.space(10)
              Text {
                Layout.fillWidth: true
                text: root.tab === "history" && entry.modelData.kind === "packages"
                  ? entry.modelData.changes.length + (entry.modelData.changes.length === 1 ? " package change" : " package changes") : entry.modelData.name
                textFormat: Text.PlainText
                color: root.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
                elide: Text.ElideRight
              }
              Text {
                Layout.maximumWidth: contents.width * 0.38
                text: root.tab === "packages" ? (entry.modelData.version || "")
                  : root.tab === "discover" ? (entry.modelData.installed ? "Installed" : entry.modelData.installable ? "Available" : (entry.modelData.status || ""))
                  : root.tab === "plugins" ? (entry.modelData.enabled ? "Enabled" : "Disabled")
                  : entry.modelData.kind === "plugins" ? "Plugin" : "Packages"
                textFormat: Text.PlainText
                color: root.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
              Text {
                text: entry.expanded ? "⌃" : "⌄"
                color: root.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }
            }
            Text {
              width: parent.width
              visible: !entry.expanded || root.tab === "history"
              text: Model.subtitle(entry.modelData, root.tab)
              textFormat: Text.PlainText
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
            Text {
              width: parent.width
              visible: entry.expanded
              text: visible ? Model.details(entry.modelData, root.tab) : ""
              textFormat: Text.PlainText
              color: root.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
              topPadding: Style.space(8)
            }
            Text {
              width: parent.width
              visible: entry.expanded && (root.tab === "packages" || root.tab === "plugins") && text !== ""
              text: [entry.modelData.critical ? "Critical" : "",
                entry.modelData.bundled ? "Bundled with Omarchy" : root.tab === "plugins" ? "User installed" : ""].filter(Boolean).join(" · ")
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
            }
            Text {
              width: parent.width
              visible: entry.expanded && (root.tab === "packages" || root.tab === "plugins")
              text: entry.modelData.removalBlock === undefined ? "Refresh inventory to check removal eligibility."
                : entry.modelData.removalBlock || "Opens a terminal for review and confirmation."
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
            }
            Text {
              width: parent.width
              visible: entry.expanded && root.tab === "discover" && entry.modelData.installable && !entry.modelData.installed
              text: "Installs current upstream code, not a pinned verified snapshot."
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
            }
            Row {
              visible: entry.expanded && root.tab === "discover"
              spacing: Style.space(8)
              Button {
                text: entry.modelData.installed ? "Installed" : entry.modelData.installable ? "Install…" : "Unavailable"
                enabled: entry.modelData.installable === true && !entry.modelData.installed && !root.issue
                foreground: root.foreground
                focusable: true
                bordered: true
                onClicked: root.installItem(entry.modelData)
              }
              Button {
                text: "Source ↗"
                enabled: !!entry.modelData.repo
                foreground: root.foreground
                focusable: true
                onClicked: Qt.openUrlExternally(entry.modelData.repo)
              }
            }
            Button {
              visible: entry.expanded && (root.tab === "packages" || root.tab === "plugins")
              text: entry.modelData.removalBlock ? "Protected" : "Remove…"
              enabled: entry.modelData.removalBlock !== undefined && !entry.modelData.removalBlock
              foreground: root.foreground
              focusable: true
              bordered: true
              onClicked: root.removeItem(entry.modelData)
            }
          }
          MouseArea {
            id: hit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: { list.currentIndex = entry.index; list.forceActiveFocus(); root.activateRow() }
          }
        }

        Text {
          anchors.centerIn: parent
          width: parent.width - Style.space(30)
          visible: list.count === 0
          text: root.busy ? (root.tab === "discover" ? "Loading the official marketplace…" : "Reading your installed software…")
            : search.text || root.filter !== "All" ? "No matches. Try another search or filter."
            : root.tab === "history" ? "No recorded changes yet.\nPlugin history starts with your first observation."
            : root.issue ? "Inventory is not available yet." : "Nothing to show."
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.Wrap
          color: root.muted
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }
      }

      PanelSeparator { Layout.fillWidth: true; foreground: root.foreground }
      Text {
        Layout.fillWidth: true
        text: root.tab === "discover" ? (root.issue ? "Offline · showing the last catalog" : "Official marketplace · Install opens a confirmation")
          : root.tab === "history" ? "History · Observed changes" + (root.snapshot.historyTotal > 500 ? " · Latest 500 entries" : "")
          : root.issue ? "Some information may be out of date" : "Installed on this computer"
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: root.muted
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
    }
  }
}
