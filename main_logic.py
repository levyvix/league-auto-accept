import logging
import time
from typing import Dict, Any, Optional, Callable

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
        self.assigned_position: str = ""
        self.current_game_mode: str = "CLASSIC"
        self.is_custom_game: bool = False
        self.selected_pick_champion_id: int = 0
        self._last_swap_signature: str = ""

        # End-of-game requeue state
        self.came_from_game: bool = False
        self._honor_skipped: bool = False
        self._last_phase: str = ""
        self._requeue_triggered_in_lobby: bool = False
        self._is_searching_for_match: bool = (
            False  # Track if we're actively in matchmaking search
        )
        self._search_start_time: float = 0  # When we started matchmaking search

        # State shared with UI
        self.shared_state = {
            "phase": "Unknown",
            "is_auto_accept_on": settings.auto_accept_on,
            "auto_requeue": settings.auto_requeue,
        }

        # Callback for saving settings
        self.on_settings_changed: Optional[Callable[[], None]] = None

    def run(self):
        """Main loop for automation."""
        while self.running:
            response = self.lcu.request("GET", "lol-gameflow/v1/session")
            if not response or not response.ok:
                time.sleep(2)
                continue

            try:
                session = response.json()
                phase = session.get("phase", "Unknown")
                self.shared_state["phase"] = phase
                self.shared_state["auto_requeue"] = self.settings.auto_requeue

                # Log every phase for debugging
                logger.info(
                    f"PHASE CHECK: {phase} (last={self._last_phase}, came_from_game={self.came_from_game}, auto_requeue={self.settings.auto_requeue})"
                )

                if phase in ("Lobby", "Matchmaking", "ReadyCheck"):
                    self._refresh_position_preferences()

                # Handle auto-requeue even if auto_accept is off
                if phase in ("InProgress", "WaitingForStats"):
                    self.came_from_game = True
                    self._honor_skipped = False
                elif phase == "PreEndOfGame":
                    self.came_from_game = True
                    if self.settings.auto_requeue:
                        self._handle_pre_end_of_game()
                        self._handle_requeue()
                elif phase == "EndOfGame":
                    self.came_from_game = True
                    if self.settings.auto_requeue:
                        self._handle_requeue()
                elif phase == "Lobby":
                    # Check if user cancelled an active matchmaking search
                    # Auto-requeue when in Lobby (after game OR on app startup if first in session)
                    # Only skip if we just cancelled matchmaking (detected by _check_matchmaking_status)
                    if (
                        self.settings.auto_requeue
                        and not self._requeue_triggered_in_lobby
                    ):
                        self._handle_requeue()
                        self._requeue_triggered_in_lobby = True
                elif phase == "Matchmaking":
                    self.came_from_game = False
                    # Reset requeue flag when leaving Lobby
                    self._requeue_triggered_in_lobby = False
                else:
                    # Reset requeue flag when entering any other phase
                    self._requeue_triggered_in_lobby = False

                if phase == "ChampSelect" and (
                    self.settings.auto_accept_on or self.settings.auto_swap_accept
                ):
                    self._handle_champ_select()

                # Only handle ready-check accept if auto_accept is on
                if self.settings.auto_accept_on and phase == "ReadyCheck":
                    self._is_searching_for_match = (
                        False  # Queue popped, no longer searching
                    )
                    self._handle_ready_check()

                # Track the previous phase for detecting state transitions
                self._last_phase = phase

                time.sleep(
                    2
                    if phase
                    in (
                        "InProgress",
                        "WaitingForStats",
                        "EndOfGame",
                        "Lobby",
                        "Matchmaking",
                        "PreEndOfGame",
                    )
                    else 1
                )

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(2)

    def _handle_ready_check(self):
        """Accept the ready check."""
        logger.info("Accepting ready check")
        response = self.lcu.request("POST", "lol-matchmaking/v1/ready-check/accept")
        if response and response.ok:
            logger.info("Ready check accepted")
        time.sleep(1)

    def _handle_champ_select(self):
        """Handle champion select phase."""
        response = self.lcu.request("GET", "lol-champ-select/v1/session")
        if not response or not response.ok:
            return

        try:
            session = response.json()
            current_chat_room = session.get("chatDetails", {}).get(
                "multiUserChatId", ""
            )

            # Reset state if we're in a new champ select (detected by chat room change)
            if current_chat_room != self.last_chat_room or not self.last_chat_room:
                self.picked_champ = False
                self.locked_champ = False
                self.picked_ban = False
                self.locked_ban = False
                self.selected_pick_champion_id = 0
                self._last_swap_signature = ""
                self.assigned_position = ""
                self.last_chat_room = current_chat_room
                self.champ_select_start = time.time() * 1000
                self.current_game_mode = self._fetch_game_mode()

            local_player_cell_id = session.get("localPlayerCellId")
            self.is_custom_game = bool(session.get("isCustomGame", False))
            detected_position = self._get_assigned_position(
                session, local_player_cell_id
            )
            if detected_position and detected_position != self.assigned_position:
                self.assigned_position = detected_position
                logger.info(f"Assigned position detected: {self.assigned_position}")

            self._handle_pick_order_swaps(
                session,
                local_player_cell_id=local_player_cell_id,
                auto_accept_enabled=self.settings.auto_swap_accept,
            )

            # Process pick/ban actions only when auto-accept automation is enabled.
            if self.settings.auto_accept_on and not (
                self.picked_champ
                and self.locked_champ
                and self.picked_ban
                and self.locked_ban
            ):
                self._handle_actions(session, local_player_cell_id)

            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in champ select: {e}")

    def _handle_actions(self, session: Dict[str, Any], local_player_cell_id: int):
        """Process champ select actions."""
        actions = session.get("actions", [])
        timer = session.get("timer", {})

        # Flatten the 2D actions array
        flat_actions = []
        for action_list in actions:
            if isinstance(action_list, list):
                flat_actions.extend(action_list)

        for action in flat_actions:
            actor_cell_id = action.get("actorCellId")
            is_completed = action.get("completed", False)
            is_in_progress = action.get("isInProgress", False)

            # Only process our own actions
            if actor_cell_id != local_player_cell_id or is_completed:
                continue

            action_type = action.get("type")
            action_id = action.get("id")
            champion_id = action.get("championId", 0)

            if action_type == "pick":
                self._handle_pick_action(action_id, champion_id, is_in_progress, timer)
            elif action_type == "ban":
                self._handle_ban_action(action_id, is_in_progress, timer)

    def _handle_pick_action(
        self,
        action_id: int,
        champion_id: int,
        is_in_progress: bool,
        timer: Dict[str, Any],
    ):
        """Handle champion pick action."""
        if champion_id == 0:
            self.picked_champ = False
            self.selected_pick_champion_id = 0
        elif self.selected_pick_champion_id == 0:
            self.selected_pick_champion_id = champion_id

        # Check if we should hover
        phase = timer.get("phase", "PLANNING")
        current_time = time.time() * 1000
        time_elapsed = current_time - self.champ_select_start

        should_hover = (
            time_elapsed > self.settings.pick_start_hover_delay or phase != "PLANNING"
        )

        if not self.picked_champ and should_hover:
            for champ_id in self._get_pick_candidates():
                if self._hover_champion(action_id, champ_id, "pick"):
                    self.selected_pick_champion_id = champ_id
                    break

        if is_in_progress and not self.locked_champ:
            champ_id = self._get_pick_champion_to_lock(champion_id)
            if champ_id <= 0:
                return
            if self.settings.insta_lock:
                self._lock_champion(action_id, champ_id, "pick")
            else:
                self._check_lock_delay(action_id, champ_id, timer, "pick")

    def _handle_ban_action(
        self,
        action_id: int,
        is_in_progress: bool,
        timer: Dict[str, Any],
    ):
        """Handle champion ban action."""
        phase = timer.get("phase", "PLANNING")

        if is_in_progress and phase != "PLANNING":
            if not self.picked_ban:
                ban_id = int(self.settings.ban_id)
                if ban_id > 0:
                    self._hover_champion(action_id, ban_id, "ban")

            if not self.locked_ban:
                if self.settings.insta_ban:
                    self._lock_champion(action_id, int(self.settings.ban_id), "ban")
                else:
                    self._check_lock_delay(
                        action_id, int(self.settings.ban_id), timer, "ban"
                    )

    def _handle_pick_order_swaps(
        self,
        session: Dict[str, Any],
        local_player_cell_id: int,
        auto_accept_enabled: bool,
    ):
        """Log and optionally accept incoming pick-order swap requests."""
        swaps = session.get("swaps")
        if not isinstance(swaps, list):
            swaps = None

        # Fallback for clients/builds where swaps are not embedded in session payload.
        if swaps is None:
            swaps_response = self.lcu.request(
                "GET", "lol-champ-select/v1/session/swaps"
            )
            if swaps_response and swaps_response.ok:
                try:
                    response_data = swaps_response.json()
                except ValueError:
                    response_data = []
                if isinstance(response_data, list):
                    swaps = response_data
                else:
                    logger.warning(
                        f"Unexpected swaps endpoint payload type: {type(response_data).__name__}"
                    )
                    swaps = []
            else:
                swaps = []
        elif not swaps:
            # Small fallback retry when session payload has an empty swaps field.
            swaps_response = self.lcu.request(
                "GET", "lol-champ-select/v1/session/swaps"
            )
            if swaps_response and swaps_response.ok:
                try:
                    response_data = swaps_response.json()
                except ValueError:
                    response_data = []
                if isinstance(response_data, list):
                    swaps = response_data

        # Log only when the swaps snapshot changes to avoid log spam every poll.
        signature_items = []
        for swap in swaps:
            if isinstance(swap, dict):
                signature_items.append(
                    f"{swap.get('id')}:{swap.get('state')}:{swap.get('direction')}:"
                    f"{swap.get('fromCellId')}->{swap.get('toCellId')}"
                )
        signature = "|".join(signature_items)
        if signature != self._last_swap_signature:
            received_count = sum(
                1
                for swap in swaps
                if self._is_incoming_swap(swap, local_player_cell_id)
            )
            logger.info(
                f"Pick-order swap snapshot changed: total={len(swaps)} incoming={received_count} "
                f"details=[{signature}]"
            )
            self._last_swap_signature = signature

        if not swaps:
            return

        for swap in swaps:
            if not self._is_incoming_swap(swap, local_player_cell_id):
                continue
            swap_id = swap.get("id")
            if not auto_accept_enabled:
                logger.info(
                    f"Incoming pick-order swap detected (id={swap_id}), "
                    "auto-swap accept is disabled"
                )
                continue
            logger.info(f"Attempting to accept pick-order swap (id={swap_id})")
            endpoint = f"lol-champ-select/v1/session/swaps/{swap_id}/accept"
            response = self.lcu.request("POST", endpoint)
            if response and response.ok:
                logger.info(f"Auto-accepted pick-order swap (id={swap_id})")
            else:
                status = response.status_code if response else "None"
                logger.warning(f"Failed to accept swap (id={swap_id}): status={status}")

    def _is_incoming_swap(
        self, swap: Dict[str, Any], local_player_cell_id: Optional[int] = None
    ) -> bool:
        """Return True when swap entry represents an incoming offer to local player."""
        if not isinstance(swap, dict):
            return False
        state = str(swap.get("state", "")).upper()
        direction = str(swap.get("direction", "")).upper()

        incoming_directions = {"RECEIVED", "INCOMING"}
        if direction in incoming_directions:
            return True

        # Some LCU payloads expose incoming/outgoing through target/source cell ids.
        if isinstance(local_player_cell_id, int):
            target_keys = ("toCellId", "receiverCellId", "targetCellId")
            for key in target_keys:
                value = swap.get(key)
                if isinstance(value, int) and value == local_player_cell_id:
                    return True

        # Conservative fallback: only treat RECEIVED as incoming without target info.
        return state == "RECEIVED"

    def _hover_champion(
        self, action_id: int, champion_id: int, action_type: str = "pick"
    ) -> bool:
        """Hover a champion."""
        try:
            endpoint = f"lol-champ-select/v1/session/actions/{action_id}"
            response = self.lcu.request("PATCH", endpoint, {"championId": champion_id})
            if response and response.ok:
                logger.info(f"Hovered {action_type} champion {champion_id}")
                if action_type == "pick":
                    self.picked_champ = True
                    self.selected_pick_champion_id = champion_id
                elif action_type == "ban":
                    self.picked_ban = True
                return True
            logger.info(
                f"Failed to hover {action_type} champion {champion_id}: "
                f"status={response.status_code if response else 'None'}"
            )
        except Exception as e:
            logger.error(f"Error hovering champion: {e}")
        return False

    def _lock_champion(
        self, action_id: int, champion_id: int, action_type: str = "pick"
    ) -> bool:
        """Lock a champion."""
        try:
            endpoint = f"lol-champ-select/v1/session/actions/{action_id}"
            response = self.lcu.request(
                "PATCH", endpoint, {"championId": champion_id, "completed": True}
            )
            if response and response.ok:
                logger.info(f"Locked {action_type} {champion_id}")
                if action_type == "pick":
                    self.locked_champ = True
                    self.selected_pick_champion_id = champion_id
                elif action_type == "ban":
                    self.locked_ban = True
                return True
            logger.info(
                f"Failed to lock {action_type} champion {champion_id}: "
                f"status={response.status_code if response else 'None'}"
            )
        except Exception as e:
            logger.error(f"Error locking champion: {e}")
        return False

    def _check_lock_delay(
        self, action_id: int, champion_id: int, timer: Dict[str, Any], action_type: str
    ):
        """Check if it's time to lock based on configured delays."""
        total_time = timer.get("totalTimeInPhase", 0)
        remaining = timer.get("adjustedTimeLeftInPhase", 0)
        elapsed = total_time - remaining

        if action_type == "pick":
            start_delay = self.settings.pick_start_lock_delay
            end_delay = self.settings.pick_end_lock_delay
        else:  # ban
            start_delay = self.settings.ban_start_lock_delay
            end_delay = self.settings.ban_end_lock_delay

        # Lock if time remaining is less than end_delay or elapsed time exceeds start_delay
        if remaining <= end_delay or elapsed >= start_delay:
            self._lock_champion(action_id, champion_id, action_type)

    def _get_pick_candidates(self) -> list[int]:
        """Return the ordered list of configured pick candidates for the current role."""
        position = self.assigned_position
        if not position:
            if self.current_game_mode == "CLASSIC" and not self.is_custom_game:
                logger.info(
                    "Assigned position is not available yet; postponing champion selection"
                )
                return []
            position = "UTILITY"

        use_primary_pool = self._uses_primary_champion_pool(position)
        if use_primary_pool is None:
            return []

        if use_primary_pool:
            candidates = [
                self.settings.champ_id,
                self.settings.backup_champ_id,
            ]
            logger.info(f"Using primary champion pool for assigned position {position}")
        else:
            candidates = [
                self.settings.secondary_champ_id,
                self.settings.secondary_backup_champ_id,
            ]
            logger.info(
                f"Using secondary champion pool for assigned position {position}"
            )

        result: list[int] = []
        for champ_id in candidates:
            try:
                champ_int = int(champ_id)
            except (TypeError, ValueError):
                continue
            if champ_int > 0 and champ_int not in result:
                result.append(champ_int)
        return result

    def _uses_primary_champion_pool(self, assigned_position: str) -> Optional[bool]:
        """Match the assigned position against the saved lobby preferences."""
        primary_position = self._normalize_position_preference(
            self.settings.primary_position
        )
        secondary_position = self._normalize_position_preference(
            self.settings.secondary_position
        )

        if primary_position == "FILL" or assigned_position == primary_position:
            return True
        if assigned_position == secondary_position:
            return False
        if primary_position:
            logger.warning(
                f"Assigned position {assigned_position} does not match saved "
                f"preferences ({primary_position}, {secondary_position or 'NONE'}); "
                "skipping automatic champion selection for autofill"
            )
            return None

        # Backwards-compatible fallback until lobby preferences are captured.
        return assigned_position == "UTILITY"

    def _get_pick_champion_to_lock(self, current_action_champion_id: int) -> int:
        """Choose which champion should be locked for the current pick action."""
        if self.selected_pick_champion_id > 0:
            return self.selected_pick_champion_id
        if current_action_champion_id > 0:
            return current_action_champion_id
        candidates = self._get_pick_candidates()
        return candidates[0] if candidates else 0

    def _fetch_game_mode(self) -> str:
        """Fetch the current game mode from the gameflow session."""
        response = self.lcu.request("GET", "lol-gameflow/v1/session")
        if response and response.ok:
            try:
                data = response.json()
                mode = data.get("gameData", {}).get("queue", {}).get("gameMode", "")
                if mode:
                    return mode.upper()
            except Exception:
                pass
        return "CLASSIC"

    def _refresh_position_preferences(self):
        """Capture and persist the local player's current lobby position choices."""
        response = self.lcu.request("GET", "lol-lobby/v2/lobby")
        if not response or not response.ok:
            return

        try:
            lobby = response.json()
        except (TypeError, ValueError):
            return
        if not isinstance(lobby, dict):
            return

        local_member = lobby.get("localMember", {})
        if not isinstance(local_member, dict):
            return

        position_preferences = local_member.get("positionPreferences", {})
        if not isinstance(position_preferences, dict):
            position_preferences = {}

        first_position = self._normalize_position_preference(
            local_member.get("firstPositionPreference")
            or position_preferences.get("firstPreference")
        )
        second_position = self._normalize_position_preference(
            local_member.get("secondPositionPreference")
            or position_preferences.get("secondPreference")
        )
        if not first_position:
            return

        if (
            first_position == self.settings.primary_position
            and second_position == self.settings.secondary_position
        ):
            return

        self.settings.primary_position = first_position
        self.settings.secondary_position = second_position
        logger.info(
            f"Saved lobby position preferences: primary={first_position}, "
            f"secondary={second_position or 'NONE'}"
        )
        if self.on_settings_changed:
            self.on_settings_changed()

    def _get_assigned_position(
        self, session: Dict[str, Any], local_player_cell_id: Any
    ) -> str:
        """Get the assigned position for the local player."""
        for player in session.get("myTeam", []):
            if not isinstance(player, dict):
                continue
            if str(player.get("cellId")) != str(local_player_cell_id):
                continue
            for position_key in (
                "assignedPosition",
                "position",
                "selectedPosition",
            ):
                position = self._normalize_position(player.get(position_key))
                if position:
                    return position
        return ""

    @staticmethod
    def _normalize_position(position: Any) -> str:
        """Normalize LCU position names and keep missing values unknown."""
        if not isinstance(position, str):
            return ""

        normalized = position.strip().upper()
        aliases = {
            "ADC": "BOTTOM",
            "BOT": "BOTTOM",
            "MID": "MIDDLE",
            "SUPPORT": "UTILITY",
            "SUP": "UTILITY",
        }
        normalized = aliases.get(normalized, normalized)
        valid_positions = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
        return normalized if normalized in valid_positions else ""

    @classmethod
    def _normalize_position_preference(cls, position: Any) -> str:
        """Normalize a lobby position preference, including the fill option."""
        normalized = cls._normalize_position(position)
        if normalized:
            return normalized
        if isinstance(position, str) and position.strip().upper() == "FILL":
            return "FILL"
        return ""

    def _handle_pre_end_of_game(self):
        """Skip honor vote during PreEndOfGame phase."""
        if self._honor_skipped:
            time.sleep(2)
            return
        logger.info("Skipping honor vote")
        response = self.lcu.request("POST", "lol-honor-v2/v1/skip-honor-vote")
        if response and response.ok:
            logger.info("Honor vote skipped")
            self._honor_skipped = True
        time.sleep(2)

    def _handle_requeue(self):
        """Start matchmaking after returning to lobby post-game."""
        logger.info("Auto-requeue: clicking Play Again")
        response = self.lcu.request("POST", "lol-lobby/v2/play-again")
        if response and response.ok:
            logger.info("Play Again clicked")
        else:
            logger.warning(
                f"Play Again failed: status={response.status_code if response else 'None'}"
            )
            time.sleep(2)
            return

        time.sleep(0.5)

        logger.info("Auto-requeue: starting matchmaking search")
        response = self.lcu.request("POST", "lol-lobby/v2/lobby/matchmaking/search")
        if response and response.ok:
            logger.info("Matchmaking search started")
            self._is_searching_for_match = True
            self._search_start_time = time.time()
            self.came_from_game = False
        else:
            logger.warning(
                f"Requeue failed: status={response.status_code if response else 'None'}"
            )
        time.sleep(2)

    def stop(self):
        """Stop the automation."""
        self.running = False
