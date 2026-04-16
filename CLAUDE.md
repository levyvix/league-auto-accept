### Building Executable
```bash
uv sync --all-groups  # Install dev dependencies
pyinstaller --onefile --name league-auto-accept main.py
```

## Project Overview

**League Auto Accept** is a League of Legends automation tool that monitors the game client and automatically:
- Accepts ready checks when the queue pops
- Selects (hovers) and locks in your configured champion during champion select
- Optionally auto-bans a champion
- Auto-requeues after games

## Architecture

### Core Components

**1. Main Application Loop (`main.py`)**
- Entry point: `LeagueAutoAcceptApp` class
- Manages three main threads:
  - **Monitor thread**: Detects League Client connection via `get_lcu_client()`
  - **Automation thread**: Runs the core automation logic
  - **Update thread**: Checks for application updates
- Handles terminal UI rendering using Rich library's `Live` display
- Manages input handling and screen navigation (main → picker → settings)

**2. Automation Logic (`main_logic.py`)**
- `AutoAccept` class: Core state machine for game phase handling
- Monitors the game flow via the LCU API endpoint `lol-gameflow/v1/session`
- Handles distinct phases:
  - `ReadyCheck`: Accepts the queue pop
  - `ChampSelect`: Hovers/locks champion and applies bans
  - `InProgress/WaitingForStats/EndOfGame`: Auto-requeue handling
- Tracks session state (what's been picked/locked, etc.)
- Key methods: `_handle_ready_check()`, `_handle_champ_select()`, `_handle_requeue()`

**3. League Client Communication (`lcu.py`)**
- `LCUClient`: HTTP client for the League Client Update (LCU) API
- Detects the League Client process (`LeagueClientUx.exe`) via psutil
- Extracts auth token and port from process command line
- Makes HTTPS requests to internal client API endpoints (uses self-signed certs)
- All API calls go through `client.request(method, endpoint, json_data)`

**4. Settings Management (`settings.py`)**
- `Settings` dataclass: Persists user configuration to `settings.json`
- Tracks champion selections (primary + backups, both roles)
- Stores ban preferences, spell selections
- Contains behavior toggles (auto_accept_on, insta_lock, auto_requeue, etc.)
- Delay configurations for timing actions
- Recent champions/bans list for quick reselection

**5. Terminal UI (`ui.py`)**
- `UIManager`: Rich-based terminal interface
- Screens:
  - Main status screen: Shows current settings and game phase
  - Champion picker: Searchable list with keyboard navigation (arrows, typing, backspace)
  - Settings menu: Toggle various options
  - Waiting screen: Displayed while client is offline
- Non-blocking input handling using `msvcrt` (Windows-specific)

**6. Data Loading (`data.py`)**
- `ChampionInfo` dataclass: Champion metadata (name, id, image path, etc.)
- `load_champions()`: Fetches owned champions from LCU API for the current summoner
- `load_summoner_id()`: Gets summoner ID from client

**7. Versioning & Updates (`version.py`, `updater.py`)**
- Tracks current application version
- `check_for_updates()`: Queries GitHub releases API for newer versions
- Provides in-app update notifications

## Data Flow

```
Main App Loop
├── Connects to League Client
├── Loads champion/summoner data
└── Runs AutoAccept state machine
    ├── Monitors game phase via LCU API
    ├── On ReadyCheck → POST accept to LCU
    ├── On ChampSelect → GET session, hover/lock champion
    └── On EndOfGame → Auto-requeue if enabled
```

## Key API Endpoints Used

| Purpose | Endpoint | Method |
|---------|----------|--------|
| Game flow phase | `lol-gameflow/v1/session` | GET |
| Accept queue | `lol-matchmaking/v1/ready-check/accept` | POST |
| Champ select data | `lol-champ-select/v1/session` | GET |
| Pick/ban actions | `lol-champ-select/v1/session/actions/{action-id}` | PATCH |
| Summoner info | `lol-summoner/v1/current-summoner` | GET |
| Champions | `lol-champions/v1/owned-champions-minimal` | GET |

## Important Notes

- **Windows-only**: Uses `msvcrt` for non-blocking input; will not work on macOS/Linux without modifications
- **No daemon mode**: Application runs in foreground; terminates when window closes or Ctrl+C pressed
- **Timing-dependent**: Champion hover/lock/ban timing relies on delay settings in `settings.json` to work reliably
- **Logging**: All logs written to `league_auto_accept.log` (console output suppressed to keep UI clean)
- **Self-signed SSL**: The League Client uses self-signed certificates; SSL verification is disabled in `requests`
