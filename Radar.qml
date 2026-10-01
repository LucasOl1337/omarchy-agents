import QtQuick
import qs.Commons
import qs.Ui

// Ranked quota list for the Radar tab. Panel.qml owns the heuristic and
// hands this the already-sorted rows; this file only paints them.
//
// Order is what you act on: the ranking first (what to burn next, how much
// is left, when it comes back), then only the accounts that need a hand,
// then the harnesses with no quota at all.
Column {
  id: root
  required property var quotaRows
  required property var byoRows
  property var accountRows: []
  property bool refreshing: false
  property string readLabel: ""
  property color foreground: Color.foreground
  property color dim: Qt.darker(foreground, 1.55)
  property color urgent: Color.urgent
  property color track: Style.selectedFillFor(foreground, Color.accent)
  property string fontFamily: Style.font.family

  signal refreshRequested()
  signal accountUpdateRequested(string providerId)

  spacing: Style.space(10)

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

  readonly property bool empty: quotaRows.length === 0 && byoRows.length === 0 && accountRows.length === 0

  Item {
    width: parent.width
    implicitHeight: Math.max(radarHeader.implicitHeight, radarRefresh.implicitHeight)

    PanelSectionHeader {
      id: radarHeader
      anchors.left: parent.left
      anchors.right: radarRefresh.left
      anchors.verticalCenter: parent.verticalCenter
      text: "USAR AGORA"
      foreground: root.foreground
      fontFamily: root.fontFamily
    }

    Row {
      id: radarRefresh
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(6)

      Text {
        textFormat: Text.PlainText
        anchors.verticalCenter: parent.verticalCenter
        text: root.readLabel
        visible: text !== ""
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      PanelActionButton {
        anchors.verticalCenter: parent.verticalCenter
        iconText: "↻"
        bordered: true
        enabled: !root.refreshing
        tooltipText: "Reler as cotas agora"
        foreground: root.foreground
        fontFamily: root.fontFamily
        fontSize: Style.font.body
        onClicked: root.refreshRequested()
      }
    }
  }

  Text {
    visible: root.empty
    width: parent.width
    text: "Nenhuma cota nos registros carregados."
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    wrapMode: Text.WordWrap
  }

  Repeater {
    model: root.accountRows

    AccountRow {
      required property var modelData
      width: root.width
      row: modelData
    }
  }

  Column {
    visible: root.quotaRows.length > 0
    width: parent.width
    spacing: Style.space(10)

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
    visible: root.byoRows.length > 0 && (root.quotaRows.length > 0 || root.accountRows.length > 0)
    foreground: root.foreground
  }

  Column {
    visible: root.byoRows.length > 0
    width: parent.width
    spacing: Style.space(6)

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

  // Two lines: who and what is left, then the meter. Plain Column rows (no
  // nested Item+anchors) so flickable height stays honest and meters never
  // sit under the next title.
  component RadarRow: Column {
    id: quotaRow
    property var row: null
    property int rank: 0
    spacing: Style.space(4)

    readonly property bool hot: !!(row && (row.exhausted || row.alarming))

    Row {
      width: parent.width
      spacing: Style.space(8)

      Text {
        id: rowName
        textFormat: Text.PlainText
        width: parent.width - rowWhy.width - parent.spacing
        text: {
          if (!quotaRow.row) return ""
          var title = quotaRow.rank + "  " + quotaRow.row.harness
          if (quotaRow.row.pool !== "") title += " · " + quotaRow.row.pool
          return title
        }
        color: quotaRow.row && quotaRow.row.exhausted ? root.dim : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: quotaRow.rank === 1 && !quotaRow.hot
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
      }

      Text {
        id: rowWhy
        textFormat: Text.PlainText
        text: quotaRow.row ? quotaRow.row.why : ""
        color: quotaRow.hot ? root.urgent : root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        height: rowName.height
        verticalAlignment: Text.AlignVCenter
      }
    }

    Item {
      id: meter
      width: parent.width
      height: Math.max(Style.space(4), Math.round(Style.spacing.controlHeight * 0.14))

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
      visible: !!(quotaRow.row && quotaRow.row.account)
      height: visible ? implicitHeight : 0
      width: parent.width
      text: quotaRow.row && quotaRow.row.account ? quotaRow.row.account : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      elide: Text.ElideRight
    }

    Text {
      textFormat: Text.PlainText
      visible: !!(quotaRow.row && quotaRow.row.balanceText)
      height: visible ? implicitHeight : 0
      width: parent.width
      text: quotaRow.row ? quotaRow.row.balanceText : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  // An account that needs a hand: login dropped, or the plan answered without
  // its percentage. Healthy accounts never show here; they are ranked rows.
  component AccountRow: Item {
    id: accountRow
    property var row: null
    width: parent ? parent.width : 0
    height: Math.max(accountName.implicitHeight, accountAction.implicitHeight) + Style.space(8)

    Rectangle {
      anchors.fill: parent
      radius: Style.cornerRadius
      color: Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.10)
    }

    Text {
      id: accountName
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.leftMargin: Style.space(8)
      anchors.right: accountReading.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      text: {
        if (!accountRow.row) return ""
        var who = accountRow.row.harness || ""
        if (accountRow.row.account) who += " · " + accountRow.row.account
        return who
      }
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }

    Text {
      id: accountReading
      textFormat: Text.PlainText
      anchors.right: accountAction.left
      anchors.rightMargin: Style.space(10)
      anchors.verticalCenter: parent.verticalCenter
      text: accountRow.row ? accountRow.row.reading : ""
      color: root.urgent
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }

    Text {
      id: accountAction
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      text: accountRow.row ? accountRow.row.action : ""
      color: accountActionMouse.containsMouse ? root.foreground : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.underline: true

      MouseArea {
        id: accountActionMouse
        anchors.fill: parent
        anchors.margins: -Style.space(6)
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (accountRow.row) root.accountUpdateRequested(accountRow.row.providerId)
      }
    }
  }

  component ByoRow: Item {
    id: byoRow
    property var row: null
    width: parent ? parent.width : 0
    height: Math.max(byoName.implicitHeight, byoTag.implicitHeight) + Style.space(8)

    Rectangle {
      anchors.fill: parent
      radius: Style.cornerRadius
      color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.05)
    }

    Text {
      id: byoName
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.leftMargin: Style.space(8)
      anchors.right: byoTag.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
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
    }

    Text {
      id: byoTag
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      width: Math.min(implicitWidth, parent.width * 0.5)
      text: byoRow.row ? byoRow.row.why : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
      horizontalAlignment: Text.AlignRight
    }
  }
}
