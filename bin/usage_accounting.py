"""Calendar accounting for dated calls and cumulative session totals.

Input rows have one identity and normalized (cache-inclusive) token total.
A session spanning a boundary is never charged wholly to its last hour/day.
"""
from datetime import datetime

NATIVE_PROVIDERS = ('codex', 'claude', 'grok', 'hermes', 'opencode', 'devin')


def empty_part():
    return dict(tokens=0, calls=0, models={}, days={}, hours={}, unassignedTokens=0, excludedTokens=0)


def summarize(rows, since, until, period):
    providers = {p: empty_part() for p in NATIVE_PROVIDERS}
    for provider, model, ts, tokens, calls, pid, kind, span_start in rows:
        if not ts or ts > until or ts < since:
            continue
        part = providers.setdefault(provider, empty_part())
        if kind == 'session' and period != 'total' and (not span_start or span_start < since):
            part['excludedTokens'] += tokens
            continue
        part['tokens'] += tokens
        part['calls'] += calls
        part['models'][model] = part['models'].get(model, 0) + tokens
        when = datetime.fromtimestamp(ts)
        start = datetime.fromtimestamp(span_start) if span_start else None
        if kind == 'session' and (not start or start.date() != when.date()):
            part['unassignedTokens'] += tokens
            continue
        day = when.date().isoformat()
        part['days'][day] = part['days'].get(day, 0) + tokens
        hour = when.replace(minute=0, second=0, microsecond=0).timestamp()
        if kind == 'session' and (not start or start.timestamp() < hour):
            continue
        bucket = part['hours'].setdefault(hour, dict(start=hour, tokens=0, calls=0, models={}, projects={}))
        bucket['tokens'] += tokens
        bucket['calls'] += calls
        bucket['models'][model] = bucket['models'].get(model, 0) + tokens
        bucket['projects'][pid] = bucket['projects'].get(pid, 0) + tokens
    for part in providers.values():
        part['days'] = [dict(date=day, messageCount=n) for day, n in sorted(part['days'].items())]
        part['hours'] = [part['hours'][h] for h in sorted(part['hours'])]
    return providers
