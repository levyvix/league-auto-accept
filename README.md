# League Auto Accept

A Python port of the [League Auto Accept](https://github.com/sweetriverfish/LeagueAutoAccept) automation tool. Automatically accepts queue notifications and locks in your champion/ban during champion select.

## Features

- **Auto-accept queue** — Automatically accepts the ready check
- **Champion pick/lock** — Hover and lock your configured champion
- **Champion ban** — Hover and lock your configured ban
- **Instant lock** — Optional instant lock or delayed lock with configurable timing
- **Terminal UI** — Interactive menu-driven interface
- **Settings persistence** — Saves your configuration to `settings.json`

## Installation

1. **Clone or create the directory:**
   ```bash
   cd league-auto-accept
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start League of Legends client** before running the app
2. **Run the app:**
   ```bash
   python3 main.py
   ```
3. **Using the app:**
   - The app will show "Waiting for League Client" until it connects
   - Press **1** to toggle auto-accept ON/OFF
   - Press **2** to select your champion (type to filter, arrows to select, Enter to confirm)
   - Press **3** to select your ban
   - Press **4** to open settings (toggle insta-lock, insta-ban)
   - Press **Q** to quit

## Configuration

Settings are automatically saved to `settings.json` after each change. You can also manually edit this file:

```json
{
  "champ_name": "Ahri",
  "champ_id": "103",
  "ban_name": "Yasuo",
  "ban_id": "157",
  "insta_lock": false,
  "insta_ban": false,
  "pick_start_hover_delay": 10000,
  "pick_end_lock_delay": 1000,
  "ban_start_hover_delay": 1500,
  "ban_end_lock_delay": 1000,
  "auto_accept_on": false,
  "save_settings": true
}
```

### Key Settings

- `champ_name`/`champ_id` — Your primary champion pick
- `ban_name`/`ban_id` — Champion to ban
- `insta_lock` — If true, immediately locks your champion (default: delayed)
- `insta_ban` — If true, immediately locks your ban (default: delayed)
- `pick_start_hover_delay` — Wait this many ms before hovering your champion (default: 10000ms)
- `pick_end_lock_delay` — Lock your champion this many ms before timer ends (default: 1000ms)
- `ban_start_hover_delay` — Wait this many ms before hovering your ban (default: 1500ms)
- `ban_end_lock_delay` — Lock your ban this many ms before timer ends (default: 1000ms)
- `save_settings` — If true, settings are auto-saved after changes (default: true)
- `auto_accept_on` — Remember last auto-accept toggle state (default: false)

## Logs

Application logs are written to `league_auto_accept.log` and also printed to console.

## License

This is a community port inspired by the original [LeagueAutoAccept](https://github.com/sweetriverfish/LeagueAutoAccept) by sweetriverfish.

**Disclaimer:** This tool interacts with the League Client Update (LCU) API. Use at your own risk. The tool is for educational purposes and may violate Riot's Terms of Service.
