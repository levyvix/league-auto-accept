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
from updater import check_for_updates

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
        self.picker_type = None  # Track which type of picker is open
        self.wizard_step = 0  # Track position in champion setup wizard (0-3)

    def run(self):
        """Main application loop using rich.Live for clean output."""
        logger.info("Starting League Auto Accept")

        # Start update check in background (non-blocking)
        update_thread = threading.Thread(
            target=check_for_updates, args=(self.console,), daemon=True
        )
        update_thread.start()

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
                    elif self.current_screen == "picker":
                        # Determine title and recent list based on picker type
                        if self.picker_type == "champion_wizard":
                            title = "Select Champions"
                            recent = self.settings.recent_champions
                            # Get current champion id for auto-selection
                            current_id = self._get_wizard_current_champ_id()
                            panel, filtered = self.ui.build_champion_picker(
                                title,
                                recent,
                                wizard_step=self.wizard_step,
                                current_id=current_id,
                            )
                            # Auto-select the current champion if found
                            if current_id and current_id != "0":
                                for i, champ in enumerate(filtered):
                                    if champ.id == current_id:
                                        self.ui.current_selection = i
                                        break
                        elif self.picker_type == "ban":
                            title = "Select Ban"
                            recent = self.settings.recent_bans
                            panel, filtered = self.ui.build_champion_picker(
                                title, recent
                            )
                        else:
                            title = "Select"
                            panel, filtered = self.ui.build_champion_picker(title)

                        live.update(panel)
                        self._handle_picker_input(filtered, self.picker_type)
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
            # Always save settings on exit
            save_settings(self.settings)
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
            # Start champion wizard
            self.current_screen = "picker"
            self.picker_type = "champion_wizard"
            self.wizard_step = 0
            self.ui.champions = self.champions
            self.ui.search_filter = ""
            self.ui.current_selection = 0
            logger.info("Starting champion setup wizard")

        elif key_char == "3":
            # Select ban
            self.current_screen = "picker"
            self.picker_type = "ban"
            self.ui.champions = self.champions
            self.ui.search_filter = ""
            self.ui.current_selection = 0

        elif key_char == "4":
            self.current_screen = "settings"

        elif key_char == "U":
            from updater import check_for_updates_interactive

            check_for_updates_interactive(self.console)

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
            if picker_type == "champion_wizard":
                logger.info("Champion wizard cancelled")

        elif key == 13:  # Enter
            selected = filtered[self.ui.current_selection]

            if picker_type == "champion_wizard":
                # Handle wizard steps
                if self.wizard_step == 0:
                    self.settings.champ_name = selected.name
                    self.settings.champ_id = selected.id
                    logger.info(f"Step 1 - Primary: {selected.name}")
                elif self.wizard_step == 1:
                    self.settings.backup_champ_name = selected.name
                    self.settings.backup_champ_id = selected.id
                    logger.info(f"Step 2 - Primary Backup: {selected.name}")
                elif self.wizard_step == 2:
                    self.settings.secondary_champ_name = selected.name
                    self.settings.secondary_champ_id = selected.id
                    logger.info(f"Step 3 - Secondary: {selected.name}")
                elif self.wizard_step == 3:
                    self.settings.secondary_backup_champ_name = selected.name
                    self.settings.secondary_backup_champ_id = selected.id
                    logger.info(f"Step 4 - Secondary Backup: {selected.name}")

                self.settings.add_recent_champion(selected.id)

                # Move to next step
                self.wizard_step += 1
                if self.wizard_step > 3:
                    # Wizard complete
                    if self.auto_accept:
                        self.auto_accept.settings = self.settings
                    if self.settings.save_settings:
                        save_settings(self.settings)
                    self.current_screen = "main"
                    logger.info("Champion wizard completed")
                else:
                    # Move to next step, reset search
                    self.ui.search_filter = ""
                    self.ui.current_selection = 0

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

    def _get_wizard_current_champ_id(self) -> str:
        """Get the current champion ID for the current wizard step."""
        if self.wizard_step == 0:
            return self.settings.champ_id
        elif self.wizard_step == 1:
            return self.settings.backup_champ_id
        elif self.wizard_step == 2:
            return self.settings.secondary_champ_id
        elif self.wizard_step == 3:
            return self.settings.secondary_backup_champ_id
        return "0"

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

        elif key_char == "S":
            self.settings.save_settings = not self.settings.save_settings
            save_settings(self.settings)
            logger.info(f"Auto-save toggled: {self.settings.save_settings}")

        elif key_char == "R":
            self.settings.auto_requeue = not self.settings.auto_requeue
            if self.auto_accept:
                self.auto_accept.settings.auto_requeue = self.settings.auto_requeue
                self.auto_accept.shared_state["auto_requeue"] = (
                    self.settings.auto_requeue
                )
            if self.settings.save_settings:
                save_settings(self.settings)
            logger.info(f"Auto-requeue toggled: {self.settings.auto_requeue}")

        elif key_char == "Q":
            self.current_screen = "main"


def main():
    """Entry point."""
    app = LeagueAutoAcceptApp()
    app.run()


if __name__ == "__main__":
    main()
