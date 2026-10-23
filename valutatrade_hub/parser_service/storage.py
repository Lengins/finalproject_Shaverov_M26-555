"""Атомарное чтение/запись rates.json (snapshot) и exchange_rates.json (history)."""
from __future__ import annotations

import json
import os
from pathlib import Path


class ParserStorage:
    def __init__(self, rates_path: Path, history_path: Path) -> None:
        self._rates_path = rates_path
        self._history_path = history_path

    # --- rates.json ---
    def save_snapshot(self, pairs: dict[str, dict], last_refresh: str) -> None:
        self._atomic_write(self._rates_path,
                           {"pairs": pairs, "last_refresh": last_refresh})

    def load_snapshot(self) -> dict:
        if not self._rates_path.exists():
            return {"pairs": {}, "last_refresh": None}
        try:
            with self._rates_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"pairs": {}, "last_refresh": None}

    # --- exchange_rates.json ---
    def append_history(self, records: list[dict]) -> int:
        history = self.load_history()
        seen = {r.get("id") for r in history}
        added = 0
        for rec in records:
            if rec["id"] not in seen:
                history.append(rec)
                seen.add(rec["id"])
                added += 1
        self._atomic_write(self._history_path, history)
        return added

    def load_history(self) -> list[dict]:
        if not self._history_path.exists():
            return []
        try:
            with self._history_path.open(encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    # --- утилита ---
    @staticmethod
    def _atomic_write(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)