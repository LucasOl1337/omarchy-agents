import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "omarchy.agents"
  ipcTarget: "omarchy.agents"
  manageIpc: false

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color surface: Color.popups.background
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  readonly property var providers: usage.enabledProviders
  // The selection follows the provider, not the slot it happens to sit in: a
  // provider whose first scan lands while the panel is open would otherwise
  // shift the list underneath you and swap out what you were reading.
  property string selectedProviderId: ""
  property string period: "week"
  readonly property var periodOptions: [
    { key: "hour", label: "Hour" },
    { key: "day", label: "Day" },
    { key: "week", label: "Week" },
    { key: "month", label: "Month" },
    { key: "total", label: "Total" }
  ]
  readonly property int providerIndex: {
    for (var i = 0; i < providers.length; i++)
      if (providers[i].providerId === selectedProviderId) return i
    return 0
  }
  readonly property var provider: providers.length > 0 ? providers[providerIndex] : null

  property string activeView: "provider"
  readonly property bool trackingExpanded: activeView === "projects" || activeView === "live"
  readonly property bool radarActive: activeView === "radar"
  readonly property var navigationTabs: {
    var tabs = [
      { id: "all", label: "All" },
      { id: "projects", label: "Projetos" },
      { id: "live", label: "Tempo real" },
      { id: "radar", label: "Radar" }
    ]
    for (var i = 0; i < providers.length; i++) {
      if (providers[i].providerId !== "all")
        tabs.push({ id: providers[i].providerId, label: providers[i].chipName || providers[i].providerName })
    }
    return tabs
  }
  readonly property string activeTab: (trackingExpanded || radarActive) ? activeView : (provider ? provider.providerId : "all")

  function selectTab(tab) {
    if (tab === "projects" || tab === "live" || tab === "radar") activeView = tab
    else { selectedProviderId = tab; activeView = "provider" }
    cursorActive = false
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }
  property bool cursorActive: false

  // Countdowns and "updated" read this instead of Date.now() so the
  // panel keeps telling the truth while it sits open.
  property double nowMs: Date.now()

  readonly property var limits: limitWindows(provider)
  readonly property var models: period === "hour" ? hourlyModelRows() : modelRows(provider, period)
  // Hour rows come from the tracking ledger (per-event timestamps); the
  // usage records only carry per-day buckets.
  readonly property var periodRows: period === "hour" ? hourlyRows() : daysForPeriod(provider, period)
  readonly property var headline: bindingWindow(provider)
  readonly property var balance: provider ? (provider.balance || null) : null
  // A prepaid account runs low the way a subscription window fills up: the
  // last 10% of the funded credits lights the same alarm.
  readonly property bool balanceAlarming: !!balance && balance.funded > 0
    && balance.remaining / balance.funded <= 0.1
  readonly property bool alarming: (!!headline && headline.percent >= 0.9) || balanceAlarming

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  function selectProvider(index) {
    if (providers.length === 0) return
    var wrapped = ((index % providers.length) + providers.length) % providers.length
    selectedProviderId = providers[wrapped].providerId
    activeView = "provider"
  }

  function refreshNow() {
    if (activeView === "projects") projectData.refresh()
    else if (activeView === "live") liveData.refresh()
    else if (activeView === "radar") usage.refreshLimits()
    else {
      usage.refreshAll(true)
      if (period === "hour") hourData.refresh()
    }
  }

  function launchAgent() {
    if (root.bar) root.bar.run("omarchy-agent --pick")
    root.close()
  }

  // ---------------------------------------------------------------- limits
  //
  // Both providers report the same two shapes: a short rolling session window
  // and a long weekly one. Everything below normalizes them into one record so
  // the meters and the hero speak a single language.

  // Claude spells its windows out ("Session (5-hour)"), Codex abbreviates
  // them ("5h window", "30m window"). Both have to land on the same record.
  function windowIsLong(text) {
    return text.indexOf("week") >= 0 || text.indexOf("7-day") >= 0 || text.indexOf("seven") >= 0
      || text.indexOf("month") >= 0 || text.indexOf("30-day") >= 0
  }

  function windowSpanMs(label) {
    var text = String(label || "").toLowerCase()
    if (text.indexOf("month") >= 0 || text.indexOf("30-day") >= 0) return 30 * 24 * 3600 * 1000
    if (windowIsLong(text)) return 7 * 24 * 3600 * 1000
    var hours = text.match(/(\d+)\s*-?\s*h(?:our)?\b/)
    if (hours) return Number(hours[1]) * 3600 * 1000
    var minutes = text.match(/(\d+)\s*-?\s*m(?:in(?:ute)?s?)?\b/)
    if (minutes) return Number(minutes[1]) * 60 * 1000
    return 0
  }

  function windowTitle(label) {
    var text = String(label || "").toLowerCase()
    if (text.indexOf("month") >= 0) return "Monthly"
    if (windowIsLong(text)) return "Weekly"
    if (text.indexOf("session") >= 0 || windowSpanMs(label) > 0) return "Session"
    var plain = String(label || "").replace(/\s*\(.*\)\s*/, "").trim()
    return plain === "" ? "Limit" : plain
  }

  // A collector that already knows which window a limit belongs to says so,
  // and that beats reading it back out of the label: a model-scoped limit is
  // titled after its model, and a name like "Opus 5 (1M context)" would parse
  // as a one-minute window.
  function limitWindow(label, percent, resetAt, title) {
    return {
      title: String(title || "") !== "" ? String(title) : windowTitle(label),
      percent: Number(percent),
      resetAt: String(resetAt || "")
    }
  }

  function limitWindows(p) {
    if (!p) return []
    var out = []
    var list = p.limits || []
    for (var i = 0; i < list.length; i++) {
      var entry = list[i] || {}
      var percent = Number(entry.percent)
      if (percent >= 0) out.push(limitWindow(entry.label, percent, entry.resetsAt, entry.title))
    }
    return out
  }

  // The window that decides how much room is left — the fullest one, since
  // that is what stops the next prompt.
  function bindingWindow(p) {
    var windows = limitWindows(p)
    var best = null
    for (var i = 0; i < windows.length; i++) {
      if (!best || windows[i].percent > best.percent) best = windows[i]
    }
    return best
  }

  function resetMsFor(w) {
    if (!w || w.resetAt === "") return -1
    var ms = new Date(w.resetAt).getTime()
    return isFinite(ms) ? ms - root.nowMs : -1
  }

  function formatDuration(ms) {
    if (!(ms > 0)) return "now"
    var minutes = Math.floor(ms / 60000)
    var hours = Math.floor(minutes / 60)
    var days = Math.floor(hours / 24)
    if (days > 0) return days + "d " + (hours % 24) + "h"
    if (hours > 0) return hours + "h " + (minutes % 60) + "m"
    return Math.max(1, minutes) + "m"
  }

  // ---------------------------------------------------------------- radar
  //
  // The radar is the five paid subscriptions and nothing else: Claude,
  // Codex, Grok, Cursor and Antigravity, one weekly pool each. Session
  // windows are burst headroom, not the quota that decides the week, so
  // they stay out; model-scoped extra pools (Fable Weekly, Claude / GPT
  // Weekly) stay out too. Cursor's two model pools are its billing-cycle
  // quota — it has no session window, so they are its "weekly".
  //
  // Rows rank by use-now headroom (1 - percent); when a pool is already
  // quite full, a sooner reset is a small nudge so you know when it frees.
  // Exhausted (>= 1.0) always sink, ordered by soonest reset. Alarming
  // (>= 0.9) sit just above them unless the reset is imminent (< 30m), in
  // which case the row stays usable and is tagged "quase reset". One of
  // the five with no windows (and no prepaid ledger) goes to Sem cota /
  // BYO, ranked by today's tokens — they never mix into the quota list.

  readonly property var radarQuotaRows: buildRadarQuotaRows(nowMs, providers)
  readonly property var radarByoRows: buildRadarByoRows(providers)
  readonly property string radarSummary: buildRadarSummary(radarQuotaRows)

  function radarHarness(p) {
    return p ? String(p.chipName || p.providerName || "") : ""
  }

  function radarTier(p) {
    var tier = p ? String(p.tierLabel || "") : ""
    if (tier === "") return ""
    return tier.charAt(0).toUpperCase() + tier.slice(1)
  }

  function radarWindowKind(w) {
    var title = String((w && w.title) || "").toLowerCase()
    if (title.indexOf("month") >= 0) return "monthly"
    if (windowIsLong(title)) return "weekly"
    if (title.indexOf("session") >= 0) return "session"
    return "other"
  }

  function radarWhy(harness, title, percent, resetMs, exhausted, alarming, imminent) {
    // Prefer the window title alone; the row header already shows the harness.
    var name = String(title || harness || "")
    var line = exhausted
      ? name + " 100% · esgotado"
      : name + " " + Math.round(Number(percent) * 100) + "% usado"
    if (!exhausted && alarming && imminent) line += " · quase reset"
    else if (!exhausted && alarming) line += " · alarmante"
    if (resetMs > 0) line += " · reset em " + formatDuration(resetMs)
    return line
  }

  function radarBand(percent, resetMs) {
    if (percent >= 1.0) return 3
    var imminent = resetMs > 0 && resetMs < 30 * 60 * 1000
    if (percent >= 0.9 && !imminent) return 2
    return 1
  }

  function radarScore(percent, resetMs, band) {
    var headroom = Math.max(0, 1 - percent)
    if (band === 3) return resetMs > 0 ? (1e15 - resetMs) : 0
    var score = headroom
    if (percent >= 0.7 && resetMs > 0)
      score += 0.05 * (1 / (1 + resetMs / 3600000))
    return score
  }

  function radarBalanceNote(p) {
    var b = p ? p.balance : null
    if (!b) return ""
    return radarHarness(p) + " · " + formatMoney(b.remaining, b.currency) + " restantes"
  }

  // Only the five subscriptions the radar is for. Anything else — local
  // harnesses, BYO gateways, sync-only records — stays out of both lists.
  function radarProviderAllowed(providerId) {
    var id = String(providerId || "").toLowerCase()
    return id === "claude" || id === "codex" || id === "grok" || id === "cursor"
      || id === "agy" || id === "a01" || id.indexOf("antigravity") >= 0
  }

  // One weekly pool per provider. "Weekly" is the normalized title every
  // generic 7-day window lands on; a titled pool ("Fable Weekly") is an
  // extra the list does not want. Sessions never pass. Antigravity ships
  // Gemini + Claude/GPT session/weekly pools; only Gemini Weekly matters
  // for that subscription. Cursor's model pools are its billing-cycle
  // quota, so both stay.
  function radarWindowAllowed(providerId, win) {
    var id = String(providerId || "").toLowerCase()
    var title = String((win && (win.title || win.label)) || "").toLowerCase()
    if (id === "antigravity" || id === "agy" || id === "a01" || id.indexOf("antigravity") >= 0)
      return title.indexOf("gemini") >= 0 && title.indexOf("weekly") >= 0 && title.indexOf("session") < 0
    if (title.indexOf("session") >= 0) return false
    if (id === "cursor") return true
    return title === "weekly"
  }

  function buildRadarQuotaRows(now, list) {
    var rows = []
    var seenBalance = ({})
    for (var i = 0; i < list.length; i++) {
      var p = list[i]
      if (!p || p.providerId === "all") continue
      if (!radarProviderAllowed(p.providerId)) continue
      var windows = limitWindows(p)
      var balance = p.balance || null
      if (windows.length === 0 && balance && balance.funded > 0) {
        var used = 1 - (balance.remaining / balance.funded)
        windows = [limitWindow("Prepaid", used, "", "Prepaid")]
      }
      if (windows.length === 0) continue
      var harness = radarHarness(p)
      var tier = radarTier(p)
      var balanceText = ""
      if (balance && !seenBalance[p.providerId]) {
        seenBalance[p.providerId] = true
        balanceText = radarBalanceNote(p)
      }
      for (var w = 0; w < windows.length; w++) {
        var win = windows[w]
        if (!radarWindowAllowed(p.providerId, win)) continue
        var percent = Number(win.percent)
        var resetMs = -1
        if (win.resetAt !== "") {
          var at = new Date(win.resetAt).getTime()
          if (isFinite(at)) resetMs = at - now
        }
        var exhausted = percent >= 1.0
        var imminent = resetMs > 0 && resetMs < 30 * 60 * 1000
        var alarming = percent >= 0.9
        var band = radarBand(percent, resetMs)
        rows.push({
          key: p.providerId + ":" + win.title + ":" + w,
          providerId: p.providerId,
          harness: harness,
          tier: tier,
          title: win.title,
          kind: radarWindowKind(win),
          percent: percent,
          headroom: Math.max(0, 1 - percent),
          resetMs: resetMs,
          exhausted: exhausted,
          alarming: alarming,
          imminent: imminent,
          band: band,
          score: radarScore(percent, resetMs, band),
          badge: exhausted ? "esgotado" : (alarming && imminent ? "quase reset" : (alarming ? "alarmante" : "")),
          why: radarWhy(harness, win.title, percent, resetMs, exhausted, alarming, imminent),
          balanceText: w === 0 ? balanceText : ""
        })
      }
    }
    rows.sort(function(a, b) {
      if (a.band !== b.band) return a.band - b.band
      if (b.score !== a.score) return b.score - a.score
      return String(a.harness).localeCompare(String(b.harness))
    })
    return rows
  }

  function buildRadarByoRows(list) {
    var rows = []
    for (var i = 0; i < list.length; i++) {
      var p = list[i]
      if (!p || p.providerId === "all") continue
      if (!radarProviderAllowed(p.providerId)) continue
      if (limitWindows(p).length > 0) continue
      if (p.balance && p.balance.funded > 0) continue
      var today = Number(p.todayTotalTokens || 0)
      rows.push({
        key: p.providerId,
        providerId: p.providerId,
        harness: radarHarness(p),
        tier: radarTier(p),
        todayTokens: today,
        why: "sem cota" + (today > 0 ? " · " + usage.formatTokenCount(today) + " tokens hoje" : "")
      })
    }
    rows.sort(function(a, b) { return b.todayTokens - a.todayTokens })
    return rows
  }

  function buildRadarSummary(rows) {
    var next = null
    var exhausted = []
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i]
      if (row.exhausted) exhausted.push(row.title.indexOf(row.harness) >= 0 ? row.title : (row.harness + " " + row.title))
      if (row.resetMs > 0 && (!next || row.resetMs < next.resetMs)) next = row
    }
    var lines = []
    if (next) lines.push("Próximo reset · " + next.harness + " " + next.title + " em " + formatDuration(next.resetMs))
    if (exhausted.length > 0) lines.push("Esgotadas · " + exhausted.join(", "))
    return lines.join("\n")
  }

  // ---------------------------------------------------------------- balance
  //
  // Prepaid agents report a credit ledger instead of rate-limit windows: the
  // record's balance object carries remaining, funded, and spent amounts.

  function currencyPrefix(currency) {
    var code = String(currency || "USD").toUpperCase()
    if (code === "USD") return "$"
    if (code === "EUR") return "€"
    if (code === "GBP") return "£"
    return code + " "
  }

  function formatMoney(value, currency) {
    var amount = Number(value)
    if (!isFinite(amount)) amount = 0
    return currencyPrefix(currency) + amount.toFixed(2)
  }

  function balanceDetailText(b) {
    if (!b || !(b.funded > 0)) return ""
    var text = formatMoney(b.spent, b.currency) + " spent of " + formatMoney(b.funded, b.currency) + " funded"
    if (b.estimated) text += " · estimated"
    return text
  }

  // ---------------------------------------------------------------- content

  // The plan you pay for, under the name of the tool it pays for. Limits live
  // in their own section; the hero just says what this is.
  function heroMeta(p) {
    if (!p) return ""
    if (String(p.usageStatusText || "") !== "") return p.usageStatusText
    var tier = String(p.tierLabel || "")
    if (tier === "") return "Subscription"
    return tier.charAt(0).toUpperCase() + tier.slice(1)
  }

  // Local calendar date, recomputed from nowMs so a panel left open across
  // midnight moves the "Today" row with the clock.
  function todayDate() {
    var now = new Date(root.nowMs)
    return now.getFullYear()
      + "-" + String(now.getMonth() + 1).padStart(2, "0")
      + "-" + String(now.getDate()).padStart(2, "0")
  }

  function dateOffset(days) {
    var now = new Date(root.nowMs)
    now.setDate(now.getDate() + days)
    return now.getFullYear()
      + "-" + String(now.getMonth() + 1).padStart(2, "0")
      + "-" + String(now.getDate()).padStart(2, "0")
  }

  function periodStartDate(kind) {
    if (kind === "day") return root.todayDate()
    if (kind === "week") return dateOffset(-6)
    if (kind === "month") return dateOffset(-29)
    return ""
  }

  // Buckets minted from the ledger carry their own label and tooltip so the
  // DayRow component can render them without learning about hours.
  function hourlyRows() {
    var snap = hourData.snapshot || ({})
    var list = snap.hours || []
    var out = []
    for (var i = 0; i < list.length; i++) {
      var h = list[i] || {}
      var start = Number(h.start || 0)
      var when = new Date(start * 1000)
      var tokens = Number(h.tokens || 0)
      var calls = Number(h.calls || 0)
      out.push({
        date: "",
        messageCount: tokens,
        current: h.current === true,
        label: Qt.formatDateTime(when, "HH:mm"),
        tooltip: Qt.formatDateTime(when, "HH:mm") + "–" + Qt.formatDateTime(new Date((start + 3600) * 1000), "HH:mm")
          + " · " + usage.formatTokenCount(tokens) + " tokens"
          + " · " + calls + (calls === 1 ? " call" : " calls")
      })
    }
    return out
  }

  function daysForPeriod(p, kind) {
    if (!p) return []
    if (kind === "total") return []
    if (kind === "week") return p.recentDays || []
    var start = periodStartDate(kind)
    var hist = (p.history && p.history.length) ? p.history : (p.recentDays || [])
    var out = []
    for (var i = 0; i < hist.length; i++) {
      var row = hist[i] || {}
      var date = String(row.date || "")
      if (start !== "" && date < start) continue
      if (kind === "month" && Number(row.messageCount || 0) <= 0) continue
      out.push(row)
    }
    // Only mint a Today row from todayTotalTokens when that field is
    // actually for today. A leftover usage file keeps yesterday's total
    // under the same name; synthesizing it here is how 585k of OpenCode
    // from Sept 6 showed up as "today".
    if (kind === "day" && out.length === 0 && usage.todayFieldsAreCurrent && usage.todayFieldsAreCurrent(p))
      out.push({ date: root.todayDate(), messageCount: Number(p.todayTotalTokens || 0) })
    return out
  }

  function emptyTokenBucket() {
    return { inputTokens: 0, outputTokens: 0, cacheReadInputTokens: 0, cacheCreationInputTokens: 0 }
  }

  function addTokenValue(usage, id, value) {
    if (!usage[id]) usage[id] = emptyTokenBucket()
    if (value && typeof value === "object") {
      usage[id].inputTokens += Number(value.inputTokens || 0)
      usage[id].outputTokens += Number(value.outputTokens || 0)
      usage[id].cacheReadInputTokens += Number(value.cacheReadInputTokens || 0)
      usage[id].cacheCreationInputTokens += Number(value.cacheCreationInputTokens || 0)
    } else if (Number(value || 0) > 0) {
      usage[id].inputTokens += Number(value || 0)
    }
  }

  function bucketTotal(bucket) {
    var b = bucket || {}
    return Number(b.inputTokens || 0) + Number(b.outputTokens || 0)
      + Number(b.cacheReadInputTokens || 0) + Number(b.cacheCreationInputTokens || 0)
  }

  function usageMapTotal(usage) {
    var n = 0
    for (var id in usage) n += bucketTotal(usage[id])
    return n
  }

  // Codex and Claude ship all-time modelUsage plus daily totals, but no
  // per-day tokensByModel. Hermes and Grok do. Cursor's modelUsage is the
  // current billing cycle. Sum each harness on its own, then combine — and
  // never substitute all-time/cycle modelUsage for a bounded period. That
  // fallback is how 1B of Grok Bot showed up under Day.
  function periodModelMap(p, kind) {
    if (!p) return {}
    if (p.providerId === "all") {
      var combined = ({})
      var list = root.providers || []
      for (var i = 0; i < list.length; i++) {
        var child = list[i]
        if (!child || child.providerId === "all" || child.providerId === "9router") continue
        var part = periodModelMap(child, kind)
        for (var id in part) addTokenValue(combined, id, part[id])
      }
      return combined
    }
    if (kind === "total") return p.modelUsage || ({})
    var start = periodStartDate(kind)
    var today = root.todayDate()
    var hist = p.history || []
    var tokenUsage = ({})
    var todayCovered = false
    for (var h = 0; h < hist.length; h++) {
      var row = hist[h] || {}
      var date = String(row.date || "")
      if (start !== "" && date < start) continue
      var models = row.tokensByModel || ({})
      var before = usageMapTotal(tokenUsage)
      for (var mid in models) addTokenValue(tokenUsage, mid, models[mid])
      if (date === today && usageMapTotal(tokenUsage) > before) todayCovered = true
    }
    if (!todayCovered && usage.todayFieldsAreCurrent && usage.todayFieldsAreCurrent(p)) {
      var todayModels = p.todayTokensByModel || ({})
      for (var tid in todayModels) addTokenValue(tokenUsage, tid, todayModels[tid])
    }
    return tokenUsage
  }

  function dayName(date) {
    var parsed = new Date(String(date || "") + "T00:00:00")
    if (isNaN(parsed.getTime())) return String(date || "")
    return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][parsed.getDay()]
  }

  function dayLabel(date, today) {
    if (today) return "Today"
    return dayName(date)
  }

  function dayTooltip(day, today) {
    if (!day) return ""
    var parsed = new Date(String(day.date) + "T00:00:00")
    var label = isNaN(parsed.getTime())
      ? String(day.date)
      : dayName(day.date) + " " + (parsed.getMonth() + 1) + "/" + parsed.getDate()
    var text = label + " · " + usage.formatTokenCount(Number(day.messageCount || 0)) + " tokens"
    // Prompt and session counts only exist for today, so they ride along here
    // instead of taking a section of their own. Billing-API agents never
    // count prompts, and "0 prompts" would read as a quiet day, not a gap.
    if (today && provider && provider.hasPromptStats !== false)
      text += " · " + Number(provider.todayPrompts || 0) + " prompts · "
        + Number(provider.todaySessions || 0) + " sessions"
    return text
  }

  function weekPeak(p) {
    var days = p ? (p.recentDays || []) : []
    var peak = 0
    for (var i = 0; i < days.length; i++) peak = Math.max(peak, Number(days[i].messageCount || 0))
    return peak
  }

  function modelRowsFromUsage(usageByModel, cap) {
    var rows = []
    for (var id in usageByModel) {
      var bucket = usageByModel[id] || {}
      var input = Number(bucket.inputTokens || 0)
      var output = Number(bucket.outputTokens || 0)
      var cacheRead = Number(bucket.cacheReadInputTokens || 0)
      var cacheWrite = Number(bucket.cacheCreationInputTokens || 0)
      var total = input + output + cacheRead + cacheWrite
      if (total <= 0) continue
      rows.push({
        name: usage.friendlyModelName(id),
        total: total,
        input: input,
        output: output,
        cacheRead: cacheRead,
        cacheWrite: cacheWrite
      })
    }
    rows.sort(function(a, b) { return b.total - a.total })
    return rows.slice(0, cap)
  }

  function modelRows(p, kind) {
    var cap = (kind === "total" || (p && p.providerId === "all")) ? 12 : 8
    return modelRowsFromUsage(periodModelMap(p, kind || "week"), cap)
  }

  // The ledger keeps one total per model (no in/out/cache split), which is
  // the same shape a plain numeric tokensByModel entry already has.
  function hourlyModelRows() {
    var map = ({})
    var models = (hourData.snapshot && hourData.snapshot.models) || ({})
    for (var id in models) addTokenValue(map, id, models[id])
    return modelRowsFromUsage(map, 8)
  }

  function modelTooltip(row) {
    if (!row) return ""
    if (row.output === 0 && row.cacheRead === 0 && row.cacheWrite === 0)
      return usage.formatTokenCount(row.total) + " tokens"
    return "In " + usage.formatTokenCount(row.input)
      + " · out " + usage.formatTokenCount(row.output)
      + " · cache read " + usage.formatTokenCount(row.cacheRead)
      + " · cache write " + usage.formatTokenCount(row.cacheWrite)
  }

  // Only speaks up when the numbers cover more than this machine.
  function footerText() {
    if (usage.syncStatusText !== "") return usage.syncStatusText
    if (provider && provider.providerId === "all") {
      var tokens = 0
      var rows = root.models
      for (var i = 0; i < rows.length; i++) tokens += Number(rows[i].total || 0)
      var label = root.period === "hour" ? "today" : root.period === "day" ? "today" : root.period === "week" ? "this week" : root.period === "month" ? "this month" : "all time"
      return usage.formatTokenCount(tokens) + " tokens " + label + " · every harness"
    }
    if (provider && provider.syncEnabled && provider.syncDeviceCount > 0)
      return "Merged from " + provider.syncDeviceCount + " device" + (provider.syncDeviceCount === 1 ? "" : "s")
    return ""
  }

  // Agents that ship a white mark carry an `assets/<id>-light.svg` twin for
  // light surfaces; marks that work on both (Claude's brand-orange) ship one
  // file. The luminance check decides which candidate to try first.
  function colorChannelLuminance(value) {
    var channel = Number(value)
    if (!isFinite(channel)) return 0
    return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)
  }

  function colorLuminance(color) {
    return 0.2126 * colorChannelLuminance(color.r)
      + 0.7152 * colorChannelLuminance(color.g)
      + 0.0722 * colorChannelLuminance(color.b)
  }

  // Marks resolve by convention, so a new agent's data file needs nothing
  // from this panel: assets/<id>.svg if it ships one, the module's bar glyph
  // if it doesn't.
  function iconCandidatesForProvider(p, surfaceColor) {
    if (!p) return []
    var candidates = []
    if (colorLuminance(surfaceColor || Color.background) >= 0.5)
      candidates.push(Qt.resolvedUrl("assets/" + p.providerId + "-light.svg"))
    candidates.push(Qt.resolvedUrl("assets/" + p.providerId + ".svg"))
    return candidates
  }

  // Nothing to report, nothing in the bar: Bar.qml collapses a slot whose item
  // is invisible, so the icon appears the moment the first scan finds usage and
  // stays away entirely on a machine that has never run either CLI.
  visible: providers.length > 0
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onProviderIndexChanged: if (panelFlick) panelFlick.contentY = 0
  onActiveViewChanged: if (panelFlick) panelFlick.contentY = 0
  onOpenedChanged: if (opened) {
    cursorActive = false
    nowMs = Date.now()
    if (panelFlick) panelFlick.contentY = 0
    usage.refreshLimits()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  TrackingData {
    id: projectData
    active: root.opened && root.activeView === "projects"
  }

  TrackingData {
    id: liveData
    active: root.opened && root.activeView === "live"
    live: true
    period: "day"
  }

  // The ledger only scans while a view asks for it; tying `active` to the
  // Hour period keeps the buckets current without a permanent 30 s scan.
  TrackingData {
    id: hourData
    active: root.opened && root.activeView === "provider" && root.period === "hour"
    hours: 24
    today: true
    provider: root.provider ? root.provider.providerId : "all"
  }

  Main {
    id: usage
    settings: root.settings
  }

  // Cheap enough to keep running: it only re-evaluates text bindings, and a
  // stale "resets in 2h" on a panel that is open is worse than a timer.
  Timer {
    interval: 30000
    running: root.opened
    repeat: true
    onTriggered: root.nowMs = Date.now()
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refreshNow(); return "ok" }
    function next(): string { root.selectProvider(root.providerIndex + 1); return "ok" }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󱚣"
    active: root.alarming
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.launchAgent()
      else if (buttonCode === Qt.MiddleButton) root.selectProvider(root.providerIndex + 1)
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(root.trackingExpanded ? Style.space(900) : Style.space(380))
    // Taller than the control panels on purpose: this one is a dashboard, and
    // the whole point is reading limits and history without scrolling.
    contentHeight: root.trackingExpanded ? panel.fittedContentHeight(Style.space(560), Style.space(600)) : panel.fittedContentHeight(column.implicitHeight, root.radarActive ? Style.space(520) : Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onMoveRequested: function(dx, dy) {
        if (root.trackingExpanded) { expandedTracking.scrollBy(dy); return }
        if (dx !== 0 && !root.radarActive) {
          root.cursorActive = true
          root.selectProvider(root.providerIndex + dx)
        }
        if (dy !== 0)
          panelFlick.contentY = root.clamp(panelFlick.contentY + dy * Style.space(56), 0,
                                           Math.max(0, panelFlick.contentHeight - panelFlick.height))
      }
      onActivateRequested: root.refreshNow()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") { root.refreshNow(); return }
        if (root.trackingExpanded) {
          if (root.activeView === "projects") {
            var periods = { "1": "day", d: "day", "2": "week", w: "week", "3": "month", m: "month", "4": "total", t: "total" }
            var chosen = periods[t.toLowerCase()]
            if (chosen) projectData.period = chosen
          }
          return
        }
        if (t === "h" || t === "H") root.period = "hour"
        else if (t === "1" || t === "d" || t === "D") root.period = "day"
        else if (t === "2" || t === "w" || t === "W") root.period = "week"
        else if (t === "3" || t === "m" || t === "M") root.period = "month"
        else if (t === "4" || t === "t" || t === "T") root.period = "total"
      }

      Column {
        id: inspection
        anchors.fill: parent
        visible: root.trackingExpanded
        spacing: Style.space(10)

        NavigationTabs { width: parent.width }

        Tracking {
          id: expandedTracking
          width: parent.width
          height: Math.max(1, inspection.height - y)
          mode: root.activeView === "live" ? "live" : "projects"
          tracker: root.activeView === "live" ? liveData : projectData
          foreground: root.foreground
          fontFamily: root.fontFamily
        }
      }

      Flickable {
        id: panelFlick
        visible: !root.trackingExpanded
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar {
          id: panelScrollBar
          policy: ScrollBar.AsNeeded
          padding: 0
        }

        Column {
          id: column
          // Inset so meters/captions never sit under the scrollbar thumb.
          width: panelFlick.width - Style.space(14)
          spacing: Style.space(12)

          // ---------- Hero: provider mark · name · plan ----------
          PanelHero {
            id: hero
            visible: !!root.provider && !root.radarActive
            width: parent.width
            title: root.provider ? root.provider.providerName : ""
            meta: root.heroMeta(root.provider)
            foreground: root.foreground
            fontFamily: root.fontFamily

            iconComponent: Component {
              Item {
                id: heroMark
                property var candidates: root.iconCandidatesForProvider(root.provider, root.surface)
                // Provider objects are rebuilt on every refresh, which churns the
                // array's identity without changing its content. Restart the fallback
                // walk only when the URLs change: re-pointing source at a URL whose
                // load already failed emits no statusChanged, so an identity-only
                // reset would strand the walker on a missing -light twin.
                property string candidatesKey: candidates.join("\n")
                property int candidateIndex: 0
                onCandidatesKeyChanged: candidateIndex = 0

                width: Style.font.display
                height: Style.font.display

                Image {
                  id: heroMarkImage
                  anchors.fill: parent
                  source: heroMark.candidateIndex < heroMark.candidates.length ? heroMark.candidates[heroMark.candidateIndex] : ""
                  sourceSize.width: Style.font.display * 2
                  sourceSize.height: Style.font.display * 2
                  fillMode: Image.PreserveAspectFit
                  // Advancing source from inside its own status change trips the
                  // binding-loop detector; defer the step one tick.
                  onStatusChanged: if (status === Image.Error && heroMark.candidateIndex < heroMark.candidates.length)
                    Qt.callLater(function() { heroMark.candidateIndex++ })
                }

                Text {
                  textFormat: Text.PlainText
                  anchors.centerIn: parent
                  visible: heroMarkImage.status !== Image.Ready
                  text: button.text
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.display
                }
              }
            }
          }

          Text {
            visible: root.providers.length === 0
            width: parent.width
            topPadding: Style.space(24)
            text: "No AI coding subscriptions found.\nAgents show up here once you've used them."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }

          // ---------- Provider switch ----------
          NavigationTabs {
            id: providerSwitch
            width: parent.width
          }

          Radar {
            visible: root.radarActive
            width: parent.width
            quotaRows: root.radarQuotaRows
            byoRows: root.radarByoRows
            summary: root.radarSummary
            foreground: root.foreground
            dim: root.dim
            urgent: root.urgent
            track: root.track
            fontFamily: root.fontFamily
          }

          // ---------- Status ----------
          // Only an auth or endpoint problem earns the alarm surface. Cursor
          // rides a healthy status line in usageStatusText with no help text,
          // while the stock Claude and Codex collectors always ship a login
          // hint in authHelpText even when signed in. A real problem sets
          // both, so the box needs both.
          BorderSurface {
            visible: !root.radarActive && !!root.provider
              && String(root.provider.usageStatusText || "") !== ""
              && String(root.provider.authHelpText || "") !== ""
            width: parent.width
            implicitHeight: statusText.implicitHeight + Style.spacing.xl * 2
            color: root.alpha(root.urgent, 0.10)
            borderSpec: Border.flat(root.alpha(root.urgent, 0.35), 1)
            radius: Style.cornerRadius

            Text {
              id: statusText
              textFormat: Text.PlainText
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.leftMargin: Style.space(12)
              anchors.rightMargin: Style.space(12)
              text: root.provider ? String(root.provider.authHelpText || "") : ""
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }
          }

          // ---------- Balance / limits ----------
          PanelSeparator {
            visible: !root.radarActive && (balanceSection.visible || limitsSection.visible)
            foreground: root.foreground
          }

          Column {
            id: balanceSection
            visible: !root.radarActive && !!root.balance
            width: parent.width
            spacing: Style.space(10)

            // The meter shows what is left, not what is used: a prepaid
            // account drains toward empty rather than filling toward a cap.
            readonly property real ratio: root.balance && root.balance.funded > 0
              ? root.clamp(root.balance.remaining / root.balance.funded, 0, 1)
              : -1

            PanelSectionHeader {
              width: parent.width
              text: "BALANCE"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Item {
              width: parent.width
              implicitHeight: Math.max(balanceLabel.implicitHeight, balanceValue.implicitHeight)

              Text {
                id: balanceLabel
                text: "Prepaid credits"
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
              }

              Text {
                id: balanceValue
                textFormat: Text.PlainText
                text: root.balance ? root.formatMoney(root.balance.remaining, root.balance.currency) : ""
                color: root.balanceAlarming ? root.urgent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
              }
            }

            Meter {
              visible: balanceSection.ratio >= 0
              width: parent.width
              value: balanceSection.ratio
              alarming: root.balanceAlarming
            }

            Text {
              textFormat: Text.PlainText
              visible: text !== ""
              width: parent.width
              text: root.balanceDetailText(root.balance)
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }

          Column {
            id: limitsSection
            visible: !root.radarActive && root.limits.length > 0
            width: parent.width
            spacing: Style.space(10)

            PanelSectionHeader {
              text: "LIMITS"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.limits

              LimitRow {
                required property var modelData
                width: limitsSection.width
                window: modelData
              }
            }
          }

          // ---------- Period ----------
          PanelSeparator {
            visible: !root.radarActive && periodSwitch.visible
            foreground: root.foreground
          }

          Row {
            id: periodSwitch
            visible: !root.radarActive && !!root.provider
            width: parent.width
            spacing: Style.spacing.md

            readonly property real cellWidth: root.periodOptions.length > 0
              ? (width - spacing * (root.periodOptions.length - 1)) / root.periodOptions.length
              : 0

            Repeater {
              model: root.periodOptions

              Button {
                required property var modelData

                width: periodSwitch.cellWidth
                text: modelData.label
                selected: root.period === modelData.key
                bordered: true
                foreground: root.foreground
                fontFamily: root.fontFamily
                fontSize: Style.font.caption
                verticalPadding: Style.spacing.controlPaddingY
                onClicked: root.period = modelData.key
              }
            }
          }

          // ---------- Usage ----------
          PanelSeparator {
            visible: !root.radarActive && usageSection.visible
            foreground: root.foreground
          }

          Column {
            id: usageSection
            visible: {
              if (root.radarActive) return false
              var list = root.periodRows
              for (var i = 0; i < list.length; i++)
                if (Number(list[i].messageCount || 0) > 0) return true
              return false
            }
            width: parent.width
            spacing: Style.spacing.md

            readonly property var days: root.periodRows
            readonly property real peak: {
              var list = days
              var high = 0
              for (var i = 0; i < list.length; i++) high = Math.max(high, Number(list[i].messageCount || 0))
              return Math.max(1, high)
            }

            PanelSectionHeader {
              width: parent.width
              text: root.period === "hour" ? "TOKENS BY HOUR (TODAY)" : root.period === "day" ? "TOKENS TODAY" : root.period === "month" ? "TOKENS BY DAY (MONTH)" : "TOKENS BY DAY"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: usageSection.days

              DayRow {
                required property var modelData
                required property int index

                width: usageSection.width
                day: modelData
                ratio: Number(modelData.messageCount || 0) / usageSection.peak
                // By date, not by position: the Claude stats-cache fallback can
                // hand us a window that stops short of today. Hourly buckets
                // flag their in-progress hour instead.
                today: modelData.current === true || String(modelData.date || "") === root.todayDate()
              }
            }
          }

          // Agents the ledger does not index (Cursor, Antigravity, Fireworks
          // report through billing APIs) land here on Hour: an honest empty
          // state instead of a chart that silently shows another window.
          Text {
            textFormat: Text.PlainText
            visible: !root.radarActive && root.period === "hour" && !usageSection.visible
            width: parent.width
            text: hourData.error !== "" ? "Falha ao atualizar"
              : (hourData.busy || !hourData.snapshot.hours ? "Lendo registros…" : "Sem registros hoje")
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          // ---------- Models ----------
          PanelSeparator {
            visible: !root.radarActive && modelSection.visible
            foreground: root.foreground
          }

          Column {
            id: modelSection
            visible: !root.radarActive && root.models.length > 0
            width: parent.width
            spacing: Style.spacing.md

            PanelSectionHeader {
              width: parent.width
              text: root.period === "total" ? "TOKENS BY MODEL (ALL TIME)" : "TOKENS BY MODEL"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.models

              ModelRow {
                required property var modelData
                width: modelSection.width
                row: modelData
                // Scaled to the heaviest model, so the top row is always full —
                // the same scale-to-peak the weekly chart uses for its busiest day.
                share: modelData.total / Math.max(1, root.models[0].total)
              }
            }
          }

          Text {
            textFormat: Text.PlainText
            visible: !root.radarActive && text !== ""
            width: parent.width
            topPadding: Style.space(2)
            text: root.footerText()
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
          }
        }
      }
    }
  }

  // A limit window: label and percentage, meter, and reset countdown.
  component LimitRow: Column {
    id: limitRow
    property var window: null

    readonly property bool alarming: window && window.percent >= 0.9

    spacing: Style.space(6)

    Item {
      width: parent.width
      implicitHeight: Math.max(limitLabel.implicitHeight, limitValue.implicitHeight)

      Text {
        id: limitLabel
        textFormat: Text.PlainText
        // A model-scoped window is titled after its model, and those names run
        // long enough to reach the percentage, so the title gives way first.
        text: limitRow.window ? limitRow.window.title : ""
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
        anchors.left: parent.left
        anchors.right: limitValue.left
        anchors.rightMargin: Style.spacing.sm
        anchors.verticalCenter: parent.verticalCenter
      }

      Text {
        id: limitValue
        textFormat: Text.PlainText
        text: limitRow.window && limitRow.window.percent >= 0
          ? Math.round(limitRow.window.percent * 100) + "%"
          : "—"
        color: limitRow.alarming ? root.urgent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    Meter {
      width: parent.width
      value: limitRow.window ? limitRow.window.percent : -1
      alarming: limitRow.alarming
    }

    Text {
      id: resetText
      textFormat: Text.PlainText
      width: parent.width
      text: {
        var remainingMs = root.resetMsFor(limitRow.window)
        return remainingMs > 0 ? "Resets in " + root.formatDuration(remainingMs) : ""
      }
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }

  component NavigationTabs: AgentTabs {
    tabs: root.navigationTabs
    activeTab: root.activeTab
    expanded: root.trackingExpanded
    foreground: root.foreground
    fontFamily: root.fontFamily
    onSelected: function(tab) { root.selectTab(tab) }
  }

  // Rounded track showing the percentage of the allowance used.
  component Meter: Item {
    id: meter
    property real value: -1
    property bool alarming: false
    property real thickness: Math.max(Style.space(4), Math.round(Style.spacing.controlHeight * 0.14))

    implicitHeight: thickness

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
      width: meterTrack.width * root.clamp(meter.value, 0, 1)
      color: meter.alarming ? root.urgent : root.foreground

      Behavior on width {
        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
      }
    }

  }

  // One row per day: label, bar, tokens. Today is picked out in full
  // foreground so the week reads as a run-up to right now.
  component DayRow: Item {
    id: dayRow
    property var day: null
    property real ratio: 0
    property bool today: false

    implicitHeight: Math.max(dayLabel.implicitHeight, dayValue.implicitHeight) + Style.spacing.sm

    Text {
      id: dayLabel
      textFormat: Text.PlainText
      text: dayRow.day && dayRow.day.label ? dayRow.day.label : root.dayLabel(dayRow.day ? dayRow.day.date : "", dayRow.today)
      color: dayRow.today ? root.foreground : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: dayRow.today
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(52)
    }

    Rectangle {
      id: dayTrack
      anchors.left: dayLabel.right
      anchors.right: dayValue.left
      anchors.leftMargin: Style.space(8)
      anchors.rightMargin: Style.space(10)
      anchors.verticalCenter: parent.verticalCenter
      height: Math.max(Style.space(4), Math.round(Style.spacing.controlHeight * 0.14))
      radius: height / 2
      color: root.track

      Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        height: parent.height
        radius: parent.radius
        width: parent.width * root.clamp(dayRow.ratio, 0, 1)
        color: dayRow.today ? root.foreground : root.alpha(root.foreground, 0.55)

        Behavior on width {
          NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
      }
    }

    Text {
      id: dayValue
      textFormat: Text.PlainText
      text: usage.formatTokenCount(dayRow.day ? Number(dayRow.day.messageCount || 0) : 0)
      color: dayRow.today ? root.foreground : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
      horizontalAlignment: Text.AlignRight
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(52)
    }

    MouseArea {
      id: dayHover
      anchors.fill: parent
      hoverEnabled: true
      acceptedButtons: Qt.NoButton
    }

    PanelToolTip {
      visible: dayHover.containsMouse
      text: dayRow.day && dayRow.day.tooltip ? dayRow.day.tooltip : root.dayTooltip(dayRow.day, dayRow.today)
      fontFamily: root.fontFamily
    }
  }

  // Model rows read as a table: the share bar fills the row behind the label
  // instead of stacking under it, which keeps the whole dashboard on one screen.
  component ModelRow: Item {
    id: modelRow
    property var row: null
    property real share: 0

    implicitHeight: modelName.implicitHeight + Style.spacing.lg

    Rectangle {
      anchors.fill: parent
      radius: Style.cornerRadius
      color: root.alpha(root.foreground, 0.05)
    }

    Rectangle {
      anchors.left: parent.left
      anchors.top: parent.top
      anchors.bottom: parent.bottom
      width: parent.width * root.clamp(modelRow.share, 0, 1)
      radius: Style.cornerRadius
      color: root.alpha(root.foreground, 0.14)

      Behavior on width {
        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
      }
    }

    Text {
      id: modelName
      textFormat: Text.PlainText
      text: modelRow.row ? modelRow.row.name : ""
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
      anchors.left: parent.left
      anchors.leftMargin: Style.space(8)
      anchors.right: modelTokens.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
    }

    Text {
      id: modelTokens
      textFormat: Text.PlainText
      text: modelRow.row ? usage.formatTokenCount(modelRow.row.total) : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      font.bold: true
      anchors.right: parent.right
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
    }

    MouseArea {
      id: modelHover
      anchors.fill: parent
      hoverEnabled: true
      acceptedButtons: Qt.NoButton
    }

    PanelToolTip {
      visible: modelHover.containsMouse
      text: root.modelTooltip(modelRow.row)
      fontFamily: root.fontFamily
    }
  }
}
