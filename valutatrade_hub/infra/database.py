"""Singleton DatabaseManager — абстракция над JSON-хранилищем.

Все чтения — безопасные (возвращают default при повреждении файла).
Все записи — атомарные (tmp + os.replace).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .settings import SettingsLoader


class DatabaseManager:
    _instance: "DatabaseManager | None" = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # type: ignore[attr-defined]
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:  # type: ignore[has-type]
            return
        self._initialized = True  # type: ignore[has-type]
        self._settings = SettingsLoader()
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)

    # --- низкоуровневые ---
    def _path(self, filename: str) -> Path:
        return self._settings.data_dir / filename

    def read(self, filename: str, default: Any) -> Any:
        p = self._path(filename)
        if not p.exists():
            return default
        try:
            with p.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default

    def write(self, filename: str, data: Any) -> None:
        p = self._path(filename)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)

    # --- доменные методы ---
    def load_users(self) -> list[dict]:
        return self.read(self._settings.get("users_file"), [])

    def save_users(self, users: list[dict]) -> None:
        self.write(self._settings.get("users_file"), users)

    def load_portfolios(self) -> list[dict]:
        return self.read(self._settings.get("portfolios_file"), [])

    def save_portfolios(self, portfolios: list[dict]) -> None:
        self.write(self._settings.get("portfolios_file"), portfolios)

    def load_rates(self) -> dict:
        return self.read(self._settings.get("rates_file"), {})

    def save_rates(self, rates: dict) -> None:
        self.write(self._settings.get("rates_file"), rates)