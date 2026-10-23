"""Простейший планировщик периодического обновления (без внешних зависимостей)."""
from __future__ import annotations

import logging
import time

from .updater import RatesUpdater

logger = logging.getLogger("valutatrade.parser")


def start_scheduler(updater: RatesUpdater, interval_seconds: int = 300,
                    max_iterations: int | None = None) -> None:
    iteration = 0
    logger.info("Scheduler started: interval=%ds", interval_seconds)
    while max_iterations is None or iteration < max_iterations:
        try:
            result = updater.run_update()
            logger.info("Iteration %d: %d rates, %d errors",
                        iteration, result["total"], len(result["errors"]))
        except Exception:  # noqa: BLE001 — scheduler не должен падать
            logger.exception("Scheduler iteration %d failed", iteration)
        iteration += 1
        if max_iterations is not None and iteration >= max_iterations:
            break
        time.sleep(interval_seconds)
    logger.info("Scheduler stopped after %d iterations", iteration)