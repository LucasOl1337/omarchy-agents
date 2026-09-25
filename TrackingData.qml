import QtQuick
import Quickshell.Io

Item {
  id: root
  visible: false
  property bool active: false
  property bool paused: false
  property bool live: false
  // >0 switches the collector to per-hour buckets over the last N hours
  // (--hours), which the panel's Hour period reads instead of projects/rows.
  property int hours: 0
  // With hours > 0, buckets from local midnight to the current hour instead
  // of the rolling window.
  property bool today: false
  property string period: "week"
  property string provider: "all"
  property string project: "*"
  property string search: ""
  property int offset: 0
  property var snapshot: ({projects: [], rows: [], tokens: 0, calls: 0, records: 0, errors: []})
  property string error: ""
  property bool pending: false
  property bool forcing: false
  readonly property bool busy: collector.running
  // Epoch seconds of the snapshot on screen; the panel shows it next to the
  // refresh button so a stale ledger is visible instead of silently old.
  readonly property real updatedAt: Number((snapshot || {}).updatedAt || 0)
  onPeriodChanged: resetPage()
  onProviderChanged: { project = "*"; resetPage() }
  onProjectChanged: resetPage()
  onSearchChanged: resetPage()
  onOffsetChanged: refreshDelay.restart()
  onActiveChanged: { if (active) refreshDelay.restart(); else refreshDelay.stop() }
  onPausedChanged: if (!paused && active) refreshDelay.restart()
  function resetPage() { offset = 0; refreshDelay.restart() }
  function refresh() {
    if (collector.running) { pending = true; return }
    var script = decodeURIComponent(Qt.resolvedUrl("bin/tracking.py").toString().substring(7))
    collector.command = hours > 0
      ? ["python3", script, "--hours", String(hours), "--provider", provider].concat(today ? ["--today"] : [])
      : ["python3", script, "--period", period, "--provider", provider, "--project", project, "--search", search, "--offset", String(offset)]
    collector.running = true
    collectorWatchdog.restart()
  }
  // The refresh button: a collector stuck behind the ledger lock or on a slow
  // disk would otherwise swallow every retry as "pending" forever. Kill it and
  // start over.
  function forceRefresh() {
    error = ""
    if (collector.running) {
      forcing = true
      pending = true
      collector.running = false
      return
    }
    refresh()
  }
  property var detail: null
  property string detailId: ""
  readonly property bool detailBusy: detailReader.running
  function loadDetails(id) {
    detailId = id
    detail = null
    if (!detailReader.running) readDetails()
  }
  function readDetails() {
    detailReader.command = ["python3", decodeURIComponent(Qt.resolvedUrl("bin/tracking.py").toString().substring(7)), "--detail", detailId]
    detailReader.requestedId = detailId
    detailReader.running = true
  }
  Process {
    id: detailReader
    property string requestedId: ""
    onExited: { if (root.detailId !== requestedId) root.readDetails() }
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          var result = JSON.parse(text)
          if (result.id === root.detailId) root.detail = result
        } catch (e) { root.detail = null }
      }
    }
  }
  Timer { id: refreshDelay; interval: 250; onTriggered: if (root.active) root.refresh() }
  // A normal scan takes seconds; two minutes means it is wedged.
  Timer { id: collectorWatchdog; interval: 120000; onTriggered: if (collector.running) root.forceRefresh() }
  Timer { interval: root.live ? 5000 : 30000; repeat: true; running: root.active && !root.paused; onTriggered: if (!root.busy) root.refresh() }
  Process {
    id: collector
    onExited: (code, status) => {
      collectorWatchdog.stop()
      if (code !== 0 && !root.forcing) root.error = "Não foi possível atualizar. Tentando novamente…"
      if (root.forcing) { root.forcing = false; root.pending = false; root.refresh(); return }
      if (root.pending) { root.pending = false; refreshDelay.restart() }
    }
    stdout: StdioCollector {
      onStreamFinished: {
        if (text.trim() === "") return
        try { root.snapshot = JSON.parse(text); root.error = "" }
        catch (e) { root.error = "Resposta do coletor inválida" }
      }
    }
  }
}
