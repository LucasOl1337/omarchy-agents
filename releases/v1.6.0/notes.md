![Omarchy Agents v1.6.0](https://github.com/LucasOl1337/omarchy-agents/releases/download/v1.6.0/art.png)

Know which subscription to use next, inspect today at a glance, and see 9Router usage across Local and Railway without losing the source.

## What's new

- **Radar ranks the weekly pools worth burning next.** The new Radar tab orders the five subscription pools by usable headroom, includes reset timing, calls out exhausted or alarming quotas, and keeps BYO/no-quota providers separate. The result is a short answer to “which subscription should I use now?” rather than another list of unrelated meters.
- **9Router gets a first-class federated view.** Its tab now reads the local gateway's authenticated usage API, sums Local and Railway, and preserves the origin on model rows, hourly tooltips, period breakdowns, and the source summary. If the gateway API is unavailable, the collector safely falls back to the local SQLite ledger. The All tab remains harness-only to avoid counting proxied traffic twice.

## Improvements

- **Hour follows today's work.** The chart now runs from local midnight through the current hour instead of mixing in yesterday. Quiet early hours fold into one row, an order toggle can put the newest hour first, and tooltips break usage down by model and project.
- **Codex refreshes are much lighter.** The plugin owns a Codex collector compatible with current CLI approval flags, reads usage from Codex, Pi/OMP, and OpenCode sessions, and caches closed session-file totals instead of reparsing the full history on every refresh. On this machine the warm real collector completed in about 0.7 s during release validation.

## Fixes

- **Codex quotas no longer fall into BYO.** The packaged collector passed an approval flag rejected by Codex 0.154, which left rate limits empty. The plugin-side collector uses the supported invocation and restores the plan meters.
- **Federated totals stay correct when snapshot sync is enabled.** 9Router's upstream totals are account-scoped, so multiple desktop snapshots no longer multiply Railway usage. Period maps, hourly buckets, and source summaries now survive the sync pipeline.
- **Partial API failures keep useful 9Router data.** A failed chart request no longer discards all federated stats and silently drops back to local-only usage when other API responses are still valid.

## Compatibility

- No migration or deploy is required. Updating the `lol.agents` plugin and refreshing usage is enough.
- 9Router federation requires a local gateway version that exposes the federated `/api/usage/stats` and `/api/usage/chart` endpoints. Older or unavailable runtimes continue to use the local SQLite fallback.

Upstream PR: https://github.com/omacom/omarchy/pull/10400
