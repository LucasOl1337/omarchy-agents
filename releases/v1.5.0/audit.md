# v1.5.0 audit

- Base: v1.4.1 = 678af83 (2026-09-12). Candidate: 424feee (main, pushed).
- Range: 2 commits · 2c7092b (periodModelMap shadowing fix, Cursor co-author) and 424feee (Hour period, this Devin session).

## Changes

| Item | Evidence | State | Where |
|---|---|---|---|
| Hour period: 24h buckets, current-hour highlight, per-window model map, `h` shortcut, empty state for API-only agents | 424feee · bin/tracking.py `hourly()`, TrackingData.qml `hours`, Panel.qml `hourlyRows`/`hourlyModelRows`/`periodRows`, tests | merged in candidate | notes |
| Ledger `--hours` mode (per-event scan, all-N-hour buckets incl. empty, `current` flag, models map, 9router excluded from `all`) | same commit | merged | notes (folded into feature bullet) |
| `usage` shadowing fix restores today's model breakdown on stock Claude/Codex records | 2c7092b | merged | notes (Fixes) |

## Coverage

- Devin: this session implemented and verified the Hour feature (tracking.py `--hours` against the live ledger, 222M tokens / 24h / devin; 36 unit tests incl. new hourly case; `qmlformat` parse clean).
- Cursor: co-author on 2c7092b per commit trailer; no session read.
- Claude/Codex/Grok/Hermes/Orca/Pi: no related sessions consulted.

## Validation

- `python3 -m unittest discover -s tests` · 36 tests OK (repo checkout and installed copy).
- `tracking.py --hours 24 --provider devin` · real ledger output verified.
- Upstream port: same files applied to `shell/plugins/agents/`, plugin tests + `test/shell.d/agents-*` green.
- Mirrors to omacom/omarchy PR #10400 as commit 6ad89bd8.

## Excluded / pending

- Cursor, Antigravity, Fireworks have no local event stream; Hour shows the empty state by design.
- 9router stays out of the `all` total, matching the existing tracking convention.
