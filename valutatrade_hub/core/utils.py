"""Утилиты: JSON I/O, валидаторы, кеш курсов."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Корень проекта: .../finalproject_<...>/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"

RATE_TTL = timedelta(minutes=5)

# Заглушка, пока Parser Service не подключён
DEFAULT_EXCHANGE_RATES: dict[str, float] = {
    "EUR_USD": 1.0786,
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "RUB_USD": 0.01016,
}


# ---------------------- JSON ----------------------

def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data: Any) -> None:
    ensure_data_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # атомарная замена


# ---------------------- Валидаторы ----------------------

def validate_currency_code(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


def validate_positive_amount(amount: float) -> float:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("'amount' должен быть числом")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


# ---------------------- Время ----------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def is_fresh(updated_at: str, ttl: timedelta = RATE_TTL) -> bool:
    try:
        return datetime.now() - parse_iso(updated_at) < ttl
    except (TypeError, ValueError):
        return False


# ---------------------- Курсы ----------------------

def _load_rates() -> dict[str, dict]:
    return load_json(RATES_FILE, {})


def _save_rates(rates: dict[str, dict]) -> None:
    save_json(RATES_FILE, rates)


def _build_stub_rates() -> dict[str, dict]:
    ts = now_iso()
    return {pair: {"rate": rate, "updated_at": ts}
            for pair, rate in DEFAULT_EXCHANGE_RATES.items()}


def _refresh_rates() -> dict[str, dict]:
    """Заглушка обновления: подмешиваем DEFAULT_EXCHANGE_RATES."""
    rates = _load_rates() or {}
    rates.update(_build_stub_rates())
    rates["source"] = "Stub"
    rates["last_refresh"] = now_iso()
    _save_rates(rates)
    return rates


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Возвращает (rate, updated_at). Прямой курс или обратный (1/x)."""
    f = validate_currency_code(from_code)
    t = validate_currency_code(to_code)
    if f == t:
        return 1.0, now_iso()

    rates = _load_rates()
    direct_key, inverse_key = f"{f}_{t}", f"{t}_{f}"

    entry = rates.get(direct_key)
    if entry and is_fresh(entry["updated_at"]):
        return float(entry["rate"]), entry["updated_at"]

    inv = rates.get(inverse_key)
    if inv and is_fresh(inv["updated_at"]):
        return 1.0 / float(inv["rate"]), inv["updated_at"]

    # Устарело/нет → обновляем (заглушка)
    refreshed = _refresh_rates()
    entry = refreshed.get(direct_key)
    if entry:
        return float(entry["rate"]), entry["updated_at"]
    inv = refreshed.get(inverse_key)
    if inv:
        return 1.0 / float(inv["rate"]), inv["updated_at"]

    raise ValueError(f"Не удалось получить курс для {f}→{t}")


def get_rates_map() -> dict[str, float]:
    """{ 'EUR_USD': 1.07, ... } — удобно для Portfolio.get_total_value()."""
    rates = _load_rates()
    if not rates or "last_refresh" not in rates:
        rates = _refresh_rates()
    return {k: float(v["rate"]) for k, v in rates.items()
            if isinstance(v, dict) and "rate" in v}