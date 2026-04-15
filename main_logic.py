import json
import logging
import threading
import time
from typing import Optional, Dict, Any

from lcu import LCUClient
from settings import Settings

logger = logging.getLogger(__name__)


class AutoAccept:
    """Main automation logic for accepting queue and selecting champions."""

    def __init__(self, lcu: LCUClient, settings: Settings):
        self.lcu = lcu
        self.settings = settings
        self.running = True

        # Per-session state
        self.picked_champ = False
        self.locked_champ = False
        self.picked_ban = False
        self.locked_ban = False
        self.last_chat_room = ""
        self.champ_select_start = 0

        # State shared with UI
        self.shared_state = {
            'phase': 'Unknown',
            'is_auto_accept_on': settings.auto_accept_on,
        }

    def run(self):
        """Main loop for automation."""
        while self.running:
            if not self.settings.auto_accept_on:
                time.sleep(2)
                continue

            response = self.lcu.request('GET', 'lol-gameflow/v1/session')
            if not response or not response.ok:
                time.sleep(2)
                continue

            try:
                session = response.json()
                phase = session.get('phase', 'Unknown')
                self.shared_state['phase'] = phase

                logger.debug(f"Phase: {phase}")

                if phase == 'ReadyCheck':
                    self._handle_ready_check()
                elif phase == 'ChampSelect':
                    self._handle_champ_select()
                elif phase in ('Matchmaking', 'Lobby', 'InProgress', 'WaitingForStats', 'PreEndOfGame', 'EndOfGame'):
                    time.sleep(2)
                else:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(2)

    def _handle_ready_check(self):
        """Accept the ready check."""
        logger.info("Accepting ready check")
        response = self.lcu.request('POST', 'lol-matchmaking/v1/ready-check/accept')
        if response and response.ok:
            logger.info("Ready check accepted")
        time.sleep(1)

    def _handle_champ_select(self):
        """Handle champion select phase."""
        response = self.lcu.request('GET', 'lol-champ-select/v1/session')
        if not response or not response.ok:
            return

        try:
            session = response.json()
            current_chat_room = session.get('chatDetails', {}).get('multiUserChatId', '')

            # Reset state if we're in a new champ select (detected by chat room change)
            if current_chat_room != self.last_chat_room or not self.last_chat_room:
                self.picked_champ = False
                self.locked_champ = False
                self.picked_ban = False
                self.locked_ban = False
                self.last_chat_room = current_chat_room
                self.champ_select_start = time.time() * 1000

            local_player_cell_id = session.get('localPlayerCellId')

            # Process actions
            if not (self.picked_champ and self.locked_champ and self.picked_ban and self.locked_ban):
                self._handle_actions(session, local_player_cell_id)

            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in champ select: {e}")

    def _handle_actions(self, session: Dict[str, Any], local_player_cell_id: int):
        """Process champ select actions."""
        actions = session.get('actions', [])
        timer = session.get('timer', {})

        # Flatten the 2D actions array
        flat_actions = []
        for action_list in actions:
            if isinstance(action_list, list):
                flat_actions.extend(action_list)

        for action in flat_actions:
            actor_cell_id = action.get('actorCellId')
            is_completed = action.get('completed', False)
            is_in_progress = action.get('isInProgress', False)

            # Only process our own actions
            if actor_cell_id != local_player_cell_id or is_completed:
                continue

            action_type = action.get('type')
            action_id = action.get('id')
            champion_id = action.get('championId', 0)

            if action_type == 'pick':
                self._handle_pick_action(action_id, champion_id, is_in_progress, timer)
            elif action_type == 'ban':
                self._handle_ban_action(action_id, champion_id, is_in_progress, timer)

    def _handle_pick_action(self, action_id: int, champion_id: int, is_in_progress: bool, timer: Dict[str, Any]):
        """Handle champion pick action."""
        if champion_id == 0:
            self.picked_champ = False

        # Check if we should hover
        phase = timer.get('phase', 'PLANNING')
        current_time = time.time() * 1000
        time_elapsed = current_time - self.champ_select_start

        should_hover = (
            time_elapsed > self.settings.pick_start_hover_delay
            or phase != 'PLANNING'
        )

        if not self.picked_champ and should_hover:
            champ_id = int(self.settings.champ_id)
            if champ_id > 0:
                self._hover_champion(action_id, champ_id, 'pick')

        if is_in_progress and not self.locked_champ:
            if self.settings.insta_lock:
                self._lock_champion(action_id, int(self.settings.champ_id), 'pick')
            else:
                self._check_lock_delay(action_id, int(self.settings.champ_id), timer, 'pick')

    def _handle_ban_action(self, action_id: int, champion_id: int, is_in_progress: bool, timer: Dict[str, Any]):
        """Handle champion ban action."""
        phase = timer.get('phase', 'PLANNING')

        if is_in_progress and phase != 'PLANNING':
            if not self.picked_ban:
                ban_id = int(self.settings.ban_id)
                if ban_id > 0:
                    self._hover_champion(action_id, ban_id, 'ban')

            if not self.locked_ban:
                if self.settings.insta_ban:
                    self._lock_champion(action_id, int(self.settings.ban_id), 'ban')
                else:
                    self._check_lock_delay(action_id, int(self.settings.ban_id), timer, 'ban')

    def _hover_champion(self, action_id: int, champion_id: int, action_type: str = 'pick'):
        """Hover a champion."""
        try:
            endpoint = f'lol-champ-select/v1/session/actions/{action_id}'
            response = self.lcu.request('PATCH', endpoint, {'championId': champion_id})
            if response and response.ok:
                logger.info(f"Hovered {action_type} champion {champion_id}")
                if action_type == 'pick':
                    self.picked_champ = True
                elif action_type == 'ban':
                    self.picked_ban = True
        except Exception as e:
            logger.error(f"Error hovering champion: {e}")

    def _lock_champion(self, action_id: int, champion_id: int, action_type: str = 'pick'):
        """Lock a champion."""
        try:
            endpoint = f'lol-champ-select/v1/session/actions/{action_id}'
            response = self.lcu.request('PATCH', endpoint, {
                'championId': champion_id,
                'completed': True
            })
            if response and response.ok:
                logger.info(f"Locked {action_type} {champion_id}")
                if action_type == 'pick':
                    self.locked_champ = True
                elif action_type == 'ban':
                    self.locked_ban = True
        except Exception as e:
            logger.error(f"Error locking champion: {e}")

    def _check_lock_delay(self, action_id: int, champion_id: int, timer: Dict[str, Any], action_type: str):
        """Check if it's time to lock based on configured delays."""
        total_time = timer.get('totalTimeInPhase', 0)
        remaining = timer.get('adjustedTimeLeftInPhase', 0)
        elapsed = total_time - remaining

        if action_type == 'pick':
            start_delay = self.settings.pick_start_lock_delay
            end_delay = self.settings.pick_end_lock_delay
        else:  # ban
            start_delay = self.settings.ban_start_lock_delay
            end_delay = self.settings.ban_end_lock_delay

        # Lock if time remaining is less than end_delay or elapsed time exceeds start_delay
        if remaining <= end_delay or elapsed >= start_delay:
            self._lock_champion(action_id, champion_id)

    def stop(self):
        """Stop the automation."""
        self.running = False
