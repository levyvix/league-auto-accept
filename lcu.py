import base64
import logging
import re
import time
from typing import Optional, Dict, Any

import psutil
import requests
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def find_lcu_process() -> Optional[psutil.Process]:
    """Find the LeagueClientUx process."""
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] == "LeagueClientUx.exe":
                return psutil.Process(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def parse_auth_from_cmdline(proc: psutil.Process) -> Optional[tuple[str, str]]:
    """
    Extract port and auth token from LeagueClientUx process command line.
    Returns: (port, base64_auth_header) or None if parsing fails.
    """
    try:
        # Get the full command line
        cmdline = proc.cmdline()
        cmdline_str = " ".join(cmdline)

        # Extract port
        port_match = re.search(r'--app-port="?(\d+)"?', cmdline_str)
        if not port_match:
            logger.warning("Could not find app port in cmdline")
            return None
        port = port_match.group(1)

        # Extract auth token
        token_match = re.search(r"--remoting-auth-token=([a-zA-Z0-9_-]+)", cmdline_str)
        if not token_match:
            logger.warning("Could not find auth token in cmdline")
            return None
        token = token_match.group(1)

        # Build basic auth header
        auth_str = f"riot:{token}"
        auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

        logger.info(f"Parsed LCU auth: port={port}")
        return port, auth_b64
    except Exception as e:
        logger.error(f"Error parsing auth from cmdline: {e}")
        return None


class LCUClient:
    """HTTP client for League Client Update API."""

    def __init__(self, port: str, auth_header: str):
        self.base_url = f"https://127.0.0.1:{port}"
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(
            {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json",
            }
        )

    def request(
        self, method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None
    ) -> Optional[requests.Response]:
        """
        Make a request to LCU.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE, etc.)
            endpoint: API endpoint (e.g., 'lol-gameflow/v1/session')
            json_data: JSON body (optional)

        Returns: Response object or None on error
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.request(method, url, json=json_data)
            logger.debug(f"{method} {endpoint}: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Request failed: {method} {endpoint}: {e}")
            return None

    def request_until_success(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Optional[requests.Response]:
        """
        Retry a request until it succeeds or timeout.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json_data: JSON body (optional)
            timeout: Max seconds to retry

        Returns: Response object or None on timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.request(method, endpoint, json_data)
            if response and response.ok:
                return response
            time.sleep(1)
        logger.warning(f"Request timed out: {method} {endpoint}")
        return None

    def is_client_open(self) -> bool:
        """Check if the League Client is still open."""
        response = self.request("GET", "lol-gameflow/v1/session")
        return response is not None and response.ok


def get_lcu_client() -> Optional[LCUClient]:
    """
    Find the League Client process and create an LCUClient.

    Returns: LCUClient instance or None if process not found.
    """
    proc = find_lcu_process()
    if not proc:
        logger.debug("LeagueClientUx process not found")
        return None

    auth_info = parse_auth_from_cmdline(proc)
    if not auth_info:
        return None

    port, auth_header = auth_info
    return LCUClient(port, auth_header)
