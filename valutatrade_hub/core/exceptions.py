"""Пользовательские исключения ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовое исключение домена (для общих перехватов)."""


class CurrencyNotFoundError(ValutaTradeError):
    """Неизвестный код валюты. Ловится в CLI, чтобы подсказать список кодов."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке при списании."""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class ApiRequestError(ValutaTradeError):
    """Сбой при получении курса из внешнего источника."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")