function number(value) {
  var n = Number(value || 0)
  return isFinite(n) && n > 0 ? n : 0
}

function tokenTotal(value) {
  if (!value || typeof value !== "object") return number(value)
  return number(value.inputTokens) + number(value.outputTokens)
    + number(value.cacheReadInputTokens) + number(value.cacheCreationInputTokens)
}

function combine(ledger, summaries, modelKey, midnight) {
  ledger = ledger || {}
  if ((ledger.hours || []).length > 0 && number(ledger.hours[0].start) < number(midnight)) ledger = {}
  var result = { hours: [], unassigned: [], models: {}, tokens: 0, calls: 0 }
  var hours = {}
  var rows = ledger.hours || []
  for (var i = 0; i < rows.length; i++) {
    var h = rows[i]
    hours[h.start] = { start: h.start, current: h.current, tokens: 0, calls: 0, models: {}, projects: {} }
  }
  function merge(into, part) {
    for (var key in (part || {})) into[key] = number(into[key]) + number(part[key])
  }
  function addModels(models, routed) {
    for (var key in models) {
      var id = routed ? modelKey(key, result.models) : key
      result.models[id] = number(result.models[id]) + tokenTotal(models[key])
    }
  }
  // Local events supply both totals and their timestamps. Billing snapshots
  // without dated buckets stay explicit instead of being assigned an hour.
  for (var s = 0; s < summaries.length; s++) {
    var summary = summaries[s]
    var id = summary.id
    var local = (ledger.byProvider || {})[id]
    if (local && id !== "9router") {
      result.tokens += number(local.tokens)
      result.calls += number(local.calls)
      addModels(local.models || {}, false)
      for (var j = 0; j < (local.hours || []).length; j++) {
        var part = local.hours[j]
        var target = hours[part.start]
        if (!target) continue
        target.tokens += number(part.tokens)
        target.calls += number(part.calls)
        merge(target.models, part.models)
        merge(target.projects, part.projects)
      }
      var remoteTotal = summary.current && summary.synced ? number(summary.tokens) : 0
      var extra = Math.max(0, remoteTotal - number(local.tokens))
      if (extra > 0) {
        result.tokens += extra
        result.models["Sem modelo · outras máquinas · " + summary.name] = extra
        result.unassigned.push({ label: summary.name + " · outras máquinas", tokens: extra,
          calls: 0, tooltip: "Uso sincronizado sem timestamps locais nesta máquina." })
      }
      continue
    }
    if (!summary.current) continue
    var total = number(summary.tokens)
    if (total <= 0) continue
    result.tokens += total
    result.calls += number(summary.calls)
    var models = summary.models || {}
    var modelTotal = 0
    for (var mid in models) modelTotal += tokenTotal(models[mid])
    if (modelTotal <= total) {
      addModels(models, id === "9router")
      if (modelTotal < total) result.models["Sem modelo · " + summary.name] = total - modelTotal
    } else {
      result.models["Sem modelo · " + summary.name] = total
    }
    result.unassigned.push({
      provider: id,
      label: summary.name + " · sem horário",
      tokens: total,
      calls: number(summary.calls),
      tooltip: summary.name + ": o total inclui uso sem timestamps no dia local."
        + " Não foi distribuído entre as horas."
    })
  }
  result.hours = rows.map(function(row) { return hours[row.start] })
  return result
}
