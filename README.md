# League Auto Accept

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
