"""Singleton SettingsLoader — единая точка конфигурации проекта.

Реализован через __new__, а не метакласс: проще и читабельнее, а метакласс
даёт избыточную гибкость для одной задачи «ровно один экземпляр».
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def _find_project_root() -> Path:
    """Ищем вверх по дереву, пока не найдём pyproject.toml."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parents[2]  # fallback


class SettingsLoader:
    _instance: "SettingsLoader | None" = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # type: ignore[attr-defined]
        return cls._instance

    def __init__(self, config_path: Path | None = None) -> None:
        if self._initialized:  # type: ignore[has-type]
            return
        self._initialized = True  # type: ignore[has-type]
        self._config_path = config_path
        self._data: dict[str, Any] = {}
        self._load()

    # --- загрузка ---
    def _load(self) -> None:
        root = _find_project_root()
        defaults: dict[str, Any] = {
            "data_dir": str(root / "data"),
            "users_file": "users.json",
            "portfolios_file": "portfolios.json",
            "rates_file": "rates.json",
            "rates_ttl_seconds": 300,
            "base_currency": "USD",
            "log_dir": str(root / "logs"),
            "log_file": "actions.log",
            "log_level": "INFO",
            "log_format": "text",          # "text" | "json"
            "log_max_bytes": 1_000_000,
            "log_backup_count": 3,
        }

        # 1) pyproject.toml → [tool.valutatrade]
        if tomllib is not None:
            pyproject = root / "pyproject.toml"
            if pyproject.exists():
                try:
                    with pyproject.open("rb") as f:
                        cfg = tomllib.load(f)
                    defaults.update(cfg.get("tool", {}).get("valutatrade", {}))
                except (OSError, ValueError):
                    pass

        # 2) config.json (приоритетнее pyproject.toml, если оба есть)
        config_file = self._config_path or (root / "config.json")
        if config_file and config_file.exists():
            try:
                with config_file.open(encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except (OSError, json.JSONDecodeError):
                pass

        self._data = defaults

    # --- публичный интерфейс ---
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def reload(self) -> None:
        self._load()

    # --- удобные свойства ---
    @property
    def data_dir(self) -> Path:
        return Path(self._data["data_dir"])

    @property
    def base_currency(self) -> str:
        return str(self._data["base_currency"])

    @property
    def rates_ttl(self) -> timedelta:
        return timedelta(seconds=int(self._data["rates_ttl_seconds"]))