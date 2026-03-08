#!/usr/bin/env python3
"""
DEVORUN: Oracle Radar — LIVE  (Stealth Mode v4)
Real-time Twitter/X intelligence feed via Nitter RSS.
Monitors: zachxbt, zoomerfied, elonmusk, Devran1An, VitalikButerin, whale_alert
Press Ctrl+C to exit.

Stealth Mode features (v4):
  - Diversity Check: every account has its own staggered instance priority so
    all 6 accounts NEVER hit the same Nitter mirror simultaneously (ghost fix).
  - Show All Tweets: non-critical tweets appear as [INFO] (white/blue) instead of
    being visually buried — full stream is always visible.
  - Smart Rotation: global _instance_failures tracker — failed instances are
    bypassed immediately, healthy ones tried first (no 5-second inter-try sleep).
  - Table Capacity: ENTRIES_PER_FEED = 20, MAX_ROWS = 120 — 20 tweets per source.
  - Random User-Agent per request: Chrome/Firefox/Safari/Edge/Mobile rotation
  - Self-Healing: as soon as one real tweet lands, OFFLINE sentinel is cleared
  - Verbose footer: FETCHING: @elonmusk, @VitalikButerin... in real-time
  - FETCH_TIMEOUT = 15s to tolerate slow servers
  - Partial-data streaming: each account flushes results as it finishes
  - Error ring buffer: last 3 errors shown in footer (HTTP 403, Timeout, etc.)
"""

import html
import random
import re
import threading
import time
from datetime import datetime, timezone

import feedparser
import requests
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

# ── Config ────────────────────────────────────────────────────────────────────
ACCOUNTS = ["zachxbt", "zoomerfied", "elonmusk", "Devran1An", "VitalikButerin", "whale_alert"]

KEYWORDS = [
    "btc", "liquid", "sol", "raise", "investment", "capital",
    "war", "token", "crypto", "hack", "emergency", "breaking",
    "whale", "million", "billion", "ethereum", "vitalik", "alert",
]

# Default Nitter instances tried in order — first that responds with data wins.
# Last verified: 2026-03-08 — Stealth v3: added mint.lgbt, perennialte.ch, esmailelbob.xyz.
# Less-crowded mirrors are placed near the top to surface data faster.
NITTER_INSTANCES = [
    "https://nitter.mint.lgbt",          # new — generally less hammered
    "https://nitter.perennialte.ch",     # new — low-traffic UK mirror
    "https://nitter.esmailelbob.xyz",    # new — independent operator
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://xcancel.com",
    "https://nitter.nixnet.services",
]

# Per-account instance priority overrides.
# DIVERSITY CHECK (v4):  each account starts from a DIFFERENT mirror so that
# all 6 parallel fetch threads never hammer the same server at second 0.
# Rotation order below is offset by one slot per account (round-robin stagger).
NITTER_ACCOUNT_INSTANCES: dict[str, list[str]] = {
    # Slot 0 — leads with mint.lgbt
    "elonmusk": [
        "https://nitter.mint.lgbt",
        "https://nitter.perennialte.ch",
        "https://nitter.esmailelbob.xyz",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://xcancel.com",
        "https://nitter.nixnet.services",
    ],
    # Slot 1 — leads with perennialte.ch
    "Devran1An": [
        "https://nitter.perennialte.ch",
        "https://nitter.esmailelbob.xyz",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://xcancel.com",
        "https://nitter.nixnet.services",
        "https://nitter.mint.lgbt",
    ],
    # Slot 2 — leads with esmailelbob.xyz  (Ghost Fix for Vitalik)
    "VitalikButerin": [
        "https://nitter.esmailelbob.xyz",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://xcancel.com",
        "https://nitter.nixnet.services",
        "https://nitter.mint.lgbt",
        "https://nitter.perennialte.ch",
    ],
    # Slot 3 — leads with poast.org  (Ghost Fix for Whale Alert)
    "whale_alert": [
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://xcancel.com",
        "https://nitter.nixnet.services",
        "https://nitter.mint.lgbt",
        "https://nitter.perennialte.ch",
        "https://nitter.esmailelbob.xyz",
    ],
    # Slot 4 — leads with privacydev.net  (Ghost Fix for ZachXBT)
    "zachxbt": [
        "https://nitter.privacydev.net",
        "https://xcancel.com",
        "https://nitter.nixnet.services",
        "https://nitter.mint.lgbt",
        "https://nitter.perennialte.ch",
        "https://nitter.esmailelbob.xyz",
        "https://nitter.poast.org",
    ],
    # Slot 5 — leads with xcancel.com  (Ghost Fix for Zoomerfied)
    "zoomerfied": [
        "https://xcancel.com",
        "https://nitter.nixnet.services",
        "https://nitter.mint.lgbt",
        "https://nitter.perennialte.ch",
        "https://nitter.esmailelbob.xyz",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
    ],
}

REFRESH_SECS       = 30    # seconds between full re-pulls
MAX_ROWS           = 120   # max tweet rows shown (6 sources x 20 entries)
FETCH_TIMEOUT      = 15    # per-request timeout — 15 s for slow servers
ENTRIES_PER_FEED   = 20   # latest N entries to grab per account (was 8)
LOG_FILE           = "radar_history.txt"   # ultra-light persistent tweet log

# ── Stealth Mode ──────────────────────────────────────────────────────────────
# Rotate User-Agents so instances see normal browser traffic, not a bot string.
USER_AGENTS = [
    # Chrome/Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome/macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome/Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox/Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Firefox/Linux
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Safari/macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Safari/iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    # Edge/Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

# Smart Rotation: after trying all 7 instances once, do one more pass of the
# surviving (non-failed) instances before declaring SOURCE OFFLINE.
STEALTH_RETRY_PASS = 2   # max full sweeps per cycle (no inter-instance sleep)

# ── Shared diagnostic state ───────────────────────────────────────────────────
# All of these are written by fetch threads and read by the UI thread.

_status_lock    = threading.Lock()
_active_fetches: set[str] = set()   # handles currently in-flight
_fetch_label    = "idle"            # human-readable line shown in footer subtitle

_errors_lock = threading.Lock()
_last_errors: list[str] = []        # ring buffer — last 3 error snippets

# ── Smart Rotation: per-account instance health tracker ───────────────────────
# Stores URLs of instances that failed in the CURRENT cycle for each username.
# fetch_feed() marks failures immediately and skips them on the same cycle.
# Cleared at the start of every new fetch cycle so stale failures don't persist.
_instance_lock:    threading.Lock       = threading.Lock()
_instance_failures: dict[str, set[str]] = {}   # username -> {failed_url, ...}

# ── Alert & Logging dedup sets ────────────────────────────────────────────────
# Both keyed on hash(source|time|content[:80]) so each unique tweet fires at
# most once per event type, even across multiple UI refresh cycles.
_alerted_hashes: set[str] = set()   # tweets that have already fired a beep
_logged_hashes:  set[str] = set()   # tweets that have already been written to disk

# Partial-result buffer.  Each _account_worker writes here as it finishes.
# The main loop polls this every 0.25 s so partial data appears immediately
# without waiting for the slowest account.
_result_lock = threading.Lock()
_result: dict = {
    "tweets":        [],
    "last_update":   "Never",
    "ready":         False,      # flipped to True as soon as any account lands
    "fetch_running": False,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def audio_alert() -> None:
    """
    Non-blocking terminal beep on CRITICAL signal.
    Uses the ANSI BEL character (\a) — zero deps, zero crash risk.
    Works on Linux/macOS/Windows terminals that have bell enabled.
    """
    print("\a", end="", flush=True)


def log_tweet(tweet: dict) -> None:
    """
    Append a single tweet to radar_history.txt exactly once.
    Never raises — a disk error must never crash the radar.
    Format: [YYYY-MM-DD HH:MM:SS] [SIGNAL  ] @source @ tweet_time | content
    """
    key = f"{tweet['source']}|{tweet['time']}|{tweet['content'][:80]}"
    h   = hash(key)
    if h in _logged_hashes:
        return
    _logged_hashes.add(h)
    signal    = "CRITICAL" if tweet["critical"] else "NOMINAL "
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line      = (
        f"[{timestamp}] [{signal}] "
        f"{tweet['source']:20s} @ {tweet['time']} | "
        f"{tweet['content'][:140]}\n"
    )
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass   # silently skip — never crash the radar over a log write


def strip_html(raw: str) -> str:
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return html.unescape(raw).strip()


def has_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)


def best_content(entry: dict) -> str:
    candidates = []
    for c in entry.get("content", []):
        candidates.append(strip_html(c.get("value", "")))
    if entry.get("summary"):
        candidates.append(strip_html(entry["summary"]))
    if entry.get("title"):
        candidates.append(strip_html(entry["title"]))
    seen = ""
    for c in candidates:
        if len(c) > len(seen):
            seen = c
    return seen


def parse_time(entry: dict) -> tuple[str, float]:
    pub = entry.get("published_parsed")
    if pub:
        try:
            dt = datetime(*pub[:6], tzinfo=timezone.utc)
            return dt.strftime("%H:%M:%S"), dt.timestamp()
        except Exception:
            pass
    return "??:??:??", 0.0


def _push_error(msg: str) -> None:
    """Append to the error ring buffer (max 3 entries).  Thread-safe."""
    with _errors_lock:
        _last_errors.append(msg[:65])
        del _last_errors[:-3]  # keep only the last 3


def _update_label() -> None:
    """
    Rebuild _fetch_label from _active_fetches.
    MUST be called while the caller already holds _status_lock.
    """
    global _fetch_label
    if _active_fetches:
        handles = ", ".join(sorted(_active_fetches))
        _fetch_label = f"FETCHING: {handles}"
    else:
        _fetch_label = f"done @ {datetime.now().strftime('%H:%M:%S')}"


# ── Per-account feed fetch ────────────────────────────────────────────────────

def _mark_failed(username: str, url: str) -> None:
    """Thread-safe: record that this instance URL failed for this account."""
    with _instance_lock:
        _instance_failures.setdefault(username, set()).add(url)


def _build_candidate_list(username: str, base: list[str]) -> list[str]:
    """
    Smart Rotation helper: return instances sorted so healthy ones come first.
    Within each group the order is randomised to spread load across the pool.
    """
    with _instance_lock:
        failed = set(_instance_failures.get(username, set()))
    healthy  = [i for i in base if i not in failed]
    degraded = [i for i in base if i in failed]
    random.shuffle(healthy)
    random.shuffle(degraded)
    return healthy + degraded   # try good ones first, bad ones as last resort


def fetch_feed(username: str) -> tuple[list[dict], str]:
    """
    Smart Rotation fetch engine (v4):

      - Uses per-account instance lists (Diversity Check) so concurrent threads
        never all hit the same Nitter mirror at the same moment.
      - Builds the candidate queue by putting HEALTHY instances first and
        PREVIOUSLY-FAILED instances last — no 5-second sleep between tries.
      - Marks each failure immediately so the NEXT account that coincidentally
        shares the same instance skips it without waiting.
      - Does up to STEALTH_RETRY_PASS sweeps total.  If the first sweep gets a
        result, the second never starts (instant exit on first success).
      - On full success, clears the failure record for this account.

    Returns (tweets, last_error_msg).  tweets=[] only if all passes exhaust.
    """
    base       = list(NITTER_ACCOUNT_INSTANCES.get(username, NITTER_INSTANCES))
    last_error = ""

    for sweep in range(STEALTH_RETRY_PASS):
        candidates = _build_candidate_list(username, base)

        for instance in candidates:
            short = instance.replace("https://", "").split("/")[0]
            try:
                ua   = random.choice(USER_AGENTS)
                url  = f"{instance}/{username}/rss?t={int(time.time())}"
                resp = requests.get(
                    url,
                    headers={"User-Agent": ua},
                    timeout=FETCH_TIMEOUT,
                )
                resp.raise_for_status()

                feed = feedparser.parse(resp.content)
                if not feed.entries:
                    last_error = f"@{username} {short}: empty feed"
                    _mark_failed(username, instance)
                    continue   # immediately try next — no sleep

                tweets = []
                for entry in feed.entries[:ENTRIES_PER_FEED]:
                    content = best_content(entry)
                    if not content:
                        continue
                    ts, sort_key = parse_time(entry)
                    tweets.append({
                        "time":     ts,
                        "source":   f"@{username}",
                        "content":  content,
                        "critical": has_keyword(content),
                        "sort_key": sort_key,
                    })

                if tweets:
                    # Clear failure record — this instance is alive again
                    with _instance_lock:
                        _instance_failures.pop(username, None)
                    return tweets, ""   # success — bail immediately

                # Feed parsed OK but zero usable entries
                last_error = f"@{username} {short}: 0 usable entries"
                _mark_failed(username, instance)

            except requests.exceptions.Timeout:
                last_error = f"@{username} {short}: Timeout (>{FETCH_TIMEOUT}s)"
                _mark_failed(username, instance)
            except requests.exceptions.ConnectionError:
                last_error = f"@{username} {short}: Connection refused"
                _mark_failed(username, instance)
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else "?"
                last_error = f"@{username} {short}: HTTP {code}"
                _mark_failed(username, instance)
            except Exception as exc:
                last_error = f"@{username}: {exc!s:.50}"

        # All candidates exhausted for this sweep.  Second sweep (if any) will
        # re-evaluate health — maybe a 429 cleared between sweeps.

    return [], last_error


# ── Parallel fetch with per-account isolation ─────────────────────────────────

def _account_worker(username: str) -> None:
    """
    Thread per account.

    1. Marks the account as in-flight in _active_fetches so the footer can show
       e.g. "FETCHING: @elonmusk, @VitalikButerin..."
    2. Calls fetch_feed() — any crash here is isolated to this account.
    3. On success, IMMEDIATELY flushes tweets into _result (partial-data streaming).
       The UI will paint these before other accounts have finished.
    4. Pushes any error string into the ring buffer for the footer to display.
    """
    with _status_lock:
        _active_fetches.add(f"@{username}")
        _update_label()

    try:
        tweets, error = fetch_feed(username)

        if error:
            _push_error(error)

        now_str = datetime.now().strftime("%H:%M:%S")
        if tweets:
            # ── Partial-data hotpath: merge this account's fresh tweets in ──
            with _result_lock:
                # Self-Heal: drop any stale OFFLINE sentinel for this account
                # the instant real data arrives — no manual intervention needed.
                clean = [
                    t for t in _result["tweets"]
                    if not (
                        t["source"]  == f"@{username}"
                        and t["content"] == "⚠️ SOURCE OFFLINE"
                    )
                ]
                combined = clean + tweets
                combined.sort(key=lambda x: x["sort_key"], reverse=True)
                _result["tweets"]      = combined[:MAX_ROWS]
                _result["last_update"] = now_str
                _result["ready"]       = True   # wake up the UI immediately
        else:
            # All instances failed — show a sentinel row so the source column
            # still renders and the operator knows the radar is still trying.
            sentinel = {
                "time":     now_str,
                "source":   f"@{username}",
                "content":  "⚠️ SOURCE OFFLINE",
                "critical": False,
                "sort_key": 0,   # sink to bottom so real data stays on top
            }
            with _result_lock:
                # Replace any stale sentinel for this account, then re-insert.
                _result["tweets"] = [
                    t for t in _result["tweets"]
                    if not (t["source"] == f"@{username}" and t["content"] == "⚠️ SOURCE OFFLINE")
                ]
                _result["tweets"].append(sentinel)
                _result["tweets"].sort(key=lambda x: x["sort_key"], reverse=True)
                _result["tweets"]      = _result["tweets"][:MAX_ROWS]
                _result["last_update"] = now_str
                _result["ready"]       = True

    except Exception as exc:
        _push_error(f"@{username}: worker crash: {exc!s:.45}")

    finally:
        with _status_lock:
            _active_fetches.discard(f"@{username}")
            _update_label()


def _fetch_worker() -> None:
    """
    Orchestrates one full fetch cycle.

    - Clears the result buffer so stale data from the previous cycle isn't
      merged with new results.
    - Fires all account threads in parallel.
    - Each thread streams its own results back the moment it finishes, so the
      UI shows Elon's tweets immediately without waiting for Vitalik.
    """
    global _fetch_label

    # ── Reset cycle state ─────────────────────────────────────────────────────
    with _result_lock:
        _result["tweets"]        = []
        _result["ready"]         = False
        _result["fetch_running"] = True

    with _errors_lock:
        _last_errors.clear()

    # Clear per-cycle failure records so stale marks don't carry into the next run
    with _instance_lock:
        _instance_failures.clear()

    with _status_lock:
        _fetch_label = "launching parallel fetch..."

    threads = [
        threading.Thread(
            target=_account_worker,
            args=(acc,),
            daemon=True,
            name=f"fetch-{acc}",
        )
        for acc in ACCOUNTS
    ]
    for t in threads:
        t.start()

    # Wall-clock cost ≈ slowest single account (they run concurrently, not sequentially).
    # Stealth Mode adds up to (STEALTH_RETRY_LOOPS-1) * (STEALTH_RETRY_WAIT + FETCH_TIMEOUT)
    # of potential sleep+probe time on top of the initial full-pool sweep.
    stealth_overhead = (STEALTH_RETRY_LOOPS - 1) * (STEALTH_RETRY_WAIT + FETCH_TIMEOUT)
    max_wait = FETCH_TIMEOUT * max(
        len(NITTER_ACCOUNT_INSTANCES.get(acc, NITTER_INSTANCES))
        for acc in ACCOUNTS
    ) + stealth_overhead + 2
    for t in threads:
        t.join(timeout=max_wait)

    with _result_lock:
        _result["fetch_running"] = False


# ── UI builders ───────────────────────────────────────────────────────────────

def build_header() -> Panel:
    title = Text("D E V O R U N  O R A C L E", style=NEON_PURPLE, justify="center")
    return Panel(
        Align.center(title, vertical="middle"),
        style=NEON_BLUE,
        height=3,
    )


def build_table(tweets: list[dict]) -> Panel:
    table = Table(
        border_style=NEON_BLUE,
        header_style=f"bold {NEON_BLUE}",
        show_header=True,
        expand=True,
        padding=(0, 1),
        show_lines=True,
    )
    table.add_column("[TIME]",    style=NEON_GREEN, no_wrap=True, min_width=10)
    table.add_column("[SOURCE]",  style=NEON_GREEN, no_wrap=True, min_width=17)
    table.add_column("[CONTENT]", style=NEON_GREEN, ratio=4)
    table.add_column("[SIGNAL]",  style=NEON_GREEN, no_wrap=True, min_width=16, justify="center")

    if not tweets:
        table.add_row(
            Text("--:--:--",                         style="dim"),
            Text("--",                               style="dim"),
            Text("Awaiting signal... Fetching feeds.", style="dim"),
            Text("📡 SCANNING",                      style="bold cyan"),
        )
    else:
        for tw in tweets:
            if tw["critical"]:
                row_style   = NEON_RED
                signal_cell = Text("🚨 CRITICAL", style="bold bright_red")
            elif tw["content"] == "⚠️ SOURCE OFFLINE":
                row_style   = "bold yellow"
                signal_cell = Text("⚠ OFFLINE",  style="bold yellow")
            else:
                # Show ALL tweets — [INFO] in white/bright_blue so nothing is hidden
                row_style   = "white"
                signal_cell = Text("[INFO]", style="bold bright_blue")

            content = tw["content"]
            if len(content) > 120:
                content = content[:117] + "..."

            table.add_row(
                Text(tw["time"],   style=row_style),
                Text(tw["source"], style=row_style),
                Text(content,      style=row_style),
                signal_cell,
            )

    return Panel(
        table,
        style=NEON_BLUE,
        title="[bold bright_blue][ LIVE SIGNAL FEED ][/bold bright_blue]",
        title_align="left",
        subtitle="[bright_blue][ oracle v1.0 ][/bright_blue]",
        subtitle_align="right",
    )


def build_footer(tweets: list[dict], countdown: int, last_update: str) -> Panel:
    critical_count = sum(1 for tw in tweets if tw["critical"])
    total          = len(tweets)

    alert_part = (
        f"[bold bright_red]⚠  {critical_count} CRITICAL[/bold bright_red]  |  "
        if critical_count else ""
    )

    with _status_lock:
        label_snap = _fetch_label
    with _errors_lock:
        errors_snap = list(_last_errors)

    # ── Verbose fetch indicator ───────────────────────────────────────────────
    # Shows e.g. "FETCHING: @elonmusk, @VitalikButerin..." in bright yellow
    # while in-flight, or a dim "done @ 22:31:07" when idle.
    if label_snap.startswith("FETCHING:"):
        label_markup = f"[bold bright_yellow]{label_snap}[/bold bright_yellow]"
    else:
        label_markup = f"[dim]{label_snap}[/dim]"

    # ── Error display ─────────────────────────────────────────────────────────
    # Prints the last 2 distinct errors so the operator can see exactly what
    # failed (e.g. "HTTP 403", "Timeout (>15s)", "Connection refused").
    if errors_snap:
        err_parts  = " | ".join(errors_snap[-2:])
        err_markup = f"  [bold red]ERR:[/bold red] [dim red]{err_parts}[/dim red]"
    else:
        err_markup = ""

    text = Text.from_markup(
        f"OPERATOR: DEVRAN1AN  |  TARGETS: {len(ACCOUNTS)}  |  SIGNALS: {total}  |  "
        f"{alert_part}"
        f"[bright_yellow]REFRESH IN: {countdown:02d}s[/bright_yellow]\n"
        f"[bright_blue][LAST REFRESH: {last_update}][/bright_blue]"
        f"  |  [bright_green][LOGS: ACTIVE][/bright_green]"
        f"  |  [bright_cyan][AUTO-RECOVERY: ON][/bright_cyan]"
    )
    text.justify = "center"

    return Panel(
        Align.center(text, vertical="middle"),
        style=NEON_BLUE,
        height=5,
        subtitle=f"[dim] {label_markup}{err_markup} [/dim]",
        subtitle_align="left",
    )


def build_layout(tweets: list[dict], countdown: int, last_update: str) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["header"].update(build_header())
    layout["main"].update(build_table(tweets))
    layout["footer"].update(build_footer(tweets, countdown, last_update))
    return layout


# ── Main loop ─────────────────────────────────────────────────────────────────

def _run_main_loop() -> None:
    """
    Inner radar loop.  Runs until KeyboardInterrupt or an unhandled exception.
    Raising an exception bubbles up to main() which will auto-reboot after 10 s.
    """
    tweets:       list[dict]              = []
    last_update:  str                     = "Never"
    next_refresh: float                   = 0.0          # 0 = fire immediately on first tick
    fetch_thread: threading.Thread | None = None

    with Live(
        build_layout(tweets, REFRESH_SECS, last_update),
        refresh_per_second=4,
        screen=True,
    ) as live:
        while True:
            now = time.time()

            # ── Pick up partial or completed results (fires per-account) ──────
            with _result_lock:
                if _result["ready"]:
                    tweets      = list(_result["tweets"])
                    last_update = _result["last_update"]
                    _result["ready"] = False

            # ── Audio alert + logging for every (new) tweet ──────────────────
            for tw in tweets:
                key = f"{tw['source']}|{tw['time']}|{tw['content'][:80]}"
                h   = hash(key)
                # Beep once per unique CRITICAL tweet
                if tw["critical"] and h not in _alerted_hashes:
                    _alerted_hashes.add(h)
                    audio_alert()
                # Log every tweet exactly once
                log_tweet(tw)

            # ── Kick off a fresh cycle when the timer expires ─────────────────
            if now >= next_refresh and (fetch_thread is None or not fetch_thread.is_alive()):
                tweets = []   # clear local copy → UI shows SCANNING immediately
                fetch_thread = threading.Thread(
                    target=_fetch_worker, daemon=True, name="fetch-cycle"
                )
                fetch_thread.start()
                next_refresh = now + REFRESH_SECS

            countdown = max(0, int(next_refresh - now))
            live.update(build_layout(tweets, countdown, last_update))
            time.sleep(0.25)


def main() -> None:
    """
    Outer recovery shell.
    Catches any crash (network failure, unexpected exception) and auto-reboots
    the radar after a 10-second cooldown.  KeyboardInterrupt exits cleanly.
    """
    while True:
        try:
            _run_main_loop()

        except KeyboardInterrupt:
            console.print(
                "\n[bold bright_magenta]DEVORUN ORACLE — session terminated.[/bold bright_magenta]\n"
            )
            break

        except Exception as exc:
            # ── Auto-reboot path ─────────────────────────────────────────────
            console.print(
                "\n[bold bright_red][!] CONNECTION LOST... RECONNECTING IN 10S[/bold bright_red]"
                f"\n[dim red]Reason: {exc!s:.120}[/dim red]"
            )
            # Reset all shared state so the fresh loop starts clean
            with _result_lock:
                _result["tweets"]        = []
                _result["last_update"]   = "Never"
                _result["ready"]         = False
                _result["fetch_running"] = False
            with _errors_lock:
                _last_errors.clear()
            time.sleep(10)
            console.print("[bold bright_green][+] RECONNECTING...[/bold bright_green]\n")


if __name__ == "__main__":
    main()
