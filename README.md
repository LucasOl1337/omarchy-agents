# Omarchy Agents

Richer **Agents** panel for [Omarchy](https://omarchy.org/): one robot icon in the top bar, usage for every harness, All / Hour / Day / Week / Month / Total filters, local project inspection, and a Radar ranking of which quota to burn next.

This is the panel that runs on my Omarchy desktop. Stock `omarchy.agents` only charts Claude, Codex, and Fireworks over the last seven days. This checkout adds:

- **All** tab that sums every harness
- **Hour / Day / Week / Month / Total** token filters (Hour reads per-event buckets from the local tracking ledger, so it covers the agents with local session files)
- **Antigravity** and **Hermes** collectors
- **Projects** and **live** views: local sessions, compact project rows, on-demand message previews
- **Radar** tab: ranks live quotas so you know which subscription to burn next (headroom, reset countdown, exhausted pools called out)
- Grok / OpenCode / 9Router tracking when those session files exist on disk. The **9Router** tab is the local gateway: every HTTP call in `~/.9router`, including DailyWork GPT 5.6 Sol. All stays harness-only so Grok/Cursor are not counted twice. Tempo real **Todos** includes 9Router HTTP clients and still hides 9Router rows that only proxy a harness already indexed (Grok CLI).

Plugin id: `lol.agents` (so it can sit beside stock `omarchy.agents` without colliding).

Upstream PR to land the same work in Omarchy itself: [omacom/omarchy#10400](https://github.com/omacom/omarchy/pull/10400).

## Install

```bash
omarchy plugin add https://github.com/LucasOl1337/omarchy-agents.git --enable --yes
```

Then replace the stock widget in the bar with this one. In `~/.config/omarchy/shell.json`, change the bar entry `omarchy.agents` to `lol.agents` (right section), or:

```bash
omarchy plugin enable lol.agents --section right --after omarchy.tailscale
```

and remove `omarchy.agents` from the layout so you do not get two robot icons.

Left click opens the panel. Right click launches the default agent. Middle click cycles subscriptions.

## Collectors

On refresh the plugin runs stock `omarchy-agent-usage-update` (Claude, Codex, Fireworks), then the extra collectors in `bin/`:

| Collector | What it adds |
|---|---|
| `grok` | SuperGrok weekly pool + local session tokens |
| `antigravity` | Gemini / Claude / GPT quotas via `agy` |
| `hermes` | Tokens by model from local Hermes sessions |
| `9router` | Local 9Router gateway (`~/.9router/db/data.sqlite`) |
| `codex` | Overrides stock: packaged `-a untrusted` fails on codex 0.154 |

The panel also **displays** any JSON record already in `~/.local/state/omarchy/agents/usage/` (Grok, OpenCode, …).

## License

MIT. See [LICENSE](LICENSE).
