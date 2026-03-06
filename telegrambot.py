from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, List, Tuple
import asyncio
import html
import json
import os
import time
from datetime import datetime, timezone
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8645094734:AAGUxAxGM9maNGMrVHMvRUk97z8NvuVgiFQ"

MATCH_LINK = "https://sajatoldalad.hu/meccs"
CALC_LINK = "https://arbify-bet.hu/calculator"
CALC_DYNAMIC_BASE_URL = os.getenv("CALC_DYNAMIC_BASE_URL", "https://arbify-bet.hu/calculator").strip() or "https://arbify-bet.hu/calculator"
CALC_DEFAULT_STAKE = os.getenv("CALC_DEFAULT_STAKE", "14950").strip() or "14950"
AFFILIATE_LINK = "https://arbify-bet.hu/register?lang=rs"
GUIDE_LINK = "https://arbify-bet.hu/tutorial-sr"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://sonudgyyvxncdcganppl.supabase.co").strip().rstrip("/")
# SUPABASE_KEY marad elsődleges a visszamenőleges kompatibilitás miatt.
# SUPABASE_SERVICE_ROLE_KEY csak szerver oldali környezetben használandó (ne kerüljön repo-ba).
SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
).strip()
SUPABASE_READ_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNvbnVkZ3l5dnhuY2RjZ2FucHBsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDAzMDk0MywiZXhwIjoyMDc1NjA2OTQzfQ.6mmHZJ2QS3a4TywxZ-lswdcvwPCF5NCYLe6CuiO8-3A"
).strip()
SUPABASE_BETS_TABLE = os.getenv("SUPABASE_BETS_TABLE", "tips").strip() or "tips"
BOT_LOG_FILE = os.getenv("BOT_LOG_FILE", "").strip()
try:
    SUPABASE_SYNC_INTERVAL_SECONDS = max(5, int(os.getenv("SUPABASE_SYNC_INTERVAL_SECONDS", "35")))
except ValueError:
    SUPABASE_SYNC_INTERVAL_SECONDS = 35
try:
    SUPABASE_QUERY_LIMIT = min(1000, max(1, int(os.getenv("SUPABASE_QUERY_LIMIT", "100"))))
except ValueError:
    SUPABASE_QUERY_LIMIT = 100
try:
    MESSAGE_STATE_FLUSH_INTERVAL_SECONDS = max(1, int(os.getenv("MESSAGE_STATE_FLUSH_INTERVAL_SECONDS", "5")))
except ValueError:
    MESSAGE_STATE_FLUSH_INTERVAL_SECONDS = 5

# Bookmaker lista (a kért nevekkel)
BOOKMAKERS = [
    {"key": "maxbet", "name": "MaxBet", "emoji": "🔥", "url": "https://www.maxbet.rs/sr/registracija"},
    {"key": "mozzartbet", "name": "Mozzartbet", "emoji": "💸", "url": "https://www.mozzartbet.com/rs/registration"},
    {"key": "admiralbet", "name": "AdmiralBet", "emoji": "🎯", "url": "https://admiralbet.rs/registration"},
    {"key": "meridian", "name": "Meridian", "emoji": "🟣", "url": "https://meridianbet.rs/sr/registracija"},
    {"key": "superbet", "name": "Superbet", "emoji": "🏅", "url": "https://superbet.rs/registracija"},
    {"key": "rabona", "name": "Rabona", "emoji": "🟡", "url": "https://rabona.com/registration"},
    {"key": "megapari", "name": "Megapari", "emoji": "🔵", "url": "https://megapari.com/registration"},
    {"key": "funbet", "name": "Frumzi", "emoji": "⚫", "url": "https://frumzi.com"},
    {"key": "20bet", "name": "20bet", "emoji": "🟢", "url": "https://20bet.com/registration"},
    {"key": "mostbet", "name": "MostBet", "emoji": "🟠", "url": "https://mostbet.com"},
]

BOOKMAKER_BY_KEY = {b["key"]: b for b in BOOKMAKERS}


def _normalize_bookmaker_value(value: Any) -> str:
    """Return lowercase alphanumeric token used for bookmaker key/name matching."""
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


BOOKMAKER_KEY_BY_NORMALIZED_VALUE = {}
for _bookmaker in BOOKMAKERS:
    BOOKMAKER_KEY_BY_NORMALIZED_VALUE[_normalize_bookmaker_value(_bookmaker["key"])] = _bookmaker["key"]
    BOOKMAKER_KEY_BY_NORMALIZED_VALUE[_normalize_bookmaker_value(_bookmaker["name"])] = _bookmaker["key"]
BOOKMAKER_KEY_BY_NORMALIZED_VALUE["ivibet"] = "20bet"
BOOKMAKER_KEY_BY_NORMALIZED_VALUE["mozzart"] = "mozzartbet"
MAX_SELECTED_BOOKMAKERS = 6
BOOKMAKER_FIELD_ALIASES = {
    "book1_key": ("book_1_key", "book1", "book_1", "bookmaker_1"),
    "book2_key": ("book_2_key", "book2", "book_2", "bookmaker_2"),
    "bookmaker1": ("bookmaker_1", "book1", "book_1"),
    "bookmaker2": ("bookmaker_2", "book2", "book_2"),
}
BET_FIELD_ALIASES = {
    "profit_percent": ("profit_percent_num", "profit", "profit_pct", "yield", "roi"),
    "match_start": ("match_date", "start_time", "event_time", "kickoff"),
    "match_name": ("match", "event_name", "fixture", "competition"),
    "option1": ("selection1", "selection_1", "bet1", "bet_1", "tip1", "tip_1"),
    "option2": ("selection2", "selection_2", "bet2", "bet_2", "tip2", "tip_2"),
    "odds1": ("odd1", "odd_1", "odds_1", "coef1", "coefficient1"),
    "odds2": ("odd2", "odd_2", "odds_2", "coef2", "coefficient2"),
}
BET_ID_FIELD_ALIASES = ("bet_id", "tip_id", "row_id", "uuid")


def _resolve_bookmaker_key(value: Any) -> str:
    """Resolve bookmaker name/key value to canonical internal bookmaker key."""
    return BOOKMAKER_KEY_BY_NORMALIZED_VALUE.get(_normalize_bookmaker_value(value), "")


def _get_bet_bookmaker_value(bet: Dict[str, Any], primary_key: str, fallback_key: str) -> Any:
    """Read bookmaker value from primary field, then fallback when primary is empty."""
    candidate_keys = [
        primary_key,
        *BOOKMAKER_FIELD_ALIASES.get(primary_key, ()),
        fallback_key,
        *BOOKMAKER_FIELD_ALIASES.get(fallback_key, ()),
    ]
    for key in candidate_keys:
        value = bet.get(key)
        if value is not None and str(value).strip():
            return value
    return ""


def _get_bet_field_value(bet: Dict[str, Any], primary_key: str) -> Optional[Any]:
    candidate_keys = [primary_key, *BET_FIELD_ALIASES.get(primary_key, ())]
    for key in candidate_keys:
        value = bet.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _resolve_bet_id(bet: Dict[str, Any]) -> str:
    candidate_keys = ("id", *BET_ID_FIELD_ALIASES)
    for key in candidate_keys:
        value = bet.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_match_start(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_bet_active(bet: Dict[str, Any]) -> bool:
    is_active_raw = bet.get("is_active")
    if isinstance(is_active_raw, bool) and not is_active_raw:
        return False

    status_raw = str(bet.get("status") or "").strip().lower()
    if status_raw in {"inactive", "closed", "expired", "settled", "finished"}:
        return False

    match_start = _parse_match_start(_get_bet_field_value(bet, "match_start"))
    if match_start is None:
        return True
    return match_start > datetime.now(timezone.utc)


def _format_match_start(match_start: Optional[datetime]) -> str:
    if match_start is None:
        return "ismeretlen"
    local_match_start = match_start.astimezone()
    month_names = {
        1: "Január", 2: "Február", 3: "Március", 4: "Április", 5: "Május", 6: "Június",
        7: "Július", 8: "Augusztus", 9: "Szeptember", 10: "Október", 11: "November", 12: "December",
    }
    month_name = month_names.get(local_match_start.month, str(local_match_start.month))
    return f"{month_name} {local_match_start.day}, {local_match_start.strftime('%H:%M')}"


def _format_sync_interval(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    if seconds % 60 == 0:
        return f"{seconds} másodperc ({seconds // 60} perc)"
    return f"{seconds} másodperc ({seconds / 60:.2f} perc)"


def _safe_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urllib_parse.urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    return ""


def _append_log_to_file(message: str) -> None:
    if not BOT_LOG_FILE:
        return
    try:
        with open(BOT_LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(f"{datetime.now().isoformat()} {message}\n")
    except OSError as exc:
        print(f"⚠️ Nem sikerült a log fájlba írni ({BOT_LOG_FILE}): {exc}")


def _log(message: str) -> None:
    print(message)
    _append_log_to_file(message)


def _log_info(message: str) -> None:
    _log(message)


def _log_warning(message: str) -> None:
    _log(message)


def _bilingual_text(hu_text: str, sr_text: str) -> str:
    """Return Hungarian + Serbian version of the same user-facing text."""
    return f"{hu_text}\n\n🇷🇸 {sr_text}"


TRANSLATIONS_SR = {
    "start_welcome": "👋 <b>Dobrodošao u GoldenTipsHungary sistem!</b>\n\nUnesi svoj <b>aktivacioni kod</b> koji si dobio kupovinom.",
    "no_bets": "ℹ️ <b>Trenutno nema dostupnih opklada</b> za izabrani par kladionica.\n\n🔄 Dodaj još kladionica komandom <b>/kancelarije</b>, ili sačekaj da stigne nova arbitražna opklada.",
    "saved": "✅ <b>GoldenTipsHungary</b>\nKladionice su sačuvane!\n\nAko želiš da izmeniš sa kojih kladionica primaš obaveštenja, pošalji: <b>/irodak</b>.\n\nŠaljem trenutno aktivne opklade...",
}

def _extract_total_count_from_content_range(content_range: str) -> Optional[int]:
    if "/" not in content_range:
        return None
    total_part = content_range.rsplit("/", 1)[-1].strip()
    if not total_part or total_part == "*":
        return None
    try:
        return int(total_part)
    except ValueError:
        return None


def _safe_read_json(path: str, fallback: Any) -> Any:
    if not path:
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def _safe_write_json(path: str, payload: Any) -> None:
    if not path:
        return
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        _log_warning(f"⚠️ Nem sikerült állapotfájlt írni ({path}): {exc}")


def _bet_snapshot_payload(bet: Dict[str, Any]) -> str:
    return json.dumps(bet, sort_keys=True, default=str)


def _load_last_bet_snapshots() -> Dict[str, str]:
    raw = _safe_read_json(BETS_SNAPSHOT_FILE, {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _persist_last_bet_snapshots(snapshot_map: Dict[str, str]) -> None:
    _safe_write_json(BETS_SNAPSHOT_FILE, snapshot_map)


def _load_persisted_message_state() -> Dict[int, Dict[str, Dict[str, Any]]]:
    raw = _safe_read_json(MESSAGE_STATE_FILE, {})
    if not isinstance(raw, dict):
        return {}

    restored: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for raw_user_id, state in raw.items():
        if not isinstance(state, dict):
            continue
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue

        raw_messages = state.get("active_bet_messages", {})
        raw_snapshots = state.get("active_bet_snapshots", {})
        if not isinstance(raw_messages, dict) or not isinstance(raw_snapshots, dict):
            continue

        messages: Dict[str, int] = {}
        for bet_id, message_id in raw_messages.items():
            try:
                messages[str(bet_id)] = int(message_id)
            except (TypeError, ValueError):
                continue

        snapshots = {str(k): str(v) for k, v in raw_snapshots.items()}
        restored[user_id] = {
            "active_bet_messages": messages,
            "active_bet_snapshots": snapshots,
        }
    return restored


def _mark_message_state_dirty() -> None:
    global MESSAGE_STATE_DIRTY
    MESSAGE_STATE_DIRTY = True


def _persist_message_state(force: bool = False) -> None:
    global MESSAGE_STATE_DIRTY, LAST_MESSAGE_STATE_FLUSH_TS
    now_ts = time.time()
    if not force:
        if not MESSAGE_STATE_DIRTY:
            return
        if now_ts - LAST_MESSAGE_STATE_FLUSH_TS < MESSAGE_STATE_FLUSH_INTERVAL_SECONDS:
            return

    payload: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for user_id, session in USER_SESSIONS.items():
        payload[str(user_id)] = {
            "active_bet_messages": dict(session.get("active_bet_messages", {})),
            "active_bet_snapshots": dict(session.get("active_bet_snapshots", {})),
        }
    _safe_write_json(MESSAGE_STATE_FILE, payload)
    MESSAGE_STATE_DIRTY = False
    LAST_MESSAGE_STATE_FLUSH_TS = now_ts


def _compute_bet_diff(active_bets: List[Dict[str, Any]]) -> Tuple[int, int, int, Dict[str, str]]:
    new_snapshot_map: Dict[str, str] = {}
    added = 0
    changed = 0
    dropped = 0

    for bet in active_bets:
        bet_id = _resolve_bet_id(bet)
        if not bet_id:
            continue
        current_snapshot = _bet_snapshot_payload(bet)
        previous_snapshot = LAST_BET_SNAPSHOTS.get(bet_id)
        if previous_snapshot is None:
            added += 1
        elif previous_snapshot != current_snapshot:
            changed += 1
        new_snapshot_map[bet_id] = current_snapshot

    dropped = max(0, len(LAST_BET_SNAPSHOTS) - len(new_snapshot_map))
    return added, changed, dropped, new_snapshot_map

# Aktív fogadások in-memory cache (később DB-re cserélhető)
ACTIVE_BETS: Dict[str, Dict[str, Any]] = {}
SUPABASE_LAST_SYNC_SUMMARY = "n/a"

BETS_SNAPSHOT_FILE = os.getenv("BETS_SNAPSHOT_FILE", "bets_snapshot.txt").strip() or "bets_snapshot.txt"
MESSAGE_STATE_FILE = os.getenv("MESSAGE_STATE_FILE", "message_state.txt").strip() or "message_state.txt"
LAST_BET_SNAPSHOTS: Dict[str, str] = {}
MESSAGE_STATE_DIRTY = False
LAST_MESSAGE_STATE_FLUSH_TS = 0.0

# Demo session tárolás memóriában (újraindítás után törlődik)
USER_SESSIONS: Dict[int, Dict[str, object]] = {}
USER_SYNC_LOCKS: Dict[int, asyncio.Lock] = {}


@dataclass
class ActivationRecord:
    code: str
    telegram_user_id: Optional[int] = None
    is_active: bool = True


class ActivationService:
    """
    Aktivációs szolgáltatás absztrakció.

    Jelenleg memória-alapú demo implementáció, hogy a logika készen álljon.
    Később ugyanezeket a metódusokat DB repository-ra lehet kötni.
    """

    def __init__(self) -> None:
        self._records_by_code: Dict[str, ActivationRecord] = {
            "123": ActivationRecord(code="123", telegram_user_id=None, is_active=True)
        }
        self._code_by_user: Dict[int, str] = {}

    def has_valid_code(self, code: str) -> bool:
        record = self._records_by_code.get(code)
        return bool(record and record.is_active)

    def bind_code_to_user(self, code: str, user_id: int) -> Optional[int]:
        """
        Kód hozzárendelése userhez.
        Visszaadja az előző user_id-t, ha takeover történt, különben None.
        """
        record = self._records_by_code.get(code)
        if record is None or not record.is_active:
            return None

        previous_owner = record.telegram_user_id
        previous_code = self._code_by_user.get(user_id)

        # Ha a jelenlegi usernek volt másik kódja, azt lecsatoljuk róla.
        if previous_code and previous_code != code:
            old_record = self._records_by_code.get(previous_code)
            if old_record and old_record.telegram_user_id == user_id:
                old_record.telegram_user_id = None

        record.telegram_user_id = user_id
        self._code_by_user[user_id] = code

        # Az előző tulaj session-je maradjon kód nélkül.
        if previous_owner is not None and previous_owner != user_id:
            self._code_by_user.pop(previous_owner, None)
            return previous_owner

        return None


ACTIVATION_SERVICE = ActivationService()
LAST_BET_SNAPSHOTS = _load_last_bet_snapshots()
PERSISTED_MESSAGE_STATE = _load_persisted_message_state()


# =========================
# HELPERS
# =========================
def get_session(user_id: int) -> Dict[str, object]:
    if user_id not in USER_SESSIONS:
        persisted = PERSISTED_MESSAGE_STATE.get(user_id, {})
        USER_SESSIONS[user_id] = {
            "state": "awaiting_code",   # awaiting_code | awaiting_guide | selecting_books | ready
            "selected": set(),          # Set[str]
            "activated": False,
            "receive_bets": False,
            "active_bet_messages": dict(persisted.get("active_bet_messages", {})),
            "active_bet_snapshots": dict(persisted.get("active_bet_snapshots", {})),
            "no_bets_notice_sent": False,
        }
    return USER_SESSIONS[user_id]


def _get_user_sync_lock(user_id: int) -> asyncio.Lock:
    lock = USER_SYNC_LOCKS.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        USER_SYNC_LOCKS[user_id] = lock
    return lock


def _bet_created_at_sort_key(bet: Dict[str, Any]) -> datetime:
    created_raw = str(bet.get("created_at") or "").strip()
    if created_raw.endswith("Z"):
        created_raw = created_raw[:-1] + "+00:00"
    if created_raw:
        try:
            parsed = datetime.fromisoformat(created_raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def user_can_receive_bets(user_id: int) -> bool:
    """
    Külső fogadás-dispatcher ehhez a flaghez igazodjon:
    /irodak közben False, mentés (✅ Kész) után True.
    """
    session = get_session(user_id)
    return bool(session.get("activated") and session.get("receive_bets"))


def set_active_bets(active_bets: List[Dict[str, Any]]) -> None:
    """
    Külső DB szinkron ehhez a metódushoz küldje az éppen aktív fogadásokat.
    A bet-enként stabil kulcs: bet["id"].
    """
    global LAST_BET_SNAPSHOTS

    added_count, changed_count, dropped_count, new_snapshot_map = _compute_bet_diff(active_bets)

    ACTIVE_BETS.clear()
    dropped_without_id = 0
    for bet in active_bets:
        bet_id = _resolve_bet_id(bet)
        if bet_id:
            ACTIVE_BETS[bet_id] = bet
        else:
            dropped_without_id += 1

    LAST_BET_SNAPSHOTS = new_snapshot_map
    _persist_last_bet_snapshots(LAST_BET_SNAPSHOTS)

    _log_info(
        "ℹ️ Bet diff összegzés: "
        f"új={added_count}, módosult={changed_count}, eltűnt={dropped_count}, "
        f"feldolgozott={len(ACTIVE_BETS)}"
    )

    if dropped_without_id:
        _log_warning(
            f"⚠️ {dropped_without_id} Supabase sor kihagyva, mert nem volt azonosító mező "
            "(id/bet_id/tip_id/row_id/uuid)."
        )


def _bet_matches_selected_books(bet: Dict[str, Any], selected: Set[str]) -> bool:
    book1_key = _resolve_bookmaker_key(_get_bet_bookmaker_value(bet, "book1_key", "bookmaker1"))
    book2_key = _resolve_bookmaker_key(_get_bet_bookmaker_value(bet, "book2_key", "bookmaker2"))
    if book1_key not in BOOKMAKER_BY_KEY or book2_key not in BOOKMAKER_BY_KEY:
        return False

    if book1_key == book2_key:
        return False

    return book1_key in selected and book2_key in selected


def _build_active_bet_text(bet: Dict[str, Any]) -> str:
    if not _is_bet_active(bet):
        return ""

    external_text = str(bet.get("text", "")).strip()

    book1_source = _get_bet_bookmaker_value(bet, "book1_key", "bookmaker1")
    book2_source = _get_bet_bookmaker_value(bet, "book2_key", "bookmaker2")

    book1 = BOOKMAKER_BY_KEY.get(_resolve_bookmaker_key(book1_source))
    book2 = BOOKMAKER_BY_KEY.get(_resolve_bookmaker_key(book2_source))
    if not book1 or not book2:
        return external_text

    profit_value = _get_bet_field_value(bet, "profit_percent")
    if profit_value is None:
        profit_value = "-"
    profit = str(profit_value).strip()
    match_start = _parse_match_start(_get_bet_field_value(bet, "match_start"))
    match_date = _format_match_start(match_start)
    match_name = html.escape(str(_get_bet_field_value(bet, "match_name") or "-").strip())

    book1_name = html.escape(str(bet.get("bookmaker1") or book1.get("name", "Bookmaker 1")).strip())
    book2_name = html.escape(str(bet.get("bookmaker2") or book2.get("name", "Bookmaker 2")).strip())
    # A fogadóiroda neve mindig a fix, irodához tartozó regisztrációs linkre mutasson.
    book1_affiliate = _safe_url(book1.get("url", ""))
    book2_affiliate = _safe_url(book2.get("url", ""))
    match_link1 = _safe_url(bet.get("original_link1") or bet.get("quick_link_url") or MATCH_LINK)
    match_link2 = _safe_url(bet.get("original_link2") or bet.get("quick_link_url") or MATCH_LINK)
    if not book1_affiliate:
        book1_affiliate = _safe_url(book1.get("url", "")) or _safe_url(MATCH_LINK)
    if not book2_affiliate:
        book2_affiliate = _safe_url(book2.get("url", "")) or _safe_url(MATCH_LINK)
    if not match_link1:
        match_link1 = _safe_url(MATCH_LINK)
    if not match_link2:
        match_link2 = _safe_url(MATCH_LINK)

    option1 = html.escape(str(_get_bet_field_value(bet, "option1") or "-").strip() or "-")
    option2 = html.escape(str(_get_bet_field_value(bet, "option2") or "-").strip() or "-")
    odds1 = html.escape(str(_get_bet_field_value(bet, "odds1") or "-").strip() or "-")
    odds2 = html.escape(str(_get_bet_field_value(bet, "odds2") or "-").strip() or "-")

    return (
        "🔒 <b>ÚJ ARBITRÁZS FOGADÁS</b>\n\n"
        f"💸 <b>Profit:</b> {html.escape(profit)}\n"
        "🟢 <b>STÁTUSZ:</b> AKTÍV\n"
        f"📅 <b>Dátum:</b> {html.escape(match_date)} • ⏳\n\n"
        f"{book1['emoji']} <a href=\"{html.escape(book1_affiliate, quote=True)}\"><b>{book1_name}</b></a>\n"
        f"<b>Mérkőzés:</b> <a href=\"{html.escape(match_link1, quote=True)}\">{match_name}</a>\n"
        f"<b>Fogadás:</b> {option1}\n"
        f"<b>Odds:</b> {odds1}\n\n"
        f"{book2['emoji']} <a href=\"{html.escape(book2_affiliate, quote=True)}\"><b>{book2_name}</b></a>\n"
        f"<b>Mérkőzés:</b> <a href=\"{html.escape(match_link2, quote=True)}\">{match_name}</a>\n"
        f"<b>Fogadás:</b> {option2}\n"
        f"<b>Odds:</b> {odds2}\n\n"
        "━━━━━━━━━━━━━━━\n"
        "⚙️ Szűrő módosítás: <b>/irodak</b>"
    )



def _calculator_book_param_name(bookmaker_name: str) -> str:
    normalized = "".join(ch for ch in str(bookmaker_name or "").strip().lower() if ch.isalnum())
    if not normalized:
        normalized = "bookmaker"
    return f"{normalized}Url"


def _build_calculator_link(bet: Dict[str, Any]) -> str:
    odds1 = str(_get_bet_field_value(bet, "odds1") or "").strip()
    odds2 = str(_get_bet_field_value(bet, "odds2") or "").strip()
    book1_name = str(_get_bet_field_value(bet, "bookmaker1") or _get_bet_bookmaker_value(bet, "book1_key", "bookmaker1") or "Bookmaker1").strip()
    book2_name = str(_get_bet_field_value(bet, "bookmaker2") or _get_bet_bookmaker_value(bet, "book2_key", "bookmaker2") or "Bookmaker2").strip()

    book1_url = _safe_url(bet.get("original_link1") or bet.get("link1") or "")
    book2_url = _safe_url(bet.get("original_link2") or bet.get("link2") or "")
    match_name = str(_get_bet_field_value(bet, "match_name") or "").strip()
    option1 = str(_get_bet_field_value(bet, "option1") or "").strip()
    option2 = str(_get_bet_field_value(bet, "option2") or "").strip()

    query_pairs: List[Tuple[str, str]] = [
        ("odds1", odds1),
        ("odds2", odds2),
        ("odds1Book", book1_name),
        ("odds2Book", book2_name),
        ("stake", CALC_DEFAULT_STAKE),
        ("odds1Label", book1_name),
        ("odds2Label", book2_name),
        (_calculator_book_param_name(book1_name), book1_url),
        (_calculator_book_param_name(book2_name), book2_url),
        ("Meccs", match_name),
        ("F1", option1),
        ("F2", option2),
    ]
    return f"{CALC_DYNAMIC_BASE_URL}?{urllib_parse.urlencode(query_pairs)}"


def _build_active_bet_keyboard(bet: Dict[str, Any]) -> InlineKeyboardMarkup:
    book1_source = _get_bet_bookmaker_value(bet, "book1_key", "bookmaker1")
    book2_source = _get_bet_bookmaker_value(bet, "book2_key", "bookmaker2")
    book1 = BOOKMAKER_BY_KEY.get(_resolve_bookmaker_key(book1_source))
    book2 = BOOKMAKER_BY_KEY.get(_resolve_bookmaker_key(book2_source))

    book1_name = str(bet.get("bookmaker1") or (book1.get("name", "Bookmaker 1") if book1 else "Bookmaker 1")).strip()
    book2_name = str(bet.get("bookmaker2") or (book2.get("name", "Bookmaker 2") if book2 else "Bookmaker 2")).strip()
    book1_url = _safe_url(bet.get("original_link1") or bet.get("link1") or (book1.get("url", "") if book1 else ""))
    book2_url = _safe_url(bet.get("original_link2") or bet.get("link2") or (book2.get("url", "") if book2 else ""))

    first_row: List[InlineKeyboardButton] = []
    if book1_url:
        first_row.append(InlineKeyboardButton(book1_name, url=book1_url))
    if book2_url:
        first_row.append(InlineKeyboardButton(book2_name, url=book2_url))

    rows: List[List[InlineKeyboardButton]] = []
    if first_row:
        rows.append(first_row)
    rows.append([InlineKeyboardButton("🧮 Kalkulátor", url=_build_calculator_link(bet))])
    rows.append([InlineKeyboardButton("💰 Nincs fiókod? Regisztrálj", url=AFFILIATE_LINK)])
    return InlineKeyboardMarkup(rows)


def _build_active_bet_snapshot(bet: Dict[str, Any], bet_text: str) -> str:
    """Stabil snapshot az üzenet frissítéshez (szöveg + teljes rekord tartalom)."""
    return json.dumps(
        {
            "text": bet_text,
            "bet": bet,
            "calculator_link": _build_calculator_link(bet),
        },
        sort_keys=True,
        default=str,
    )


async def _sync_active_bets_for_user_unlocked(
    user_id: int,
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    Azonnali aktív fogadás szinkron:
    - új aktív fogadások kiküldése
    - megszűnt fogadások üzenetének törlése
    """
    session = get_session(user_id)
    if not user_can_receive_bets(user_id):
        return False

    selected: Set[str] = session["selected"]  # type: ignore
    sent_message_ids: Dict[str, int] = session["active_bet_messages"]  # type: ignore
    sent_snapshots: Dict[str, str] = session["active_bet_snapshots"]  # type: ignore
    state_changed = False

    visible_bets: Dict[str, Dict[str, Any]] = {}
    selected_match_count = 0
    active_count = 0
    for bet_id, bet in ACTIVE_BETS.items():
        matches_selected = _bet_matches_selected_books(bet, selected)
        is_active = _is_bet_active(bet)
        if matches_selected:
            selected_match_count += 1
        if is_active:
            active_count += 1
        if matches_selected and is_active:
            visible_bets[bet_id] = bet

    if not visible_bets:
        if not ACTIVE_BETS:
            _log_info(
                f"ℹ️ Nincs betöltött aktív fogadás (chat_id={chat_id}). "
                f"Lehet DB kapcsolat/szinkron probléma vagy még nincs adat. "
                f"Utolsó Supabase sync: {SUPABASE_LAST_SYNC_SUMMARY}"
            )
        elif selected_match_count == 0:
            _log_info(f"ℹ️ Nincs a szűrődnek megfelelő fogadás (chat_id={chat_id}, selected={sorted(selected)}).")
        elif active_count == 0:
            _log_info(f"ℹ️ Vannak fogadások, de jelenleg egyik sem aktív (chat_id={chat_id}).")
        else:
            _log_info(f"ℹ️ Nincs jelenleg aktív és szűrőnek megfelelő fogadás egyszerre (chat_id={chat_id}).")

        if not bool(session.get("no_bets_notice_sent")):
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "ℹ️ <b>Jelenleg nincs elérhető fogadás</b> a kiválasztott irodapárosítással.\n\n"
                    "🔄 Adj hozzá több irodát a <b>/irodak</b> paranccsal, "
                    "vagy várj, amíg új arbitrázs fogadás érkezik."
                ),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            session["no_bets_notice_sent"] = True
            state_changed = True

    if visible_bets and bool(session.get("no_bets_notice_sent")):
        session["no_bets_notice_sent"] = False
        state_changed = True

    # Új fogadások küldése + módosított fogadások frissítése
    ordered_visible_bet_ids = sorted(visible_bets.keys(), key=lambda bid: _bet_created_at_sort_key(visible_bets[bid]), reverse=True)
    for bet_id in ordered_visible_bet_ids:
        bet = visible_bets[bet_id]
        bet_text = _build_active_bet_text(bet)
        if not bet_text:
            continue
        bet_snapshot = _build_active_bet_snapshot(bet, bet_text)

        if bet_id in sent_message_ids:
            previous_text = sent_snapshots.get(bet_id)
            if previous_text == bet_snapshot:
                continue
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=sent_message_ids[bet_id],
                    text=bet_text,
                    reply_markup=_build_active_bet_keyboard(bet),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                sent_snapshots[bet_id] = bet_snapshot
                state_changed = True
                _log_info(f"✏️ Fogadás frissítve (chat_id={chat_id}, bet_id={bet_id}).")
                continue
            except TelegramError as exc:
                print(f"⚠️ Bet frissítés sikertelen (chat_id={chat_id}, bet_id={bet_id}): {exc}")
                old_message_id = sent_message_ids.pop(bet_id, None)
                if old_message_id is not None:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                    except Exception:
                        pass
                sent_snapshots.pop(bet_id, None)
                state_changed = True

        message = await context.bot.send_message(
            chat_id=chat_id,
            text=bet_text,
            reply_markup=_build_active_bet_keyboard(bet),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        sent_message_ids[bet_id] = message.message_id
        sent_snapshots[bet_id] = bet_snapshot
        state_changed = True
        _log_info(f"📨 Új fogadás kiküldve (chat_id={chat_id}, bet_id={bet_id}, message_id={message.message_id}).")

    # Már nem aktív fogadások eltüntetése (üzenet törlés)
    stale_ids = sorted([bet_id for bet_id in sent_message_ids if bet_id not in visible_bets])
    for stale_id in stale_ids:
        message_id = sent_message_ids.pop(stale_id, None)
        sent_snapshots.pop(stale_id, None)
        state_changed = True
        if message_id is None:
            continue
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            _log_info(f"🗑️ Megszűnt fogadás törölve (chat_id={chat_id}, bet_id={stale_id}, message_id={message_id}).")
        except Exception:
            # Üzenet már törölve / nem törölhető - ilyenkor csak lokális cache-ből vesszük ki.
            pass

    if state_changed:
        _mark_message_state_dirty()
    return state_changed


async def sync_active_bets_for_user(
    user_id: int,
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    lock = _get_user_sync_lock(user_id)
    async with lock:
        return await _sync_active_bets_for_user_unlocked(user_id=user_id, chat_id=chat_id, context=context)



async def sync_active_bets_for_all_users(context: ContextTypes.DEFAULT_TYPE) -> None:
    any_changes = False
    # Snapshot iteráció: ha közben session változik (pl. /start), ne dobjon RuntimeError-t.
    for user_id, session in list(USER_SESSIONS.items()):
        if not bool(session.get("activated") and session.get("receive_bets")):
            continue
        try:
            user_changed = await sync_active_bets_for_user(user_id=user_id, chat_id=user_id, context=context)
            any_changes = any_changes or user_changed
        except Exception as exc:
            _log_warning(f"⚠️ User sync hiba (user_id={user_id}): {exc}")
            continue

    if any_changes:
        _persist_message_state()


def _supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_READ_KEY and SUPABASE_BETS_TABLE)


def _load_active_bets_from_supabase() -> Optional[List[Dict[str, Any]]]:
    global SUPABASE_LAST_SYNC_SUMMARY
    if not _supabase_configured():
        SUPABASE_LAST_SYNC_SUMMARY = "SUPABASE_URL/SUPABASE_READ_KEY/SUPABASE_BETS_TABLE nincs teljesen beállítva"
        _log_warning(f"⚠️ Supabase sync kihagyva: {SUPABASE_LAST_SYNC_SUMMARY}.")
        return None

    query = urllib_parse.urlencode({"select": "*", "order": "created_at.desc", "limit": SUPABASE_QUERY_LIMIT})
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_BETS_TABLE}?{query}"
    req = urllib_request.Request(
        url,
        headers={
            "apikey": SUPABASE_READ_KEY,
            "Authorization": f"Bearer {SUPABASE_READ_KEY}",
            "Accept": "application/json",
            "Prefer": "count=exact",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            payload = response.read().decode("utf-8")
            status_code = response.getcode()
            content_range = response.headers.get("Content-Range", "")
    except (urllib_error.URLError, TimeoutError, ValueError) as exc:
        SUPABASE_LAST_SYNC_SUMMARY = f"hiba: {exc}"
        _log_warning(f"⚠️ Supabase sync error: {exc}")
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        SUPABASE_LAST_SYNC_SUMMARY = "hiba: Supabase válasz JSON parse sikertelen"
        _log_warning("⚠️ Supabase sync error: JSON parse sikertelen.")
        return None

    if not isinstance(data, list):
        SUPABASE_LAST_SYNC_SUMMARY = f"hiba: válasz típusa {type(data).__name__}, nem lista"
        _log_warning(f"⚠️ Supabase sync error: a válasz nem lista típusú (kapott típus: {type(data).__name__}).")
        return None

    rows = [row for row in data if isinstance(row, dict)]
    total_rows = _extract_total_count_from_content_range(content_range)
    summary = (
        f"status={status_code}, table={SUPABASE_BETS_TABLE}, "
        f"visszaadott_sorok={len(rows)}, {SUPABASE_BETS_TABLE}_osszes_sor={total_rows if total_rows is not None else 'ismeretlen'}, "
        f"limit={SUPABASE_QUERY_LIMIT}"
    )
    SUPABASE_LAST_SYNC_SUMMARY = summary
    _log_info(f"ℹ️ Supabase sync OK: {summary}")

    if not data:
        _log_info("ℹ️ Supabase kapcsolat rendben, de az adatbázis lekérdezés 0 sort adott vissza.")

    return rows


async def sync_supabase_bets_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    bets = await asyncio.to_thread(_load_active_bets_from_supabase)
    if bets is None:
        return

    set_active_bets(bets)
    await sync_active_bets_for_all_users(context)
    _persist_message_state()


async def refresh_and_sync_user_bets(
    user_id: int,
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Azonnali Supabase frissítés + az aktuálisan elérhető fogadások kiküldése egy usernek."""
    bets = await asyncio.to_thread(_load_active_bets_from_supabase)
    if bets is not None:
        set_active_bets(bets)
    user_changed = await sync_active_bets_for_user(user_id=user_id, chat_id=chat_id, context=context)
    if user_changed:
        _persist_message_state(force=True)


def build_selection_keyboard(selected: Set[str]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    current_row: List[InlineKeyboardButton] = []

    for bm in BOOKMAKERS:
        is_selected = bm["key"] in selected
        prefix = "✅ " if is_selected else ""
        btn_text = f"{prefix}{bm['emoji']} {bm['name']}"
        current_row.append(
            InlineKeyboardButton(btn_text, callback_data=f"bm:{bm['key']}")
        )

        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    rows.append([InlineKeyboardButton("💰 Nincs fiókod? Regisztrálj", url=AFFILIATE_LINK)])
    rows.append([InlineKeyboardButton("✅ Kész", callback_data="bm_done")])
    return InlineKeyboardMarkup(rows)


def build_guide_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📘 Útmutató megnyitása", url=GUIDE_LINK)],
            [InlineKeyboardButton("✅ Okés, elolvastam az útmutatót", callback_data="guide_done")],
        ]
    )


def selection_text(selected: Set[str], is_edit_mode: bool = False) -> str:
    if not selected:
        selected_list_hu = "Még semmit nem választottál."
        selected_list_sr = "Još ništa nisi izabrao."
    else:
        pretty = []
        for bm in BOOKMAKERS:
            if bm["key"] in selected:
                pretty.append(f"{bm['emoji']} {bm['name']}")
        selected_list_hu = "\n".join(pretty)
        selected_list_sr = selected_list_hu

    if is_edit_mode:
        header_hu = "⚙️ <b>GoldenTipsHungary</b> • Szűrők módosítása"
        header_sr = "⚙️ <b>GoldenTipsHungary</b> • Izmena filtera"
    else:
        header_hu = "✅ <b>GoldenTipsHungary</b> • Aktiváció sikeres"
        header_sr = "✅ <b>GoldenTipsHungary</b> • Aktivacija uspešna"

    hu = (
        f"{header_hu}\n\n"
        "Add meg, mely irodáknál vagy regisztrálva\n"
        "(többet is kiválaszthatsz, de maximum 6-ot), majd nyomd meg a <b>✅ Kész</b> gombot.\n\n"
        f"💰 Nincs fiókod valamelyik irodánál? <a href=\"{AFFILIATE_LINK}\"><b>Itt tudsz regisztrálni</b></a>.\n\n"
        f"📘 Ha valami nem tiszta, <a href=\"{GUIDE_LINK}\"><b>olvasd el az útmutatót</b></a>.\n\n"
        f"<b>Kiválasztott irodák:</b>\n{selected_list_hu}"
    )
    sr = (
        f"{header_sr}\n\n"
        "Izaberi kod kojih kladionica si registrovan\n"
        "(možeš izabrati više, ali najviše 6), pa klikni na dugme <b>✅ Kész</b>.\n\n"
        f"💰 Nemaš nalog kod neke kladionice? <a href=\"{AFFILIATE_LINK}\"><b>Registruj se ovde</b></a>.\n\n"
        f"📘 Ako nešto nije jasno, <a href=\"{GUIDE_LINK}\"><b>pročitaj uputstvo</b></a>.\n\n"
        f"<b>Izabrane kladionice:</b>\n{selected_list_sr}"
    )
    _ = sr
    return hu


def build_demo_bet_text(book1: dict, book2: dict) -> str:
    return (
        "🔒 <b>ÚJ ARBITRÁZS FOGADÁS</b>\n\n"
        "💸 <b>Profit:</b> 8.97%\n"
        "🟢 <b>STÁTUSZ:</b> AKTÍV\n"
        "📅 <b>Dátum:</b> Április 6, 14:00 • ⏳ <code>2 órán múlva</code>\n\n"
        f"{book1['emoji']} <a href=\"{book1['url']}\"><b>{book1['name']}</b></a>\n"
        f"<b>Mérkőzés:</b> <a href=\"{MATCH_LINK}\">Ferencváros - Újpest</a>\n"
        "<b>Fogadás:</b> Kevesebb mint -> 2.5 - Gólok\n"
        "<b>Odds:</b> 1.95\n\n"
        f"{book2['emoji']} <a href=\"{book2['url']}\"><b>{book2['name']}</b></a>\n"
        f"<b>Mérkőzés:</b> <a href=\"{MATCH_LINK}\">Ferencváros - Újpest</a>\n"
        "<b>Fogadás:</b> Több mint -> 2.5 - Gólok\n"
        "<b>Odds:</b> 2.47\n\n"
        "━━━━━━━━━━━━━━━\n"
        "⚙️ Szűrő módosítás: <b>/irodak</b>"
    )


def build_demo_bet_keyboard(book1: dict, book2: dict) -> InlineKeyboardMarkup:
    # Felső sorban a kiválasztott 2 iroda gombja
    # Alatta marad a régi Kalkulátor + Nincs fiókod gomb
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{book1['emoji']} {book1['name']}", url=book1["url"]),
                InlineKeyboardButton(f"{book2['emoji']} {book2['name']}", url=book2["url"]),
            ],
            [
                InlineKeyboardButton("🧮 Kalkulátor", url=CALC_LINK),
            ],
            [
                InlineKeyboardButton("💰 Nincs fiókod? Regisztrálj", url=AFFILIATE_LINK),
            ],
        ]
    )


# =========================
# HANDLERS
# =========================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    # Csak privát chat
    if update.effective_chat and update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    USER_SESSIONS[user_id] = {
        "state": "awaiting_code",
        "selected": set(),
        "activated": False,
        "receive_bets": False,
        "active_bet_messages": {},
        "active_bet_snapshots": {},
        "no_bets_notice_sent": False,
    }
    _mark_message_state_dirty()
    _persist_message_state(force=True)

    await update.message.reply_text(
        "👋 <b>Üdvözlünk a GoldenTipsHungary rendszerében!</b>\n\n"
        "Kérlek add meg a vásárláshoz kapott <b>aktivációs kódodat</b> az induláshoz.",
        parse_mode=ParseMode.HTML,
    )


async def filters_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    # Csak privát chat
    if update.effective_chat and update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    session = get_session(user_id)

    if not session.get("activated"):
        await update.message.reply_text(
            "Először aktiváld a fiókodat a /start paranccsal.",
            parse_mode=ParseMode.HTML,
        )
        return

    session["state"] = "selecting_books"
    session["receive_bets"] = False
    selected: Set[str] = session["selected"]  # type: ignore

    await update.message.reply_text(
        text=selection_text(selected, is_edit_mode=True),
        parse_mode=ParseMode.HTML,
        reply_markup=build_selection_keyboard(selected),
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    # Csak privát chat
    if update.effective_chat and update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    session = get_session(user_id)
    text = (update.message.text or "").strip()

    state = session.get("state")

    if state == "awaiting_code":
        if ACTIVATION_SERVICE.has_valid_code(text):
            previous_owner_id = ACTIVATION_SERVICE.bind_code_to_user(text, user_id)

            if previous_owner_id is not None:
                USER_SESSIONS[previous_owner_id] = {
                    "state": "awaiting_code",
                    "selected": set(),
                    "activated": False,
                    "receive_bets": False,
                    "active_bet_messages": {},
                    "active_bet_snapshots": {},
                    "no_bets_notice_sent": False,
                }
                _mark_message_state_dirty()
                _persist_message_state(force=True)

            session["activated"] = True
            session["state"] = "awaiting_guide"
            session["receive_bets"] = False

            await update.message.reply_text(
                text=(
                    "📘 <b>Mielőtt elkezdenél fogadni</b>, érdemes elolvasni az útmutatónkat.\n"
                    "Csak 5–6 perc, rengeteg kezdőhibát segít elkerülni, "
                    "és a praktikákkal több pénzt is tudsz keresni."
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=build_guide_keyboard(),
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text(
                "❌ <b>GoldenTipsHungary</b>\n"
                "Hibás aktivációs kód.\n\n"
                "Próbáld újra (teszt kód: <b>123</b>).",
                parse_mode=ParseMode.HTML,
            )
        return

    await update.message.reply_text(
        "Ahhoz, hogy újra kapj fogadásokat, kérlek írd be: /start",
        parse_mode=ParseMode.HTML,
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is None or update.effective_user is None:
        return

    query = update.callback_query
    user_id = update.effective_user.id
    session = get_session(user_id)

    data = query.data or ""
    selected: Set[str] = session["selected"]  # type: ignore

    # Először mindenképp válaszoljunk callbackre (Telegram UX)
    # (A konkrét üzenetet később is adhatjuk)
    # Itt csak akkor adunk azonnali választ, amikor biztos a branch.

    if data == "guide_done":
        if session.get("state") != "awaiting_guide":
            await query.answer("Először /start és aktivációs kód szükséges.", show_alert=True)
            return

        session["state"] = "selecting_books"
        selected: Set[str] = session["selected"]  # type: ignore

        await query.answer("Szuper! Jöhetnek a kiválasztott irodák ✅")
        await query.edit_message_text(
            text="✅ Útmutató visszaigazolva.",
            parse_mode=ParseMode.HTML,
        )
        if query.message is not None:
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=selection_text(selected, is_edit_mode=False),
                parse_mode=ParseMode.HTML,
                reply_markup=build_selection_keyboard(selected),
                disable_web_page_preview=True,
            )
        return

    if session.get("state") not in {"selecting_books", "ready"}:
        await query.answer("Először /start és aktivációs kód szükséges.", show_alert=True)
        return

    if data == "open_filters":
        if not session.get("activated"):
            await query.answer("Először /start és aktivációs kód szükséges.", show_alert=True)
            return

        session["state"] = "selecting_books"
        session["receive_bets"] = False
        await query.answer("Szűrőmódosítás megnyitva ⚙️")
        await query.edit_message_text(
            text=selection_text(selected, is_edit_mode=True),
            parse_mode=ParseMode.HTML,
            reply_markup=build_selection_keyboard(selected),
        )
        return

    if data.startswith("bm:"):
        key = data.split(":", 1)[1]
        if key not in BOOKMAKER_BY_KEY:
            await query.answer("Ismeretlen iroda.", show_alert=True)
            return

        if key in selected:
            selected.remove(key)
            await query.answer("Eltávolítva ✅")
        else:
            if len(selected) >= MAX_SELECTED_BOOKMAKERS:
                await query.answer(f"Maximum {MAX_SELECTED_BOOKMAKERS} irodát választhatsz.", show_alert=True)
                return
            selected.add(key)
            await query.answer("Hozzáadva ✅")

        await query.edit_message_text(
            text=selection_text(selected),
            parse_mode=ParseMode.HTML,
            reply_markup=build_selection_keyboard(selected),
        )
        return

    if data == "bm_done":
        if len(selected) < 2:
            await query.answer("Válassz legalább 2 irodát az arbitrázshoz.", show_alert=True)
            return
        if len(selected) > MAX_SELECTED_BOOKMAKERS:
            await query.answer(f"Maximum {MAX_SELECTED_BOOKMAKERS} irodát választhatsz.", show_alert=True)
            return

        session["state"] = "ready"
        session["receive_bets"] = True
        session["active_bet_messages"] = {}
        session["active_bet_snapshots"] = {}
        session["no_bets_notice_sent"] = False
        _mark_message_state_dirty()
        _persist_message_state(force=True)

        await query.answer("GoldenTipsHungary tipp érkezik 🚀")

        await query.edit_message_text(
            text=(
                "✅ <b>GoldenTipsHungary</b>\n"
                "Irodák elmentve!\n\n"
                "Ha módosítanád, hogy melyik irodákról kapj értesítést, írd be a chatbe: <b>/irodak</b>\n"
                f"📘 Útmutató: <a href=\"{GUIDE_LINK}\"><b>Itt tudod elolvasni</b></a>.\n\n"
                "Küldöm a jelenleg aktív fogadásokat..."
            ),
            parse_mode=ParseMode.HTML,
        )

        if query.message is not None:
            print(f"ℹ️ Kezdeti aktív fogadás szinkron indul (chat_id={query.message.chat.id}, selected={sorted(selected)}).")
            await refresh_and_sync_user_bets(user_id=user_id, chat_id=query.message.chat.id, context=context)
        return

    await query.answer("Ismeretlen művelet.")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "/start - GoldenTipsHungary flow indítása\n"
        "/irodak - szűrt irodák módosítása\n"
        "/help - segítség"
    )



def _collect_shutdown_notice_user_ids() -> List[int]:
    user_ids: Set[int] = set()

    for user_id, session in USER_SESSIONS.items():
        if bool(session.get("activated") and session.get("receive_bets")):
            user_ids.add(user_id)

    for raw_user_id in PERSISTED_MESSAGE_STATE.keys():
        if isinstance(raw_user_id, int):
            user_ids.add(raw_user_id)

    return sorted(user_ids)


def _send_startup_restart_notice_sync() -> None:
    if os.getenv("DISABLE_STARTUP_RESTART_NOTICE", "").strip().lower() in {"1", "true", "yes"}:
        return

    user_ids = _collect_shutdown_notice_user_ids()
    if not user_ids:
        return

    message_text = "Ahhoz, hogy újra kapj fogadásokat, kérlek írd be: /start"

    for chat_id in user_ids:
        payload = urllib_parse.urlencode({
            "chat_id": str(chat_id),
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib_request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=5):
                pass
        except Exception as exc:
            _log_warning(f"⚠️ Indulási /start értesítés sikertelen (chat_id={chat_id}): {exc}")




# =========================
# MAIN
# =========================
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("irodak", filters_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    if _supabase_configured() and app.job_queue is not None:
        app.job_queue.run_repeating(sync_supabase_bets_job, interval=SUPABASE_SYNC_INTERVAL_SECONDS, first=1)

    _send_startup_restart_notice_sync()

    print("✅ GoldenTipsHungary bot elindult (polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
