"""Утилиты: время, конвертация, кеш курсов, заглушка Parser Service."""
from __future__ import annotations

from datetime import datetime, timedelta

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
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def is_fresh(updated_at: str, ttl: timedelta | None = None) -> bool:
    ttl = ttl or _settings.rates_ttl
    try:
        return datetime.now() - parse_iso(updated_at) < ttl
    except (TypeError, ValueError):
        return False


# ---------------------- Внутренняя заглушка ----------------------

def _refresh_rates() -> dict:
    """Заглушка обновления вместо Parser Service."""
    rates = _db.load_rates() or {}
    ts = now_iso()
    for pair, rate in DEFAULT_EXCHANGE_RATES.items():
        rates[pair] = {"rate": rate, "updated_at": ts}
    rates["source"] = "Stub"
    rates["last_refresh"] = ts
    _db.save_rates(rates)
    return rates


# ---------------------- Публичный контракт ----------------------

def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Возвращает (rate, updated_at). Валидирует коды через реестр."""
    # Валидация: коды должны быть известны (иначе CurrencyNotFoundError)
    get_currency(from_code)
    get_currency(to_code)

    f = from_code.strip().upper()
    t = to_code.strip().upper()
    if f == t:
        return 1.0, now_iso()

    rates = _db.load_rates()
    direct_key, inverse_key = f"{f}_{t}", f"{t}_{f}"

    for key, invert in ((direct_key, False), (inverse_key, True)):
        entry = rates.get(key)
        if isinstance(entry, dict) and "rate" in entry \
                and is_fresh(entry.get("updated_at", "")):
            rate = float(entry["rate"])
            return (1.0 / rate if invert else rate), entry["updated_at"]

    # Нет свежего — обновляем (заглушка)
    try:
        refreshed = _refresh_rates()
    except OSError as exc:
        raise ApiRequestError(str(exc)) from exc

    for key, invert in ((direct_key, False), (inverse_key, True)):
        entry = refreshed.get(key)
        if isinstance(entry, dict) and "rate" in entry:
            rate = float(entry["rate"])
            return (1.0 / rate if invert else rate), entry["updated_at"]

    raise ApiRequestError(f"курс {f}→{t} недоступен")


def get_rates_map() -> dict[str, float]:
    rates = _db.load_rates()
    if not rates or "last_refresh" not in rates:
        rates = _refresh_rates()
    return {
        k: float(v["rate"]) for k, v in rates.items()
        if isinstance(v, dict) and "rate" in v
    }


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