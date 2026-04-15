import logging
from typing import List, Optional

from lcu import LCUClient

logger = logging.getLogger(__name__)


class ChampionInfo:
    """Champion data."""

    def __init__(self, name: str, id_: str, owned: bool = False):
        self.name = name
        self.id = id_
        self.owned = owned

    def __repr__(self):
        return f"Champion({self.name}, {self.id}, owned={self.owned})"


def load_summoner_id(lcu: LCUClient) -> Optional[int]:
    """
    Load the current summoner ID.

    Args:
        lcu: LCUClient instance

    Returns: Summoner ID or None
    """
    response = lcu.request("GET", "lol-summoner/v1/current-summoner")
    if response and response.ok:
        try:
            data = response.json()
            summoner_id = data.get("summonerId")
            logger.info(f"Loaded summoner ID: {summoner_id}")
            return summoner_id
        except Exception as e:
            logger.error(f"Error parsing summoner ID: {e}")
    return None


def load_champions(lcu: LCUClient, summoner_id: int) -> List[ChampionInfo]:
    """
    Load all available champions.

    Args:
        lcu: LCUClient instance
        summoner_id: Current summoner ID

    Returns: Sorted list of ChampionInfo (excluding bot variants)
    """
    endpoint = f"lol-champions/v1/inventories/{summoner_id}/champions-minimal"
    response = lcu.request("GET", endpoint)
    if response and response.ok:
        try:
            champs_data = response.json()
            champions = []
            for champ in champs_data:
                name = champ.get("name", "")
                # Skip None and bot variants
                if name == "None" or "Bot" in name:
                    continue
                owned = (
                    champ.get("ownership", {}).get("owned", False)
                    or champ.get("ownership", {}).get("xboxGPReward", False)
                    or champ.get("freeToPlay", False)
                )
                champions.append(
                    ChampionInfo(name=name, id_=str(champ.get("id")), owned=owned)
                )
            champions.sort(key=lambda c: c.name)
            logger.info(f"Loaded {len(champions)} champions")
            return champions
        except Exception as e:
            logger.error(f"Error parsing champions: {e}")
    return []


def load_summoner_spells(lcu: LCUClient) -> List[dict]:
    """
    Load available summoner spells.

    Args:
        lcu: LCUClient instance

    Returns: List of spell dicts with 'name' and 'id' keys
    """
    response = lcu.request("GET", "lol-game-data/assets/v1/summoner-spells.json")
    if response and response.ok:
        try:
            spells = response.json()
            spell_list = []
            for spell in spells:
                spell_list.append(
                    {"name": spell.get("name"), "id": str(spell.get("id"))}
                )
            spell_list.sort(key=lambda s: s["name"])
            logger.info(f"Loaded {len(spell_list)} summoner spells")
            return spell_list
        except Exception as e:
            logger.error(f"Error parsing summoner spells: {e}")
    return []
