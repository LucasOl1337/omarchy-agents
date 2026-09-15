![Omarchy Agents v1.5.0](https://github.com/LucasOl1337/omarchy-agents/releases/download/v1.5.0/art.png)

Hourly token charts from the same local ledger that powers Projetos and Tempo real.

## What's new

- **Hour period.** The filter row gains a fifth option, first in the row: tokens bucketed by hour over the last 24h, with the in-progress hour highlighted like "Today". TOKENS BY MODEL rescopes to the same window, row tooltips carry the hour range plus token and call counts, and `h` switches to it from the keyboard. Hour reads the tracking ledger's per-event timestamps, so it covers the agents with local session files (Claude, Codex, Grok, Hermes, OpenCode, Devin). Billing-API agents (Cursor, Antigravity, Fireworks) get an honest empty state rather than a chart that quietly shows a different window. The ledger only scans while a view asks for it, so Hour costs nothing while the panel sits on another period and refreshes every 30 s while open.

## Fixes

- **Today's model breakdown fills in again.** A local map inside `periodModelMap` shadowed the `usage` helper, so `todayTokensByModel` never merged in when a record's history carried no per-day model split. The stock Claude and Codex records hit exactly that path. Day shows today's model rows again.

Upstream PR: https://github.com/omacom/omarchy/pull/10400
