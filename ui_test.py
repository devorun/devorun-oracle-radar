#!/usr/bin/env python3
"""
DEVORUN: Oracle Radar
UI Mockup — uses the Rich library for a full terminal dashboard.

Runs a live 10-second animation where the ZachXBT CRITICAL alert flashes.
Press Ctrl+C to exit early.
"""

import time

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ── Palette ───────────────────────────────────────────────────────────────────
NEON_PURPLE = "bold bright_magenta"
NEON_BLUE   = "bright_blue"
NEON_GREEN  = "bright_green"
NEON_RED    = "bold bright_red"


# ── Header ────────────────────────────────────────────────────────────────────
def build_header() -> Panel:
    title = Text("D E V O R U N  O R A C L E", style=NEON_PURPLE, justify="center")
    return Panel(
        Align.center(title, vertical="middle"),
        style=NEON_BLUE,
        height=3,
    )


# ── Main Table ────────────────────────────────────────────────────────────────
def build_table(alert_on: bool = True) -> Panel:
    table = Table(
        border_style=NEON_BLUE,
        header_style=f"bold {NEON_BLUE}",
        show_header=True,
        expand=True,
        padding=(0, 1),
        show_lines=True,
    )

    table.add_column("[TIME]",    style=NEON_GREEN, no_wrap=True, min_width=10)
    table.add_column("[SOURCE]",  style=NEON_GREEN, no_wrap=True, min_width=14)
    table.add_column("[CONTENT]", style=NEON_GREEN, ratio=4)
    table.add_column("[SIGNAL]",  style=NEON_GREEN, no_wrap=True, min_width=16, justify="center")

    # ── Row 1 : @zachxbt — RED ALERT (flashing) ──────────────────────────────
    alert_style  = NEON_RED if alert_on else "red"
    signal_style = "bold bright_red" if alert_on else "bold dark_red"

    table.add_row(
        Text("09:42:11",  style=alert_style),
        Text("@zachxbt",  style=alert_style),
        Text(
            "Potential rug pull detected on $DEVORUN — on-chain evidence "
            "linked to known exploiter wallets. Advise immediate caution.",
            style=alert_style,
        ),
        Text("🚨 CRITICAL", style=signal_style),
    )

    # ── Row 2 : @zoomerfied ──────────────────────────────────────────────────
    table.add_row(
        Text("09:43:05",     style=NEON_GREEN),
        Text("@zoomerfied",  style=NEON_GREEN),
        Text(
            "The meta is shifting — devs who ship daily win the cycle. "
            "$DEVORUN looking like a serious sleeper 👀",
            style=NEON_GREEN,
        ),
        Text("⚡ ALERT", style="bold yellow"),
    )

    # ── Row 3 : @elonmusk ────────────────────────────────────────────────────
    table.add_row(
        Text("09:44:20",   style=NEON_GREEN),
        Text("@elonmusk",  style=NEON_GREEN),
        Text(
            "To the moon 🚀 … or not. The oracle knows what the charts won't tell you.",
            style=NEON_GREEN,
        ),
        Text("📡 MONITOR", style="bold cyan"),
    )

    # ── Row 4 : @Devran1An ───────────────────────────────────────────────────
    table.add_row(
        Text("09:45:00",    style=NEON_GREEN),
        Text("@Devran1An",  style=NEON_GREEN),
        Text(
            "DEVORUN ORACLE RADAR is live — watching every signal, every move. "
            "Nothing escapes the grid. 🔍",
            style=NEON_GREEN,
        ),
        Text("✅ NOMINAL", style="bold bright_green"),
    )

    return Panel(
        table,
        style=NEON_BLUE,
        title="[bold bright_blue][ LIVE SIGNAL FEED ][/bold bright_blue]",
        title_align="left",
        subtitle="[bright_blue][ oracle v0.1 ][/bright_blue]",
        subtitle_align="right",
    )


# ── Footer ────────────────────────────────────────────────────────────────────
def build_footer() -> Panel:
    text = Text(
        "OPERATOR: DEVRAN1AN  |  SYSTEM: ACTIVE  |  MONITORING 4 TARGETS",
        style=f"bold {NEON_GREEN}",
        justify="center",
    )
    return Panel(
        Align.center(text, vertical="middle"),
        style=NEON_BLUE,
        height=3,
    )


# ── Layout composer ───────────────────────────────────────────────────────────
def build_layout(alert_on: bool = True) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["header"].update(build_header())
    layout["main"].update(build_table(alert_on=alert_on))
    layout["footer"].update(build_footer())
    return layout


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    flash = True
    try:
        with Live(
            build_layout(flash),
            refresh_per_second=2,
            screen=True,
        ) as live:
            for _ in range(30):   # ~15 seconds of animation (0.5s per tick)
                time.sleep(0.5)
                flash = not flash
                live.update(build_layout(flash))
    except KeyboardInterrupt:
        pass
    finally:
        console.print(
            "\n[bold bright_magenta]DEVORUN ORACLE — session terminated.[/bold bright_magenta]\n"
        )


if __name__ == "__main__":
    main()
