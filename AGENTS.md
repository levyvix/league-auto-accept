# Repository guidance

Use descriptive feature names in branches, code, comments, commits and PRs.
Do not include the assistant product name in repository-facing text.

## Build and validate

```powershell
go test ./...
go vet ./...
go build -trimpath -ldflags="-s -w" -o dist/league-auto-accept.exe ./cmd/league-auto-accept
```

Use Go 1.26.2 or newer. Run gofmt on modified Go sources. The executable targets
Windows and discovers LeagueClientUx.exe through gopsutil. Keep builds in dist/.

## Architecture

- cmd/league-auto-accept: lifecycle, log file and update helper entry point.
- internal/config: settings defaults, legacy-compatible JSON and atomic saving.
- internal/lcu: local HTTPS transport, process port/token discovery and request deadlines.
- internal/automation: gameflow, lobby preferences, picks, bans, swaps and requeue.
- internal/tui: Bubble Tea v2 model with Bubbles input and Lip Gloss styling.
- internal/update: release discovery, native asset download and replacement helper.

Settings use the existing user .league_auto_accept/settings.json location.
Preserve JSON keys for upgrades. Never log auth tokens or use the local LCU TLS
exception for external requests. Unknown assigned positions and autofill must
not trigger a guessed pick. Auto-pick and auto-ban switches block their actions.
Use session/pick-order-swaps for pick-order offers; champion swaps are distinct.

## Releases

version.txt is managed by Release Please. Its generic extra-file updater tracks
the annotated version constant in internal/update/update.go. Windows releases
publish league-auto-accept.exe plus a league-auto-accept-go.exe compatibility
alias for installed native updaters. Both files must contain the same build.
