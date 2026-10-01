![Omarchy Agents v1.7.0](https://github.com/LucasOl1337/omarchy-agents/releases/download/v1.7.0/art.png)

The 9Router tab now adds Hostinger, Sherlocker, and this computer's Railway usage, and All folds that usage into the model you already track.

## What's new

- **Three gateways, one 9Router tab.** The tab reads Hostinger and Sherlocker from each gateway and adds Railway from the Jcode sessions already stored on this PC. The chat key those sessions use does not open the Railway usage page, so that line is what this computer sent, not the Railway dashboard. Each gateway stays named in the footer and on its own model rows.
- **All adds gateway usage onto the same model.** A row such as `Sherlocker · cc/claude-opus-5-5(high)` joins `claude-opus-5-5` when that model is already in All. The gateway label, the `cc/` or `cx/` route, and an effort suffix are dropped for that join. The 9Router tab still shows the gateway in the name.

## Improvements

- **The account sits under the pool when the login file has a name.** Codex, Claude, and Grok show who is signed in. Cursor's login token has no email, so that pool still has no account line.
- **A plan with no weekly percentage stays a plan.** SuperGrok Heavy can come back without `creditUsagePercent`. The panel keeps the plan name and says the quota did not arrive, instead of filing the account as bring-your-own.
- **Radar opens on the ranking.** Each pool is one line: what is left, when it resets, and the meter. A healthy account is not repeated underneath. A dropped login, or a plan whose percentage did not come back, gets a warning above the ranking. Reread only rereads. The login terminal opens only when the login actually dropped. The ranking uses the same height cap as the other views.
- **The refresh arrow drops a stuck read.** If a collector hangs, later refreshes no longer wait behind it. The button kills the run in flight and reads again. A ledger collector still running after 2 minutes, or a limits read after 5, is cut off.

## Fixes

- **Codex no longer looks logged out when the quota read is slow.** The packaged collector still starts Codex with a flag current Codex rejects, and a slow probe used to set both a status and a login hint. The plugin collector owns the Codex read, keeps the last good quota, and treats a timeout as "not read" rather than "login dropped".
- **Week is no longer a copy of today.** Claude and Codex keep a model split on each day. Week adds those days. It no longer repeats today's model list for the whole week.
- **The all-time footer counts every model.** It used to add only the rows on screen. A new model name could push another one below the cap and the footer shrank even though nothing was deleted.
- **Claude's today bar matches the model list.** Both numbers now come from the same session scan. Before, the bar kept the stock collector's total and the list used the per-day scan.

## Compatibility

- No migration. Update the `lol.agents` plugin and let usage refresh.
- Railway in this tab is this PC's Jcode history. Other machines that talk to the same Railway gateway are not in that number.
- Synced aggregation stays off until a sync folder is set. Turning the switch on with an empty folder does not upload anywhere.

Upstream PR: https://github.com/omacom/omarchy/pull/10400
