import QtQuick
import qs.Commons
import qs.Ui

// Ranked quota list for the Radar tab. Panel.qml owns the heuristic and
// hands this the already-sorted rows; this file only paints them.
Column {
  id: root
  required property var quotaRows
  required property var byoRows
  property string summary: ""
  property color foreground: Color.foreground
  property color dim: Qt.darker(foreground, 1.55)
  property color urgent: Color.urgent
  property color track: Style.selectedFillFor(foreground, Color.accent)
  property string fontFamily: Style.font.family

  spacing: Style.space(12)

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

  readonly property bool empty: quotaRows.length === 0 && byoRows.length === 0

  Text {
    visible: root.empty
    width: parent.width
    topPadding: Style.space(8)
    text: "Nenhuma cota nos registros carregados."
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    wrapMode: Text.WordWrap
  }

  Column {
    visible: root.quotaRows.length > 0
    width: parent.width
    spacing: Style.space(10)

    PanelSectionHeader {
      width: parent.width
      text: "USAR AGORA"
      foreground: root.foreground
      fontFamily: root.fontFamily
    }

    Text {
      visible: root.summary !== ""
      width: parent.width
      text: root.summary
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }

    Repeater {
      model: root.quotaRows

      RadarRow {
        required property var modelData
        required property int index
        width: parent.width
        row: modelData
        rank: index + 1
      }
    }
  }

  PanelSeparator {
    visible: root.quotaRows.length > 0 && root.byoRows.length > 0
    foreground: root.foreground
  }

  Column {
    visible: root.byoRows.length > 0
    width: parent.width
    spacing: Style.space(10)

    PanelSectionHeader {
      width: parent.width
      text: "SEM COTA / BYO"
      foreground: root.foreground
      fontFamily: root.fontFamily
    }

    Repeater {
      model: root.byoRows

      ByoRow {
        required property var modelData
        width: parent.width
        row: modelData
      }
    }
  }

  component RadarRow: Column {
    id: quotaRow
    property var row: null
    property int rank: 0

    readonly property bool hot: !!(row && (row.exhausted || row.alarming))

    spacing: Style.space(6)

    Item {
      width: parent.width
      implicitHeight: Math.max(nameLabel.implicitHeight, headLabel.implicitHeight)

      Text {
        id: nameLabel
        textFormat: Text.PlainText
        text: {
          if (!quotaRow.row) return ""
          var title = quotaRow.rank + "  " + quotaRow.row.harness
          if (quotaRow.row.tier !== "") title += " · " + quotaRow.row.tier
          if (quotaRow.row.badge !== "") title += " · " + quotaRow.row.badge
          return title
        }
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
        anchors.left: parent.left
        anchors.right: headLabel.left
        anchors.rightMargin: Style.spacing.sm
        anchors.verticalCenter: parent.verticalCenter
      }

      Text {
        id: headLabel
        textFormat: Text.PlainText
        text: quotaRow.row ? Math.round(quotaRow.row.headroom * 100) + "% livre" : ""
        color: quotaRow.hot ? root.urgent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    Item {
      id: meter
      width: parent.width
      implicitHeight: Math.max(Style.space(4), Math.round(Style.spacing.controlHeight * 0.14))

      Rectangle {
        id: meterTrack
        anchors.fill: parent
        radius: height / 2
        color: root.track
      }

      Rectangle {
        anchors.left: meterTrack.left
        anchors.verticalCenter: meterTrack.verticalCenter
        height: meterTrack.height
        radius: meterTrack.radius
        width: meterTrack.width * root.clamp(quotaRow.row ? quotaRow.row.percent : 0, 0, 1)
        color: quotaRow.hot ? root.urgent : root.foreground

        Behavior on width {
          NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
      }
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: quotaRow.row ? quotaRow.row.why : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }

    Text {
      textFormat: Text.PlainText
      visible: !!(quotaRow.row && quotaRow.row.balanceText)
      width: parent.width
      text: quotaRow.row ? quotaRow.row.balanceText : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  component ByoRow: Item {
    id: byoRow
    property var row: null

    implicitHeight: Math.max(byoName.implicitHeight, byoTag.implicitHeight) + Style.spacing.lg

    Rectangle {
      anchors.fill: parent
      radius: Style.cornerRadius
      color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.05)
    }

    Text {
      id: byoName
      textFormat: Text.PlainText
      text: {
        if (!byoRow.row) return ""
        var title = byoRow.row.harness
        if (byoRow.row.tier !== "") title += " · " + byoRow.row.tier
        return title
      }
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
      anchors.left: parent.left
      anchors.leftMargin: Style.space(8)
      anchors.right: byoTag.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
    }

    Text {
      id: byoTag
      textFormat: Text.PlainText
      text: byoRow.row ? byoRow.row.why : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
      horizontalAlignment: Text.AlignRight
      anchors.right: parent.right
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      width: Math.min(implicitWidth, parent.width * 0.55)
    }
  }
}
