"""Thin async wrapper around the Telegram Bot HTTP API."""

from typing import Any

import aiohttp

from onyx.onyxbot.telegram.constants import TELEGRAM_POLL_TIMEOUT
from onyx.onyxbot.telegram.exceptions import TelegramAPIError
from onyx.utils.logger import setup_logger

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

logger = setup_logger()


class TelegramAPI:
    """Minimal async client for the Telegram Bot API.

    Only the endpoints needed by the personal-assistant bot are implemented:
    getUpdates (long polling) and sendMessage.
    """

    def __init__(self, token: str) -> None:
        self._base = f"{TELEGRAM_API_BASE}{token}"
        self._session: aiohttp.ClientSession | None = None

    async def initialize(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("TelegramAPI not initialized — call initialize() first")
        url = f"{self._base}/{method}"
        async with self._session.post(url, json=payload) as resp:
            data: dict[str, Any] = await resp.json()
        if not data.get("ok"):
            raise TelegramAPIError(
                data.get("description", "Telegram API error"),
                error_code=data.get("error_code"),
            )
        return data

    async def get_updates(self, offset: int, timeout: int = TELEGRAM_POLL_TIMEOUT) -> list[dict[str, Any]]:
        """Long-poll for new updates starting after *offset*."""
        data = await self._post(
            "getUpdates",
            {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
        )
        result: list[dict[str, Any]] = data.get("result", [])
        return result

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a plain-text message to a chat."""
        if not text.strip():
            return
        await self._post("sendMessage", {"chat_id": chat_id, "text": text})

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        """Show a chat action (e.g. typing indicator) in the chat."""
        try:
            await self._post("sendChatAction", {"chat_id": chat_id, "action": action})
        except TelegramAPIError as e:
            logger.warning("sendChatAction failed: %s", e)
