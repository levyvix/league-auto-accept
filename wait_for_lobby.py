#!/usr/bin/env python3
"""Wait for Lobby phase then requeue."""

import sys
import time
from lcu import get_lcu_client


def wait_and_requeue():
    """Wait for Lobby phase to appear, then requeue."""
    print("Connecting to LCU client...")
    lcu = get_lcu_client()

    if not lcu:
        print("ERROR: Could not connect to League Client")
        return False

    print("Waiting for Lobby phase (checking every 2 seconds)...")
    max_wait = 60  # Wait up to 60 seconds
    start = time.time()

    while time.time() - start < max_wait:
        response = lcu.request("GET", "lol-gameflow/v1/session")
        if response and response.ok:
            phase = response.json().get("phase", "Unknown")
            print(f"Current phase: {phase}")

            if phase == "Lobby":
                print("\nLobby phase detected! Requeuing...")
                response = lcu.request("POST", "lol-lobby/v2/lobby/matchmaking/search")
                print(
                    f"Requeue response: status={response.status_code if response else None}"
                )
                if response and response.ok:
                    print("SUCCESS: Requeue sent!")
                    return True
                else:
                    print("FAILED: Requeue failed")
                    return False
        time.sleep(2)

    print(f"TIMEOUT: Lobby never appeared after {max_wait} seconds")
    return False


if __name__ == "__main__":
    success = wait_and_requeue()
    sys.exit(0 if success else 1)
