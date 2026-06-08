"""Telegram bot constants."""

# How long to wait on each getUpdates long-poll request (seconds)
TELEGRAM_POLL_TIMEOUT: int = 30

# Maximum length of a single Telegram message (server limit is 4096)
MAX_MESSAGE_LENGTH: int = 4000

# HTTP request timeout for calls to Onyx API (seconds)
API_REQUEST_TIMEOUT: int = 3 * 60  # 3 minutes

# How long to sleep between polling retries when an error occurs (seconds)
POLL_RETRY_SLEEP: int = 5
