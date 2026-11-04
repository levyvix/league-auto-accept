# League Auto Accept

## Native Go application

The Go rewrite uses Bubble Tea v2, Bubbles v2 and Lip Gloss v2. It talks directly
to the same local League Client API, discovers `LeagueClientUx.exe`, and builds
as a single Windows executable without Python.

```powershell
go run ./cmd/league-auto-accept
go test ./...
go vet ./...
go build -trimpath -ldflags="-s -w" -o dist/league-auto-accept-go.exe ./cmd/league-auto-accept
```

Use Go 1.26.2 or newer. Start the app while still in the League lobby so it can
capture the primary and secondary position preferences. Settings are shared with
the existing app at `%USERPROFILE%\.league_auto_accept\settings.json`.
Run only one version of the automation at a time.

Controls: `1` toggles automation, `2` opens the four-step champion picker,
`3` selects a ban, `4` opens settings, and `Q` quits. Type to search champions;
use arrows and Enter to select. In settings, `P` controls auto-pick, `A` controls
auto-ban, `L` instant lock, `B` instant ban, `R` requeue, `W` swap acceptance,
and `S` auto-save. Autofill leaves champion selection to the player.

`U` opens release updates; confirm with `Y` to download and restart. The updater
only accepts the `league-auto-accept-go.exe` release asset so an older Python
binary cannot replace the native application. A native release asset must be
published before this flow can download an update.

Logs are written to `league_auto_accept.log`. HTTP requests have deadlines;
client discovery retries automatically after a disconnect. A cancelled queue
disables automatic requeue. The Python implementation below remains available
as a reference during live-client validation of the rewrite.

A League of Legends automation tool that automatically accepts queue notifications and locks in your champion during champion select.

## Installation

### Option A: Pre-built executable

Download the latest `league-auto-accept.exe` from the [Releases](../../releases) page. No dependencies required.

### Option B: Run from source

For this option, you need:
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/levyvix/league-auto-accept
cd league-auto-accept
uv run main.py
```

## Usage

1. Start the League of Legends client before running the app
2. Run the app — it will monitor the client and automatically:
   - Accept the ready check
   - Hover and lock your configured champion
   - Optionally ban a champion
3. Configure your champion and settings in the terminal UI

Settings are saved to `settings.json`.
