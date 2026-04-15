#!/usr/bin/env python3

import logging
import msvcrt
import threading
import time

from rich.live import Live
from rich.console import Console

from lcu import get_lcu_client
from settings import load_settings, save_settings
from data import load_champions, load_summoner_id
from main_logic import AutoAccept
from ui import UIManager

# Suppress logging to console (use file only)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("league_auto_accept.log")],
)
logger = logging.getLogger(__name__)


class LeagueAutoAcceptApp:
    """Main application class."""

    def __init__(self):
        self.settings = load_settings("settings.json")
        self.ui = UIManager()
        self.console = Console()
        self.lcu = None
        self.auto_accept = None
        self.champions = []
        self.running = True
        self.current_screen = "main"

    def run(self):
        """Main application loop using rich.Live for clean output."""
        logger.info("Starting League Auto Accept")

        # Start client monitor thread
        monitor_thread = threading.Thread(target=self._monitor_client, daemon=True)
        monitor_thread.start()

        # Start automation thread
        automation_thread = None

        try:
            # Create a dummy initial panel
            dummy_panel = self.ui.build_waiting_screen()
            with Live(dummy_panel, refresh_per_second=4, console=self.console) as live:
                while self.running:
                    if not self.lcu:
                        # Show waiting screen
                        panel = self.ui.build_waiting_screen()
                        live.update(panel)
                        time.sleep(0.5)
                        continue

                    # Client is connected
                    if not automation_thread or not automation_thread.is_alive():
                        self.auto_accept = AutoAccept(self.lcu, self.settings)
                        automation_thread = threading.Thread(
                            target=self.auto_accept.run, daemon=True
                        )
                        automation_thread.start()
                        logger.info("Started automation thread")

                    # Show appropriate screen and handle input
                    if self.current_screen == "main" and self.auto_accept:
                        panel = self.ui.build_main_screen(
                            self.settings, self.auto_accept.shared_state
                        )
                        live.update(panel)
                        self._handle_main_input()
                    elif self.current_screen == "champion_picker":
                        panel, filtered = self.ui.build_champion_picker(
                            "Select Champion", self.settings.recent_champions
                        )
                        live.update(panel)
                        self._handle_picker_input(filtered, "champ")
                    elif self.current_screen == "ban_picker":
                        panel, filtered = self.ui.build_champion_picker(
                            "Select Ban", self.settings.recent_bans
                        )
                        live.update(panel)
                        self._handle_picker_input(filtered, "ban")
                    elif self.current_screen == "settings":
                        panel = self.ui.build_settings_menu(self.settings)
                        live.update(panel)
                        self._handle_settings_input()

                    time.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.running = False
            if self.auto_accept and automation_thread and automation_thread.is_alive():
                self.auto_accept.stop()
                automation_thread.join(timeout=2)
            logger.info("Exiting")

    def _monitor_client(self):
        """Background thread to monitor League Client connection."""
        while self.running:
            self.lcu = get_lcu_client()
            if self.lcu and not self.champions:
                try:
                    summoner_id = load_summoner_id(self.lcu)
                    if summoner_id:
                        self.champions = load_champions(self.lcu, summoner_id)
                        logger.info(f"Loaded {len(self.champions)} champions")
                except Exception as e:
                    logger.error(f"Error loading data: {e}")
            time.sleep(2)

    def _handle_main_input(self):
        """Handle input on main screen."""
        key = self.ui.input_non_blocking()
        if not key:
            return

        key_char = chr(key).upper()
        if key_char == "1":
            self.settings.auto_accept_on = not self.settings.auto_accept_on
            if self.auto_accept:
                self.auto_accept.settings.auto_accept_on = self.settings.auto_accept_on
            if self.settings.save_settings:
                save_settings(self.settings)
            logger.info(f"Auto-accept toggled: {self.settings.auto_accept_on}")

        elif key_char == "2":
            self.current_screen = "champion_picker"
            self.ui.champions = self.champions
            self.ui.search_filter = ""
            self.ui.current_selection = 0

        elif key_char == "3":
            self.current_screen = "ban_picker"
            self.ui.champions = self.champions
            self.ui.search_filter = ""
            self.ui.current_selection = 0

        elif key_char == "4":
            self.current_screen = "settings"

        elif key_char == "Q":
            self.running = False

    def _handle_picker_input(self, filtered, picker_type):
        """Handle input in champion/ban picker."""
        if not filtered:
            key = self.ui.input_non_blocking()
            if key and key == 27:  # Esc
                self.current_screen = "main"
            return

        key = self.ui.input_non_blocking()
        if not key:
            return

        if key == 27:  # Esc
            self.current_screen = "main"

        elif key == 13:  # Enter
            selected = filtered[self.ui.current_selection]
            if picker_type == "champ":
                self.settings.champ_name = selected.name
                self.settings.champ_id = selected.id
                self.settings.add_recent_champion(selected.id)
                logger.info(f"Selected champion: {selected.name}")
            elif picker_type == "ban":
                self.settings.ban_name = selected.name
                self.settings.ban_id = selected.id
                self.settings.add_recent_ban(selected.id)
                logger.info(f"Selected ban: {selected.name}")

            if self.auto_accept:
                self.auto_accept.settings = self.settings
            if self.settings.save_settings:
                save_settings(self.settings)
            self.current_screen = "main"

        elif key == 224:  # Extended key (arrow keys)
            if msvcrt.kbhit():  # type: ignore[attr-defined]
                next_key = ord(msvcrt.getch())  # type: ignore[attr-defined]
                if next_key == 72:  # Up
                    self.ui.current_selection = max(0, self.ui.current_selection - 1)
                elif next_key == 80:  # Down
                    self.ui.current_selection = min(
                        len(filtered) - 1, self.ui.current_selection + 1
                    )

        elif 32 <= key <= 126:  # Printable
            self.ui.search_filter += chr(key)

        elif key == 8:  # Backspace
            self.ui.search_filter = self.ui.search_filter[:-1]

    def _handle_settings_input(self):
        """Handle input in settings menu."""
        key = self.ui.input_non_blocking()
        if not key:
            return

        key_char = chr(key).upper()
        if key_char == "L":
            self.settings.insta_lock = not self.settings.insta_lock
            if self.settings.save_settings:
                save_settings(self.settings)
            logger.info(f"Insta-lock toggled: {self.settings.insta_lock}")

        elif key_char == "B":
            self.settings.insta_ban = not self.settings.insta_ban
            if self.settings.save_settings:
                save_settings(self.settings)
            logger.info(f"Insta-ban toggled: {self.settings.insta_ban}")

        elif key_char == "Q":
            self.current_screen = "main"


def main():
    """Entry point."""
    app = LeagueAutoAcceptApp()
    app.run()


if __name__ == "__main__":
    main()
