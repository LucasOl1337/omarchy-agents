// One accounting interface for every view. Sources supply totals and dated
// detail; missing detail is represented explicitly, never scaled or invented.
function number(value) {
  var n = Number(value || 0)
  return isFinite(n) && n > 0 ? n : 0
}

function tokenTotal(value) {
  if (!value || typeof value !== "object") return number(value)
  return number(value.inputTokens) + number(value.outputTokens)
    + number(value.cacheReadInputTokens) + number(value.cacheCreationInputTokens)
}

function mapTotal(map) {
  var total = 0
  for (var id in (map || {})) total += tokenTotal(map[id])
  return total
}

function assemble(ledger, summaries, modelKey, window) {
  ledger = ledger || {}
  var kind = window.period || "day"
  var today = kind === "day" || kind === "hour"
  if (today && (ledger.hours || []).length && number(ledger.hours[0].start) < number(window.midnight)) ledger = {}
  if (!today && ledger.period !== kind) ledger = {}
  var result = { hours: [], days: [], unassigned: [], models: {}, modelSources: {}, tokens: 0, calls: 0, warnings: [], sources: [] }
  var hours = {}, days = {}
  var rows = ledger.hours || []
  for (var i = 0; i < rows.length; i++) {
    var h = rows[i]
    hours[h.start] = { start: h.start, current: h.current, tokens: 0, calls: 0, models: {}, projects: {} }
  }
  function merge(into, part) {
    for (var key in (part || {})) into[key] = number(into[key]) + number(part[key])
  }
  function addModels(models, summary) {
    for (var key in models) {
      var id = key.indexOf("Sem modelo · ") !== 0 && (summary.canonical || (summary.id === "9router" && summaries.length > 1))
        ? modelKey(key, result.models) : key
      var amount = tokenTotal(models[key])
      result.models[id] = number(result.models[id]) + amount
      if (!result.modelSources[id]) result.modelSources[id] = {}
      var label = summary.name
      var separator = key.indexOf(" · ")
      if (summary.id === "9router" && separator > 0 && key.indexOf("Sem modelo · ") !== 0)
        label += " · " + key.slice(0, separator)
      result.modelSources[id][label] = number(result.modelSources[id][label]) + amount
    }
  }
  function datedRows(list) {
    return list.filter(function(row) {
      return row.date && (!window.today || row.date <= window.today) && (!window.start || row.date >= window.start)
    })
  }
  function addDated(list) {
    list = datedRows(list)
    for (var i = 0; i < list.length; i++) {
      var row = list[i]
      days[row.date] = number(days[row.date]) + number(row.messageCount)
    }
  }
  function withoutTime(summary, tokens, calls, reason) {
    if (!(tokens > 0)) return
    result.unassigned.push({ provider: summary.id, label: summary.name + " · sem horário", tokens: tokens,
      calls: calls, tooltip: summary.name + ": " + reason })
  }
  for (var s = 0; s < summaries.length; s++) {
    var summary = summaries[s]
    var local = (ledger.byProvider || {})[summary.id]
    var localEligible = summary.id !== "9router" || (summary.localRouter && summary.canonical)
    if (local && localEligible) {
      var total = number(local.tokens)
      result.tokens += total
      result.calls += number(local.calls)
      addModels(local.models || {}, summary)
      addDated(local.days || [])
      var dated = 0
      for (var j = 0; j < (local.hours || []).length; j++) {
        var part = local.hours[j], target = hours[part.start]
        if (!target) continue
        target.tokens += number(part.tokens)
        target.calls += number(part.calls)
        merge(target.models, part.models)
        merge(target.projects, part.projects)
        dated += number(part.tokens)
      }
      if (today) withoutTime(summary, Math.max(0, total - dated), 0, "Uso conhecido no dia, sem precisão por hora.")
      else withoutTime(summary, number(local.unassignedTokens), 0, "Acumulado de sessão sem divisão diária.")
      if (number(local.excludedTokens) > 0)
        result.warnings.push(summary.name + ": " + local.excludedTokens + " tokens acumulados atravessam o início do período e não foram somados.")
      var extra = summary.current && summary.synced ? Math.max(0, number(summary.tokens) - total) : 0
      if (extra > 0) {
        result.tokens += extra
        var unknown = {}; unknown["Sem modelo · outras máquinas · " + summary.name] = extra
        addModels(unknown, summary)
        withoutTime(summary, extra, 0, "Uso sincronizado sem timestamps locais.")
      }
      result.sources.push({ provider: summary.id, origin: "registros locais", tokens: total + extra })
      continue
    }
    if (!summary.current) continue
    var total = number(summary.tokens)
    if (total <= 0) continue
    result.tokens += total
    result.calls += number(summary.calls)
    var models = summary.models || {}, modelTotal = mapTotal(models)
    if (modelTotal <= total) {
      addModels(models, summary)
      if (modelTotal < total) {
        var missing = {}; missing["Sem modelo · " + summary.name] = total - modelTotal
        addModels(missing, summary)
      }
    } else {
      var invalid = {}; invalid["Sem modelo · " + summary.name] = total
      addModels(invalid, summary)
      result.warnings.push(summary.name + ": detalhe por modelo não bate com o total da fonte.")
    }
    if (today) withoutTime(summary, total, number(summary.calls), "Total da fonte sem timestamps no dia local; não distribuído nas horas.")
    else {
      var datedTotal = 0
      var validDays = datedRows(summary.days || [])
      for (var d = 0; d < validDays.length; d++) datedTotal += number(validDays[d].messageCount)
      if (datedTotal <= total) {
        addDated(summary.days || [])
        withoutTime(summary, total - datedTotal, 0, "Total da fonte sem divisão diária.")
      } else {
        withoutTime(summary, total, 0, "Buckets diários da fonte divergem do total; não foram somados.")
        result.warnings.push(summary.name + ": detalhe diário não bate com o total da fonte.")
      }
    }
    result.sources.push({ provider: summary.id, origin: summary.id === "9router" ? "dia dos serviços" : "coletor", tokens: total })
  }
  result.hours = rows.map(function(row) { return hours[row.start] })
  var dates = Object.keys(days).sort()
  for (var d = 0; d < dates.length; d++) result.days.push({ date: dates[d], messageCount: days[dates[d]] })
  if (today) result.days = [{ date: window.today || "", messageCount: result.tokens }]
  else for (var u = 0; u < result.unassigned.length; u++) {
    var row = result.unassigned[u]
    result.days.push({ date: "", label: row.label.replace("sem horário", "sem dia"), messageCount: row.tokens,
      unassigned: true, tooltip: row.tooltip })
  }
  return result
}

function combine(ledger, summaries, modelKey, midnight) {
  return assemble(ledger, summaries, modelKey, {period: "day", midnight: midnight})
}
