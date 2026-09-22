# v1.6.0 audit

- Official base: v1.5.0 = `588e2fed8bdfefbf1e6af69cba522fddfbf7755a` (published 2026-09-15).
- Code candidate before release artifacts: `aa64e2ae02760168215eb2557da199c44c98b461` on `main`.
- Upstream at review start: `origin/main` = `21f041ddfd55e951e23969eb7efe9cf6a31f2fc5`; candidate was one commit ahead and not behind.
- Range reviewed: `v1.5.0..aa64e2a`, 13 non-merge commits plus PR #2's merge commit, 17 changed paths.
- Version source of truth: `manifest.json`, already `1.6.0` in the candidate.

## Change matrix

| Outcome | Before → now | Evidence | State / destination |
|---|---|---|---|
| Radar recommendation tab | Independent meters → ranked weekly pools with headroom, reset context, exhausted/alarming treatment, and BYO separation | `4349c76`, `8bafd41`, `e3d1884`, `a281a7f`; `Radar.qml`, `Panel.qml`, `tests/test_radar_rank.py`; PR #2 | Integrated · notes |
| Hour tracks the current day | Rolling 24 h mixed yesterday → local midnight through current hour, quiet-hour folding, reversible order, model/project tooltip split | `8cfcb6d`, `dcb9e40`, `8099103`, `9a6ee33`; `bin/tracking.py`, `TrackingData.qml`, `Panel.qml`, `tests/test_tracking.py` | Integrated · notes |
| Codex collector compatibility and cost | Stock `-a untrusted` invocation returned no limits and full histories were reparsed → supported app-server request plus cached per-file totals across Codex/Pi/OMP/OpenCode | `c6cf329`, `21f041d`; `bin/omarchy-agent-usage-codex`, `bin/update` | Integrated · notes |
| 9Router local visibility | Gateway calls only appeared indirectly → dedicated 9Router tab and HTTP clients in Tempo real | `9663e36`, `bc75137`; `assets/9router.svg`, collector/tracking/UI tests | Integrated · folded into federated feature |
| 9Router Local + Railway federation | Widget read only local SQLite → authenticated federated stats/chart API, origin-labelled models/hours/sources, safe DB fallback | `aa64e2a`; `bin/omarchy-agent-usage-9router`, `Main.qml`, `Panel.qml`, tests | Integrated · notes |
| Sync-safe federation | Federated account totals could be multiplied by device snapshots and detail fields were dropped → account scope and preserved period/hour/source fields | `aa64e2a`; `tests/test_federated_sync_contract.py` | Integrated · fixes |
| Partial endpoint resilience | Any one of seven API request failures forced local-only DB → valid federated responses are retained unless every stats request fails | `aa64e2a`; `test_one_failed_chart_keeps_federated_stats` | Integrated · fixes |

## Session and agent coverage

- **Cursor:** commit author and PR #2 identify Cursor Agent for the initial Radar implementation. Cursor session search found no high-confidence transcript tied directly to this repository change, so attribution relies on Git/PR evidence.
- **Claude:** session `claude:c47fde0e-87ac-4dca-acd2-70b373fa2cd4` maps directly to Hour fixes/refinements and Codex caching commits `8cfcb6d`, `dcb9e40`, `8099103`, `9a6ee33`, and `21f041d`. The session recorded real collector checks and the installed plugin updates.
- **Jcode / Codex:** current session `session_zebra_1790048820775_9faf220baaa3eb58` implemented, reviewed, installed, and validated the Local + Railway widget federation in `aa64e2a`. Independent swarm review found and drove fixes for snapshot duplication/detail loss and partial API failures.
- **Devin:** commit `c6cf329` carries Devin generation/co-author metadata for the plugin-side Codex collector. No Devin transcript was consulted.
- **Grok, Hermes, Orca, Pi:** no related implementation session found in the session sources consulted. Pi/OMP appear as data sources in the Codex collector, not as attributed contributors.
- **Git-only changes:** the original local 9Router collector and follow-up Radar narrowing commits have no reliably correlated implementation transcript in the consulted session index.

## Validation

- `python -m unittest discover -s tests -p 'test_*.py' -v` · **61/61 passed**.
- `python -m py_compile bin/*.py bin/omarchy-agent-usage-*` · passed.
- `bash -n bin/update` · passed.
- `git diff --check v1.5.0..aa64e2a` · passed.
- Qt `qmllint` over all seven QML entry files · no QML/JavaScript parse errors. Context/import warnings are expected when linting the plugin outside the full Omarchy shell module graph.
- Real Codex collector smoke · ready record, 5 models, completed in ~0.690 s on the release machine.
- Real 9Router collector smoke · `Local + Railway`, both sources available, 24 hourly buckets, nine current models, account scope, and no API errors; model/hour totals matched the reported total during the feature validation.
- Installed plugin smoke before release · source and active plugin matched, 61 tests passed in the installed copy, `omarchy-shell shell ping` returned `ok`, and the shell journal showed no plugin syntax/reference errors after reload.

## Excluded / constraints

- 9Router remains excluded from the All harness total by design because many gateway rows proxy already-indexed harness traffic.
- No database migration, application deployment, or external service rollout belongs to this plugin release.
- Full Wayland visual smoke in the isolated X11 agent bench is not representative because Omarchy's layer-shell surfaces require the real compositor. The active real shell was hot-reloaded and checked by runtime data, IPC, tests, and journal instead.
- Runtime token/request counts are intentionally not recorded in public notes because they change continuously and may describe private workloads.
