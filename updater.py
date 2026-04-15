import sys
import subprocess
import tempfile
import msvcrt
from pathlib import Path

import requests
from rich.console import Console

from version import __version__

GITHUB_REPO = "levyvix/league-auto-accept"
TAG_PREFIX = "league-auto-accept-v"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse version string like '0.1.1' into tuple (0, 1, 1)."""
    return tuple(int(x) for x in tag.lstrip(TAG_PREFIX).split("."))


def check_for_updates(console: Console) -> None:
    """Check GitHub for a newer release and notify user."""
    try:
        resp = requests.get(
            API_URL, timeout=5, headers={"Accept": "application/vnd.github+json"}
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return  # silently skip if no network or rate-limited

    tag: str = data.get("tag_name", "")
    if not tag.startswith(TAG_PREFIX):
        return

    try:
        remote = _parse_version(tag)
        local = _parse_version(__version__)
    except ValueError:
        return

    if remote <= local:
        return  # already up-to-date

    remote_str = tag[len(TAG_PREFIX) :]

    # Find the .exe asset
    assets = data.get("assets", [])
    exe_asset = next((a for a in assets if a["name"].endswith(".exe")), None)
    if not exe_asset:
        return

    # Just notify, don't block
    console.print(
        f"\n[bold yellow]Update available:[/bold yellow] v{__version__} -> v{remote_str}"
    )
    console.print("[yellow]Press 'U' in the main menu to update[/yellow]\n")


def check_for_updates_interactive(console: Console) -> None:
    """Interactive update check - called when user presses U in menu."""
    try:
        resp = requests.get(
            API_URL, timeout=5, headers={"Accept": "application/vnd.github+json"}
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        console.print(f"[red]Failed to check for updates: {e}[/red]")
        return

    tag: str = data.get("tag_name", "")
    if not tag.startswith(TAG_PREFIX):
        return

    try:
        remote = _parse_version(tag)
        local = _parse_version(__version__)
    except ValueError:
        return

    if remote <= local:
        console.print(f"[green]Already up-to-date (v{__version__})[/green]")
        return

    remote_str = tag[len(TAG_PREFIX) :]

    # Find the .exe asset
    assets = data.get("assets", [])
    exe_asset = next((a for a in assets if a["name"].endswith(".exe")), None)
    if not exe_asset:
        console.print("[red]No release asset found[/red]")
        return

    console.print(
        f"[bold yellow]Update available:[/bold yellow] v{__version__} -> v{remote_str}"
    )
    console.print("Download and apply now? [Y/N] ", end="")

    while True:
        ch = msvcrt.getch()
        key = ch.decode("utf-8", errors="ignore").upper()
        if key == "Y":
            console.print("Y")
            break
        if key in ("N", "\r", "\x1b"):
            console.print("N")
            return

    _apply_update(console, exe_asset["browser_download_url"])


def _apply_update(console: Console, url: str) -> None:
    """Download update and apply via detached bat script."""
    console.print("[cyan]Downloading update...[/cyan]")

    current_exe = Path(sys.executable)
    new_exe = current_exe.with_suffix(".new.exe")

    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(new_exe, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        new_exe.unlink(missing_ok=True)
        return

    # Write a bat script that waits for this process to exit,
    # moves new exe over old exe, and relaunches.
    bat_content = (
        "@echo off\n"
        f'set "old_exe={current_exe}"\n'
        f'set "new_exe={new_exe}"\n'
        "REM Wait for the Python process to fully exit\n"
        "timeout /T 2 /NOBREAK >NUL\n"
        "REM Replace the old exe with the new one\n"
        'move /Y "%new_exe%" "%old_exe%"\n'
        "REM Relaunch the app\n"
        'if exist "%old_exe%" (\n'
        '    start "" "%old_exe%"\n'
        ")\n"
        "REM Delete this bat file\n"
        'del /Q "%~f0"\n'
    )
    bat_path = Path(tempfile.mktemp(suffix=".bat"))
    bat_path.write_text(bat_content)

    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    console.print("[green]Update downloaded. Relaunching...[/green]")
    sys.exit(0)
