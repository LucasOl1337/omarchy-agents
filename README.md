# Omarchy Agents

Richer **Agents** panel for [Omarchy](https://omarchy.org/): one robot icon in the top bar, usage for every harness, All / Day / Week / Month / Total filters, and local project inspection.

This is the panel that runs on my Omarchy desktop. Stock `omarchy.agents` charts Claude, Codex, and Fireworks over the last seven days. This checkout adds the views, collectors, and accuracy guards that stock still lacks.

Plugin id: `lol.agents` (so it can sit beside stock `omarchy.agents` without colliding).

Upstream PR to land the same work in Omarchy itself: [omacom/omarchy#10400](https://github.com/omacom/omarchy/pull/10400).

## What this fork adds

- **All** tab that sums every enabled harness
- **Day / Week / Month / Total** token filters (week is the default; Total is all-time, not a quota window)
- **Projects** and **Tempo real**: local sessions, compact project rows, on-demand message previews, no network
- Collectors for **Grok**, **Antigravity**, **Hermes**, **Cursor**, **OpenCode**, and **Devin** (plus whatever JSON already sits in `~/.local/state/omarchy/agents/usage/`)
- **Stale-today guard**: leftover `today*` fields from a file that stopped being rewritten are not painted as calendar today
- **Period model map**: Day / Week / Month never fall back to all-time or billing-cycle `modelUsage` (that is how 1B of Grok Bot showed up under Day)
- **Cursor meters match Settings**: Cursor Models / Other Models from the same display sentences Cursor shows, with no fake prepaid wallet from Ultra's included cents

9Router stays in the tracking filter but is excluded from the combined project total, so requests already counted by the harnesses are not doubled.

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
| `cursor` | Plan & Usage meters (Cursor Models / Other Models) + cycle tokens by model |
| `opencode` | Completed assistant turns from `opencode.db`, dated by the message clock |
| `devin` | Local Devin CLI session tokens |

The panel also **displays** any JSON record already in `~/.local/state/omarchy/agents/usage/`.

## License

MIT. See [LICENSE](LICENSE).
