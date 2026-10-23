"""Утилиты: время, конвертация, кеш курсов, заглушка Parser Service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..infra.database import DatabaseManager
from ..infra.settings import SettingsLoader
from .currencies import get_currency
from .exceptions import ApiRequestError, CurrencyNotFoundError

# Заглушка источника курсов (пока Parser Service не подключён)
DEFAULT_EXCHANGE_RATES: dict[str, float] = {
    "EUR_USD": 1.0786,
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "RUB_USD": 0.01016,
    "GBP_USD": 1.27,
}

_db = DatabaseManager()
_settings = SettingsLoader()


# ---------------------- Время ----------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def is_fresh(updated_at: str, ttl: timedelta | None = None) -> bool:
    ttl = ttl or _settings.rates_ttl
    try:
        dt = parse_iso(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt < ttl
    except (TypeError, ValueError):
        return False


# ---------------------- Внутренняя заглушка ----------------------

def _refresh_rates() -> dict:
    """Fallback-заглушка, если Parser Service не запускался."""
    raw = _db.load_rates() or {}
    pairs = dict(raw.get("pairs", raw))
    ts = now_iso()
    for pair, rate in DEFAULT_EXCHANGE_RATES.items():
        pairs[pair] = {"rate": rate, "updated_at": ts, "source": "Stub"}
    data = {"pairs": pairs, "last_refresh": ts}
    _db.save_rates(data)
    return data


# ---------------------- Публичный контракт ----------------------

def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    get_currency(from_code)
    get_currency(to_code)
    f, t = from_code.strip().upper(), to_code.strip().upper()
    if f == t:
        return 1.0, now_iso()

    raw = _db.load_rates()
    pairs = raw.get("pairs", raw) if isinstance(raw, dict) else {}
    direct_key, inverse_key = f"{f}_{t}", f"{t}_{f}"

    for key, invert in ((direct_key, False), (inverse_key, True)):
        entry = pairs.get(key)
        if isinstance(entry, dict) and "rate" in entry \
                and is_fresh(entry.get("updated_at", "")):
            rate = float(entry["rate"])
            return (1.0 / rate if invert else rate), entry["updated_at"]

    try:
        refreshed = _refresh_rates()
    except OSError as exc:
        raise ApiRequestError(str(exc)) from exc

    pairs = refreshed.get("pairs", {})
    for key, invert in ((direct_key, False), (inverse_key, True)):
        entry = pairs.get(key)
        if isinstance(entry, dict) and "rate" in entry:
            rate = float(entry["rate"])
            return (1.0 / rate if invert else rate), entry["updated_at"]
    raise ApiRequestError(f"курс {f}→{t} недоступен")


def get_rates_map() -> dict[str, float]:
    raw = _db.load_rates()
    pairs = raw.get("pairs", raw) if isinstance(raw, dict) else {}
    if not pairs:
        pairs = _refresh_rates().get("pairs", {})
    return {k: float(v["rate"]) for k, v in pairs.items()
            if isinstance(v, dict) and "rate" in v}


def validate_positive_amount(amount: float) -> float:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("'amount' должен быть числом")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


__all__ = [
    "DEFAULT_EXCHANGE_RATES",
    "now_iso",
    "parse_iso",
    "is_fresh",
    "get_rate",
    "get_rates_map",
    "validate_positive_amount",
    "CurrencyNotFoundError",
]