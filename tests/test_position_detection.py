from main_logic import AutoAccept
from settings import Settings


class FakeLCU:
    def __init__(self, lobby=None):
        self.lobby = lobby

    def request(self, method, endpoint, json_data=None):
        if method == "GET" and endpoint == "lol-lobby/v2/lobby" and self.lobby:
            return FakeResponse(self.lobby)
        return None


class FakeResponse:
    ok = True

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def make_auto_accept() -> AutoAccept:
    settings = Settings(
        champ_id="10",
        backup_champ_id="11",
        secondary_champ_id="20",
        secondary_backup_champ_id="21",
    )
    return AutoAccept(FakeLCU(), settings)  # type: ignore[arg-type]


def test_saved_primary_position_uses_primary_champion_pool():
    automation = make_auto_accept()
    automation.settings.primary_position = "MIDDLE"
    automation.settings.secondary_position = "BOTTOM"
    automation.assigned_position = "MIDDLE"

    assert automation._get_pick_candidates() == [10, 11]


def test_saved_secondary_position_uses_secondary_champion_pool():
    automation = make_auto_accept()
    automation.settings.primary_position = "MIDDLE"
    automation.settings.secondary_position = "BOTTOM"
    automation.assigned_position = "BOTTOM"

    assert automation._get_pick_candidates() == [20, 21]


def test_autofill_does_not_select_a_champion():
    automation = make_auto_accept()
    automation.settings.primary_position = "MIDDLE"
    automation.settings.secondary_position = "BOTTOM"
    automation.assigned_position = "TOP"

    assert automation._get_pick_candidates() == []


def test_missing_position_does_not_default_to_primary_pool_in_classic_queue():
    automation = make_auto_accept()
    session = {
        "localPlayerCellId": 3,
        "myTeam": [{"cellId": 3, "assignedPosition": ""}],
    }

    automation.assigned_position = automation._get_assigned_position(session, 3)

    assert automation.assigned_position == ""
    assert automation._get_pick_candidates() == []


def test_position_detection_accepts_string_cell_id_and_alias():
    automation = make_auto_accept()
    session = {
        "localPlayerCellId": 3,
        "myTeam": [{"cellId": "3", "assignedPosition": "support"}],
    }

    position = automation._get_assigned_position(session, 3)

    assert position == "UTILITY"


def test_roleless_mode_keeps_primary_pool_fallback():
    automation = make_auto_accept()
    automation.current_game_mode = "ARAM"

    assert automation._get_pick_candidates() == [10, 11]


def test_custom_classic_game_keeps_primary_pool_fallback():
    automation = make_auto_accept()
    automation.is_custom_game = True

    assert automation._get_pick_candidates() == [10, 11]


def test_lobby_position_preferences_are_saved():
    lobby = {
        "localMember": {
            "firstPositionPreference": "middle",
            "secondPositionPreference": "bottom",
        }
    }
    settings = Settings()
    automation = AutoAccept(FakeLCU(lobby), settings)  # type: ignore[arg-type]
    saved = []
    automation.on_settings_changed = lambda: saved.append(True)

    automation._refresh_position_preferences()

    assert settings.primary_position == "MIDDLE"
    assert settings.secondary_position == "BOTTOM"
    assert saved == [True]


def test_nested_lobby_position_preferences_are_supported():
    lobby = {
        "localMember": {
            "positionPreferences": {
                "firstPreference": "utility",
                "secondPreference": "jungle",
            }
        }
    }
    settings = Settings()
    automation = AutoAccept(FakeLCU(lobby), settings)  # type: ignore[arg-type]

    automation._refresh_position_preferences()

    assert settings.primary_position == "UTILITY"
    assert settings.secondary_position == "JUNGLE"
