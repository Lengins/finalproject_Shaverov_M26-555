"""RatesUpdater — координация клиентов и сохранение результата."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from ..core.exceptions import ApiRequestError
from .api_clients import BaseApiClient
from .storage import ParserStorage

logger = logging.getLogger("valutatrade.parser")


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class RatesUpdater:
    def __init__(self, clients: list[BaseApiClient], storage: ParserStorage) -> None:
        self._clients = clients
        self._storage = storage

    def run_update(self, source_filter: str | None = None) -> dict:
        logger.info("Starting rates update...")
        ts = _utc_now_iso()
        merged: dict[str, dict] = {}
        history: list[dict] = []
        by_source: dict[str, int] = {}
        errors: list[str] = []

        for client in self._clients:
            if source_filter and client.source_alias != source_filter.lower():
                continue
            name = client.source_name
            logger.info("Fetching from %s...", name)
            try:
                rates = client.fetch_rates()
            except ApiRequestError as exc:
                by_source[name] = 0
                errors.append(str(exc))
                logger.error("Failed to fetch from %s: %s", name, exc)
                continue

            for pair, rate in rates.items():
                try:
                    from_code, to_code = pair.split("_", 1)
                except ValueError:
                    continue
                merged[pair] = {"rate": rate, "updated_at": ts, "source": name}
                history.append({
                    "id": f"{from_code}_{to_code}_{ts}",
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": rate,
                    "timestamp": ts,
                    "source": name,
                    "meta": {"status_code": 200},
                })
            by_source[name] = len(rates)
            logger.info("Fetching from %s... OK (%d rates)", name, len(rates))

        if merged:
            self._storage.save_snapshot(merged, ts)
            logger.info("Writing %d rates to %s", len(merged), self._storage._rates_path)
        if history:
            added = self._storage.append_history(history)
            logger.info("Appended %d history records", added)

        return {
            "total": len(merged),
            "by_source": by_source,
            "errors": errors,
            "last_refresh": ts,
        }