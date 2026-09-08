# Omarchy Agents

Richer **Agents** panel for [Omarchy](https://omarchy.org/): one robot icon in the top bar, usage for every harness, All / Day / Week / Month / Total filters, and local project inspection.

This is the panel that runs on my Omarchy desktop. Stock `omarchy.agents` only charts Claude, Codex, and Fireworks over the last seven days. This checkout adds:

- **All** tab that sums every harness
- **Day / Week / Month / Total** token filters
- **Antigravity** and **Hermes** collectors
- **Projects** and **live** views: local sessions, compact project rows, on-demand message previews
- Grok / OpenCode / 9Router tracking when those session files exist on disk

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

The panel also **displays** any JSON record already in `~/.local/state/omarchy/agents/usage/` (Grok, OpenCode, …).

## License

MIT. See [LICENSE](LICENSE).
