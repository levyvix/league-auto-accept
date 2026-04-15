import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Configuration for League Auto Accept."""

    # Champion selections (name, id pairs)
    champ_name: str = "Unselected"
    champ_id: str = "0"
    backup_champ_name: str = "Unselected"
    backup_champ_id: str = "0"

    # Secondary role champion (for role flexibility)
    secondary_champ_name: str = "Unselected"
    secondary_champ_id: str = "0"
    secondary_backup_champ_name: str = "Unselected"
    secondary_backup_champ_id: str = "0"

    # Ban selection
    ban_name: str = "Unselected"
    ban_id: str = "0"

    # Summoner spells
    spell1_name: str = "Unselected"
    spell1_id: str = "0"
    spell2_name: str = "Unselected"
    spell2_id: str = "0"

    # Behavior toggles
    auto_accept_on: bool = False
    insta_lock: bool = False
    insta_ban: bool = False
    auto_requeue: bool = False
    save_settings: bool = True
    preload_data: bool = False

    # Delays (in milliseconds)
    pick_start_hover_delay: int = 10000
    pick_start_lock_delay: int = 999999999
    pick_end_lock_delay: int = 1000
    ban_start_hover_delay: int = 1500
    ban_start_lock_delay: int = 999999999
    ban_end_lock_delay: int = 1000

    # Recently used
    recent_champions: List[str] = field(default_factory=list)  # List of champ IDs
    recent_bans: List[str] = field(default_factory=list)

    def add_recent_champion(self, champ_id: str):
        """Add champion to recently used list (keep last 5)."""
        if champ_id == "0":
            return
        if champ_id in self.recent_champions:
            self.recent_champions.remove(champ_id)
        self.recent_champions.insert(0, champ_id)
        self.recent_champions = self.recent_champions[:5]

    def add_recent_ban(self, ban_id: str):
        """Add ban to recently used list (keep last 5)."""
        if ban_id == "0":
            return
        if ban_id in self.recent_bans:
            self.recent_bans.remove(ban_id)
        self.recent_bans.insert(0, ban_id)
        self.recent_bans = self.recent_bans[:5]

    def to_dict(self) -> dict:
        """Convert settings to dictionary for JSON serialization."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Settings":
        """Create Settings instance from dictionary."""
        # Filter out unknown keys
        valid_fields = {f.name for f in Settings.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return Settings(**filtered_data)


def _get_settings_path(path: str = "settings.json") -> Path:
    """
    Get the settings file path.
    If path is relative, resolve it in the user's home directory for .exe compatibility.
    """
    settings_path = Path(path)
    if settings_path.is_absolute():
        return settings_path
    # Use home directory for relative paths to work in .exe mode
    return Path.home() / ".league_auto_accept" / path


def load_settings(path: str = "settings.json") -> Settings:
    """
    Load settings from JSON file.

    Args:
        path: Path to settings file (relative paths go to ~/.league_auto_accept/)

    Returns: Settings instance (with defaults if file doesn't exist)
    """
    settings_path = _get_settings_path(path)
    if settings_path.exists():
        try:
            with open(settings_path, "r") as f:
                data = json.load(f)
            logger.info(f"Loaded settings from {settings_path}")
            return Settings.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            logger.info("Using default settings")
    return Settings()


def save_settings(settings: Settings, path: str = "settings.json") -> bool:
    """
    Save settings to JSON file.

    Args:
        settings: Settings instance to save
        path: Path to settings file (relative paths go to ~/.league_auto_accept/)

    Returns: True if successful, False otherwise
    """
    try:
        settings_path = _get_settings_path(path)
        # Create directory if it doesn't exist
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w") as f:
            json.dump(settings.to_dict(), f, indent=2)
        logger.info(f"Saved settings to {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False
