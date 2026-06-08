"""Custom exception classes for Telegram bot."""


class TelegramBotError(Exception):
    """Base exception for Telegram bot errors."""


class TelegramAPIError(TelegramBotError):
    """Error returned by the Telegram Bot API."""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class OnyxAPIConnectionError(TelegramBotError):
    """Failed to connect to the Onyx API server."""


class OnyxAPITimeoutError(TelegramBotError):
    """Request to the Onyx API server timed out."""


class OnyxAPIResponseError(TelegramBotError):
    """Onyx API server returned an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
