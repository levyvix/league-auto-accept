# League Auto Accept

A Windows terminal app that accepts ready checks, picks and bans champions,
accepts incoming pick-order swaps, and requeues. Written in Go with Bubble Tea
v2, Bubbles v2 and Lip Gloss v2. No Python runtime is required.

## Install and run

Download `league-auto-accept.exe` from [Releases](https://github.com/levyvix/league-auto-accept/releases).
Close older instances, start the League Client, and open the app while still in
the lobby so it can capture your two position preferences. Configure champions
and enable the desired settings. Keep the terminal open; closing it stops the app.

## Controls

| Key | Action |
| --- | --- |
| `1` | Toggle accept |
| `2` | Choose primary, backup, secondary and secondary backup |
| `3` | Choose a ban |
| `4` | Settings |
| `U` | Release updates |
| `Q` / `Ctrl+C` | Quit |

In the picker, type to search, use arrows to navigate and Enter to select.
Escape goes back. Select `None` to clear a slot.

| Settings key | Action |
| --- | --- |
| `P` | Auto-pick: hover and lock |
| `A` | Auto-ban |
| `L` | Instant lock |
| `B` | Instant ban |
| `R` | Auto-requeue |
| `W` | Accept incoming pick-order swaps |
| `S` | Auto-save |
| `Q` / `Esc` | Back |

Accept currently acts as the master switch for ready checks, picks and bans.
Pick and ban have additional independent switches. Swaps and requeue operate
independently of accept.

## Positions and backups

The app saves the first and second position preferences from the lobby. For
Mid/ADC, assigned `MIDDLE` uses the primary champions and `BOTTOM` uses the
secondary champions. If the first champion is banned or unavailable, the app
tries that pool's backup. Autofill leaves the pick to you. Unknown positions in
normal Classic queues wait for assignment; roleless modes use the primary pool.
Starting directly in champion select uses the last saved preferences.

Cancelling matchmaking disables auto-requeue so it does not restart your queue.

## Settings, logs and updates

Settings: `%USERPROFILE%\.league_auto_accept\settings.json`. Existing settings
from the previous app are read directly. Missing auto-pick/auto-ban options
default to enabled. Auto-save persists changes immediately; exit also saves.

Action timing is configurable in milliseconds in the JSON file:
`pick_start_hover_delay`, `pick_start_lock_delay`, `pick_end_lock_delay`,
`ban_start_lock_delay`, `ban_end_lock_delay`. Instant lock/ban bypass lock delays.
Legacy spell fields and `ban_start_hover_delay` remain compatible but are not
used for automation.

Logs append to `league_auto_accept.log` in the working directory. Client
discovery retries on disconnect and LCU requests have a five-second timeout.
Swap diagnostics include `Accept pick-order swap` and `Cannot load pick-order swaps`.

Press `U`, then `Y` to download an update and restart, or Escape to cancel.
Releases include `league-auto-accept-go.exe` as an updater-compatible alias of
the same native `league-auto-accept.exe`. Downloads require internet access and
a published native release asset.

## Development

Install Go 1.26.2 or newer:

```powershell
go mod download
go run ./cmd/league-auto-accept
go test ./...
go vet ./...
go build -trimpath -ldflags="-s -w" -o dist/league-auto-accept.exe ./cmd/league-auto-accept
```

| Package | Responsibility |
| --- | --- |
| `cmd/league-auto-accept` | Startup, logging, settings lifecycle and update helper |
| `internal/lcu` | Process discovery and authenticated local HTTPS requests |
| `internal/automation` | Gameflow, preferences, picks, bans, swaps and requeue |
| `internal/config` | Defaults, legacy JSON compatibility and atomic writes |
| `internal/tui` | Dashboard, searchable picker and settings |
| `internal/update` | GitHub release discovery, download and executable replacement |

The dedicated LCU transport accepts the local client's self-signed certificate,
uses the process port/token and Basic authentication as `riot`. Tokens are not
logged. Release downloads use normal HTTPS certificate verification.

Windows CI runs tests, vet and builds the executable as a downloadable artifact.
Release Please reads `version.txt`, updates the changelog/version constant and
creates releases. The release build checks out the released tag and uploads both
executable names. Python sources and tooling have been removed; Git history
retains the previous implementation.

Tests cover settings migration, authenticated HTTP and failures, position pools,
disabled actions, backups, duplicate inventory entries, picker controls and the
pick-order swap API. Gameplay was tested by the user; the latest swap correction
still needs live confirmation.
