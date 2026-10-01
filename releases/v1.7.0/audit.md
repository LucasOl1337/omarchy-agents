# v1.7.0 audit

- Official base: v1.6.0 = `a7f12793f9eecdfb1764f4ba40d88bc71dbd8858` (published 2026-09-22).
- `origin/main` at review start matched local `main` at `c3750d646830057d03e930d9dd0092cf7b7c6195`. Not ahead, not behind. Five commits on main were unpublished.
- Candidate adds the uncommitted usage work on top of those five commits. Version source of truth: `manifest.json`, bumped `1.6.0` → `1.7.0` in this release.
- No migration. No hosted service. Delivery is the `lol.agents` plugin on this machine plus the GitHub Release.

## Change matrix

| Outcome | Before → now | Evidence | State / destination |
|---|---|---|---|
| 9Router sums three gateways | Tab read a stale local sqlite, or one local+Railway federation that was not the live gateways → Hostinger and Sherlocker from each gateway, Railway from this PC's Jcode sessions | `bin/omarchy-agent-usage-9router`, `tests/test_9router_usage.py` | Integrated · notes. Railway dashboard total is unavailable: the Jcode chat key gets 401/404 on the usage route. |
| All joins gateway rows to the same model | All skipped provider `9router` → gateway tokens join the harness id after the gateway label, route prefix, and effort suffix, when that bare id already exists | `Main.qml` `allModelKey`, `Panel.qml` `periodModelMap`, `tests/test_period_model_map.py` | Integrated · notes. The 9Router tab still keeps origins separate. |
| Account line on Radar | Pools had no identity → Codex, Claude, and Grok show the name from the local login file | `Radar.qml`, `Panel.qml` `accountLabel`, codex/grok/claude collectors | Integrated · notes. Cursor's JWT has no email claim, so that pool stays unnamed. |
| Grok plan without a weekly percent | Missing `creditUsagePercent` looked like no plan → `quotaState` unread keeps the plan name | `b3165ee`, `bin/omarchy-agent-usage-grok`, `tests/test_grok_billing.py` | Integrated · notes |
| Radar ranking first | Every healthy account was listed again under the ranking → one line per pool, warning only for a dropped login or a missing percentage, same height cap as the other views | `730872d`, `b03e89e`, `Radar.qml`, `tests/test_radar_rank.py` | Integrated · notes |
| Refresh kills a wedged collector | A hung read parked every later refresh → the arrow kills the in-flight run; watchdogs at 2 min (ledger) and 5 min (limits) | `a65b2c6`, `Main.qml`, `TrackingData.qml` | Integrated · notes |
| Codex false "login caiu" | Stock `-a untrusted` plus a slow probe set both status strings → plugin owns Codex, timeout is unread, last good limits stay | `bin/update`, `bin/omarchy-agent-usage-codex` | Integrated · notes |
| Week models no longer copy today | Bounded periods had no per-day `tokensByModel` for Claude and Codex → each day carries its own split | `bin/omarchy-agent-usage-claude-daily`, `bin/omarchy-agent-usage-codex`, `Main.qml` `synthesizeHistory` | Integrated · notes |
| All-time footer dropped models under the cap | Footer summed the 12 rows on screen → it sums the full period map and notes how many are hidden | `Panel.qml` `footerText` | Integrated · notes |
| Claude bar and model list disagreed | `recentDays` / `todayTotalTokens` stayed on the stock collector after history was rewritten → both follow the session scan | `bin/omarchy-agent-usage-claude-daily`, `tests/test_claude_daily.py` | Integrated · notes |
| README screenshots | Radar and All shots from the live panel | `c3750d6`, `screenshots/` | Integrated · audit only |

## Session and agent coverage

- **Grok:** this session `01a0f724-d829-72b3-8fc1-cf1d18d7fd99` wrote the uncommitted usage work (three gateways, All join, Codex false logout, Claude daily alignment, account fields, tests) and this release. High confidence: the diff was produced here.
- **Claude:** commits `a65b2c6`, `b3165ee`, `730872d`, `b03e89e`, and `c3750d6` are `Co-Authored-By: Claude Opus 5.5`. No Claude project directory named for this repo was found under `~/.claude/projects`. Attribution is the commit trailer, not a transcript.
- **Codex:** `~/.codex/sessions/2026/10/01/` contains rollouts that mention `omarchy-agents`. They were not opened far enough to tie one rollout to these diffs. Not credited as an author.
- **Jcode:** several `~/.jcode/sessions/*.json` mention the repo name. Not correlated to a commit or to this diff. Not credited.
- **Pi:** one session under a different project path mentions the name. Not this change.
- **Hermes:** no related session found outside the agent source tree.
- **Orca:** CLI and `~/.orca` are absent.

## Validation

- `python3 -m unittest discover -s tests -p 'test_*.py' -q` · **78 passed**.
- `python3 -m py_compile` on the four usage collectors touched · passed.
- `bash -n bin/update` · passed.
- `git diff --check` · passed.
- Live 9Router record before this release, from the installed collector: Hostinger 1.938B, Railway 4.362B (Jcode on this PC), Sherlocker 2.563B. Week chart and week model map both 4.446B.
- Live Claude record after `apply_daily`: today field, today's history, and today's model map all 389,039,832. Week bars and week history both 6.669B. Before the fix the today bar was 374.3M and the model row was 383.0M.

## Excluded

- LucasOL / Syncthing upload. `syncMode` is Off and `syncDir` is empty. Enabling it without a folder does not publish. Left off.
- Antigravity token bars. The local log stores prompt counts and quota buckets, not token totals. Not invented.
- Railway dashboard password guessing. Stopped. The chat key cannot read `/api/usage`.
- Cursor account email. The access token's claims are `aud`, `exp`, `iss`, `randomness`, `scope`, `sub`, `time`, `type`. No email to show.
