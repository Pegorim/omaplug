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
  readonly property color foreground: Color.popups.text
  readonly property color muted: Qt.alpha(foreground, 0.72)
  property string tab: "packages"
  property string filter: "All"
  property string expandedId: ""
  property var visibleRows: []
  readonly property var filters: tab === "packages" ? ["All", "Explicit", "Dependencies", "Foreign"]
    : tab === "plugins" ? ["All", "Enabled", "Disabled", "User"] : ["All", "Packages", "Plugins"]
  readonly property string issue: !monitor ? "Connecting to the software monitor…"
    : monitor.error || (snapshot.errors || []).map(function(e) { return e.message }).join("\n")

  function selectTab(value) { tab = value; filter = "All"; search.text = ""; expandedId = ""; list.currentIndex = 0 }
  function removeItem(item) {
    if (item.removalBlock === undefined || item.removalBlock) return
    var helper = decodeURIComponent(Qt.resolvedUrl("scripts/remove.py").toString().replace(/^file:\/\//, ""))
    Quickshell.execDetached(["omarchy", "launch", "terminal", "python3", helper, tab, item.id])
    root.close()
  }
  function refreshRows() {
    if (!search || !list) return
    var next = Model.rows(snapshot, tab, filter, search.text)
    // A freshness-only update must not reset the list or its scroll position.
    if (JSON.stringify(next) !== JSON.stringify(visibleRows)) visibleRows = next
  }
  onSnapshotChanged: refreshRows()
  onTabChanged: refreshRows()
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
    if (monitor) monitor.refresh()
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
    contentHeight: panel.cappedContentHeight(Style.space(700))

    ColumnLayout {
      anchors.fill: parent
      spacing: Style.space(12)
      Keys.onEscapePressed: root.close()
      Keys.onPressed: function(event) {
        if (event.modifiers & Qt.ControlModifier) {
          if (event.key === Qt.Key_F) { search.forceActiveFocus(); event.accepted = true }
          else if (event.key >= Qt.Key_1 && event.key <= Qt.Key_3) {
            root.selectTab(["packages", "plugins", "history"][event.key - Qt.Key_1]); event.accepted = true
          }
        }
      }

      PanelHero {
        Layout.fillWidth: true
        title: "Omaplug"
        meta: root.snapshot.packages.length + " packages · " + root.snapshot.plugins.length + " plugins"
        foreground: root.foreground
        iconComponent: Component {
          Text { text: "󰏖"; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.display }
        }
        trailingControl: Component {
          Button {
            iconText: "󰑐"
            tooltipText: "Refresh software inventory"
            focusable: true
            iconSpinning: root.monitor && root.monitor.refreshing
            enabled: root.monitor && !root.monitor.refreshing
            onClicked: root.monitor.refresh()
          }
        }
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(4)
        Repeater {
          model: ["Packages", "Plugins", "History"]
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
      }

      TextField {
        id: search
        Layout.fillWidth: true
        placeholderText: "Search " + root.tab + "…"
        foreground: root.foreground
        onTextChanged: { root.expandedId = ""; root.refreshRows(); list.currentIndex = 0 }
        Keys.onDownPressed: root.moveRow(0)
        Keys.onReturnPressed: { root.moveRow(0); root.activateRow() }
        Keys.onEscapePressed: root.close()
      }

      Flow {
        Layout.fillWidth: true
        Layout.preferredHeight: childrenRect.height
        spacing: Style.space(3)
        Repeater {
          model: root.filters
          Button {
            required property string modelData
            text: modelData
            fontSize: Style.font.caption
            foreground: root.foreground
            selected: root.filter === modelData
            focusable: true
            onClicked: { root.filter = modelData; root.expandedId = ""; list.currentIndex = 0 }
          }
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

      RowLayout {
        Layout.fillWidth: true
        Text {
          Layout.fillWidth: true
          text: root.visibleRows.length + " " + (root.tab === "history"
            ? (root.visibleRows.length === 1 ? "entry" : "entries")
            : (root.visibleRows.length === 1 ? root.tab.slice(0, -1) : root.tab))
          color: root.muted
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
        Text {
          text: root.monitor && root.monitor.refreshing ? "Refreshing…" : "Enter to inspect"
          color: root.muted
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
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
                visible: !entry.expanded && root.tab !== "history" && entry.modelData.removalBlock === ""
                text: "Expand to remove"
                color: root.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }
              Text {
                Layout.maximumWidth: contents.width * 0.38
                text: root.tab === "packages" ? entry.modelData.version
                  : root.tab === "plugins" ? (entry.modelData.enabled ? "Enabled" : "Disabled")
                  : entry.modelData.kind === "plugins" ? "Plugin" : "Packages"
                textFormat: Text.PlainText
                color: root.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
              Text {
                text: entry.expanded ? "−" : "+"
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
              visible: root.tab !== "history" && text !== ""
              text: [entry.modelData.critical ? "Critical" : "",
                entry.modelData.bundled ? "Bundled with Omarchy" : root.tab === "plugins" ? "User installed" : ""].filter(Boolean).join(" · ")
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
            }
            Text {
              width: parent.width
              visible: entry.expanded && root.tab !== "history"
              text: entry.modelData.removalBlock === undefined ? "Refresh inventory to check removal eligibility."
                : entry.modelData.removalBlock || "Opens a terminal for review and confirmation."
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
            }
            Button {
              visible: entry.expanded && root.tab !== "history"
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
          text: root.monitor && root.monitor.refreshing ? "Reading your installed software…"
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
        text: root.tab === "history" ? "Plugin tracking since " + Model.date(root.snapshot.baselineAt)
          + ". Times show detection, not installation."
          + (root.snapshot.lastGap ? " Tracking was paused before " + Model.date(root.snapshot.lastGap.to) + "." : "")
          + (root.snapshot.logNotice ? " " + root.snapshot.logNotice : "")
          + (root.snapshot.historyTotal > 500 ? " Showing the latest 500 entries." : "")
          : "Checked " + Model.date(root.snapshot.sources && root.snapshot.sources[root.tab] ? root.snapshot.sources[root.tab].checkedAt : null)
            + " · " + (root.issue ? "Some information may be stale" : "Local to this computer")
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: root.muted
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
    }
  }
}
