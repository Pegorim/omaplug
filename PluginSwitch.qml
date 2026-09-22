import QtQuick
import QtQuick.Controls as QQC
import qs.Commons

// Caller-owned state: never claim success until Omarchy confirms it.
QQC.AbstractButton {
  id: control
  property bool value: false
  property bool busy: false
  property bool interactive: true
  property string explanation: ""
  signal requested()
  implicitWidth: Style.space(52)
  implicitHeight: Style.space(34)
  activeFocusOnTab: interactive
  hoverEnabled: true
  checkable: false
  Accessible.role: Accessible.CheckBox
  Accessible.checked: value
  Accessible.onToggleAction: if (interactive && !busy) requested()
  onClicked: if (interactive && !busy) requested()
  Keys.onReturnPressed: if (interactive && !busy) requested()
  QQC.ToolTip.visible: hovered
  QQC.ToolTip.text: explanation
  opacity: interactive ? 1 : 0.5
  background: Rectangle {
    color: "transparent"
    radius: height / 2
    border.width: control.activeFocus ? 2 : 0
    border.color: Color.accent
  }
  contentItem: Item {
    Rectangle {
      id: track
      anchors.centerIn: parent
      width: Style.space(42)
      height: Style.space(24)
      radius: height / 2
      color: control.value ? Color.accent : Qt.alpha(Color.popups.text, 0.20)
      border.width: control.value ? 0 : 1
      border.color: Qt.alpha(Color.popups.text, 0.3)
      Rectangle {
        width: Style.space(18)
        height: width
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        x: control.value ? track.width - width - Style.space(3) : Style.space(3)
        color: control.value ? Color.popups.background : Color.popups.text
        Behavior on x { NumberAnimation { duration: 120 } }
      }
    }
  }
}
