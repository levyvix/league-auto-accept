import logging
import msvcrt
import time
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.align import Align

from data import ChampionInfo

logger = logging.getLogger(__name__)


class UIManager:
    """Handles terminal UI using Rich."""

    def __init__(self):
        self.console = Console()
        self.running = True
        self.champions: List[ChampionInfo] = []
        self.current_selection = 0
        self.search_filter = ""

    def build_main_screen(self, settings, shared_state) -> Panel:
        """Build the main status screen panel."""
        phase = shared_state.get("phase", "Unknown")
        auto_accept_status = (
            "[bold green]ON[/bold green]"
            if settings.auto_accept_on
            else "[bold red]OFF[/bold red]"
        )

        info_lines = [
            f"Auto-Accept: {auto_accept_status}",
            f"Champion: {settings.champ_name}",
            f"Backup: {settings.backup_champ_name}",
            f"Ban: {settings.ban_name}",
            f"Game Phase: {phase}",
            "",
            "[bold]Controls:[/bold]",
            "[cyan]1[/cyan] - Toggle auto-accept",
            "[cyan]2[/cyan] - Set champion",
            "[cyan]3[/cyan] - Set ban",
            "[cyan]4[/cyan] - Settings",
            "[cyan]Q[/cyan] - Quit",
        ]

        return Panel(
            "\n".join(info_lines),
            border_style="blue",
            padding=(1, 2),
            title="[bold]League Auto Accept[/bold]",
        )

    def build_waiting_screen(self) -> Panel:
        """Build waiting for client screen."""
        return Panel(
            Align.center("[bold yellow]Waiting for League Client...[/bold yellow]"),
            border_style="yellow",
            padding=(2, 4),
        )

    def build_champion_picker(
        self, title: str = "Select Champion", recent_ids: Optional[List[str]] = None
    ) -> Tuple[Panel, List[ChampionInfo]]:
        """Build champion picker screen. Returns (panel, filtered_list)."""
        if recent_ids is None:
            recent_ids = []

        # Split recent from all
        recent_champs = [c for c in self.champions if c.id in recent_ids]
        all_champs = [c for c in self.champions if c.id not in recent_ids]

        # Apply filter to all (not recent)
        filtered_all = [
            c for c in all_champs if self.search_filter.lower() in c.name.lower()
        ]

        # Combine: recently used (always shown) + filtered
        if not self.search_filter:
            # No filter: show recent + all others
            filtered = recent_champs + all_champs
        else:
            # With filter: show recent that match + filtered
            filtered_recent = [
                c for c in recent_champs if self.search_filter.lower() in c.name.lower()
            ]
            filtered = filtered_recent + filtered_all

        if not filtered:
            return Panel(
                f"[red]No champions found for '{self.search_filter}'[/red]",
                border_style="red",
            ), []

        self.current_selection = min(self.current_selection, len(filtered) - 1)
        self.current_selection = max(self.current_selection, 0)

        # Build list
        lines = [
            "[dim]Type to filter, arrows to select, Enter to confirm, Esc to cancel[/dim]",
            "",
        ]

        # Show recent section
        if recent_champs and not self.search_filter:
            lines.append("[bold magenta]Recently Used[/bold magenta]")
            for i, champ in enumerate(recent_champs):
                if i == self.current_selection:
                    lines.append(f"[bold green]> {champ.name}[/bold green]")
                else:
                    lines.append(f"  {champ.name}")
            lines.append("")
            lines.append("[dim]All Champions[/dim]")

        # Show all champions
        start_idx = (
            len(recent_champs) if (recent_champs and not self.search_filter) else 0
        )
        for i, champ in enumerate(
            filtered[start_idx : start_idx + 15]
        ):  # Show max 15 more
            actual_idx = start_idx + i
            if actual_idx == self.current_selection:
                lines.append(f"[bold green]> {champ.name}[/bold green]")
            else:
                lines.append(f"  {champ.name}")

        remaining = len(filtered) - start_idx - 15
        if remaining > 0:
            lines.append(f"  ... and {remaining} more")

        lines.append("")
        lines.append(
            f"[dim]Search: {self.search_filter}  |  ({self.current_selection + 1}/{len(filtered)})[/dim]"
        )

        return Panel(
            "\n".join(lines),
            border_style="cyan",
            padding=(0, 1),
            title=f"[bold]{title}[/bold]",
        ), filtered

    def build_settings_menu(self, settings) -> Panel:
        """Build settings menu panel."""
        lines = [
            f"Insta Lock: [{'green' if settings.insta_lock else 'red'}]{'ON' if settings.insta_lock else 'OFF'}[/]  (Press [cyan]L[/cyan])",
            f"Insta Ban: [{'green' if settings.insta_ban else 'red'}]{'ON' if settings.insta_ban else 'OFF'}[/]  (Press [cyan]B[/cyan])",
            f"Pick Start Hover: {settings.pick_start_hover_delay}ms",
            f"Pick End Lock: {settings.pick_end_lock_delay}ms",
            f"Ban Start Hover: {settings.ban_start_hover_delay}ms",
            f"Ban End Lock: {settings.ban_end_lock_delay}ms",
            "",
            "[cyan]L[/cyan] - Toggle insta-lock",
            "[cyan]B[/cyan] - Toggle insta-ban",
            "[cyan]Q[/cyan] - Back",
        ]
        return Panel(
            "\n".join(lines),
            border_style="blue",
            padding=(1, 2),
            title="[bold]Settings[/bold]",
        )

    def input_non_blocking(self, timeout: float = 0.05) -> Optional[int]:
        """Get a key press without blocking."""
        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():  # type: ignore[attr-defined]
                return ord(msvcrt.getch())  # type: ignore[attr-defined]
            time.sleep(0.001)
        return None
