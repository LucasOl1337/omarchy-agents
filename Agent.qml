import QtQuick
import Quickshell.Io

// One agent's usage record, read straight off the data file that
// omarchy-agent-usage-update maintains. The panel never learns how the
// numbers were made — a record that appears in the usage directory is an
// agent, whoever wrote it.
Item {
  id: root
  visible: false

  property string agentId: ""
  property string path: ""
  property var record: null

  FileView {
    path: root.path
    preload: true
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
    onLoadFailed: root.record = null
  }

  function parse(content) {
    try {
      var parsed = JSON.parse(String(content || ""))
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) { root.record = null; return }
      if (!parsed.id) parsed.id = root.agentId
      root.record = parsed
    } catch (e) {
      console.warn("agents", "Ignoring bad usage record", root.path, e)
      root.record = null
    }
  }
}
