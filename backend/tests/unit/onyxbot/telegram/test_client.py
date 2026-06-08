"""Unit tests for the Telegram bot client module.

These tests verify:
- Incoming Telegram updates are correctly routed to the Onyx API.
- The Onyx response is sent back via Telegram sendMessage.
- Long responses are chunked within Telegram's message length limit.
- Messages from unauthorized chat IDs are silently dropped.
"""

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from onyx.chat.models import ChatFullResponse
from onyx.onyxbot.telegram.client import _chunk_text, _handle_update, _is_chat_allowed
from onyx.onyxbot.telegram.constants import MAX_MESSAGE_LENGTH


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text_short_message() -> None:
    """Messages shorter than the limit are returned as-is."""
    result = _chunk_text("hello", max_length=100)
    assert result == ["hello"]


def test_chunk_text_long_message() -> None:
    """Messages exceeding the limit are split into equal-sized chunks."""
    text = "a" * 250
    chunks = _chunk_text(text, max_length=100)
    assert len(chunks) == 3
    assert chunks[0] == "a" * 100
    assert chunks[1] == "a" * 100
    assert chunks[2] == "a" * 50
    assert "".join(chunks) == text


# ---------------------------------------------------------------------------
# _is_chat_allowed
# ---------------------------------------------------------------------------


def test_is_chat_allowed_empty_allowlist() -> None:
    """Empty allowlist lets everyone through."""
    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", set()):
        assert _is_chat_allowed(999) is True


def test_is_chat_allowed_matching_id() -> None:
    """Chat ID in the allowlist is permitted."""
    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", {42, 100}):
        assert _is_chat_allowed(42) is True


def test_is_chat_allowed_non_matching_id() -> None:
    """Chat ID not in the allowlist is rejected."""
    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", {42}):
        assert _is_chat_allowed(99) is False


# ---------------------------------------------------------------------------
# _handle_update
# ---------------------------------------------------------------------------


def _make_chat_response(answer: str) -> ChatFullResponse:
    return ChatFullResponse(
        answer=answer,
        answer_citationless=answer,
        top_documents=[],
        citation_info=[],
        message_id=0,
    )


@pytest.mark.asyncio
async def test_handle_update_sends_reply() -> None:
    """A valid text message is forwarded to Onyx and the answer sent back."""
    update = {"update_id": 1, "message": {"chat": {"id": 123}, "text": "What time is it?"}}

    telegram = MagicMock()
    telegram.send_chat_action = AsyncMock()
    telegram.send_message = AsyncMock()

    onyx = MagicMock()
    onyx.send_chat_message = AsyncMock(return_value=_make_chat_response("It's 3pm."))

    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", set()):
        await _handle_update(update, telegram, onyx)  # type: ignore[arg-type]

    onyx.send_chat_message.assert_awaited_once_with("What time is it?")
    telegram.send_message.assert_awaited_once_with(123, "It's 3pm.")


@pytest.mark.asyncio
async def test_handle_update_drops_unauthorized_chat() -> None:
    """Updates from unauthorized chat IDs are dropped without contacting Onyx."""
    update = {"update_id": 2, "message": {"chat": {"id": 999}, "text": "Hello"}}

    telegram = MagicMock()
    telegram.send_message = AsyncMock()
    onyx = MagicMock()
    onyx.send_chat_message = AsyncMock()

    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", {42}):
        await _handle_update(update, telegram, onyx)  # type: ignore[arg-type]

    onyx.send_chat_message.assert_not_awaited()
    telegram.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_update_ignores_no_text() -> None:
    """Updates without text (e.g. stickers, photos) are silently ignored."""
    update = {"update_id": 3, "message": {"chat": {"id": 42}}}

    telegram = MagicMock()
    onyx = MagicMock()
    onyx.send_chat_message = AsyncMock()

    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", set()):
        await _handle_update(update, telegram, onyx)  # type: ignore[arg-type]

    onyx.send_chat_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_update_long_response_is_chunked() -> None:
    """Responses longer than MAX_MESSAGE_LENGTH are split into multiple send_message calls."""
    long_answer = "x" * (MAX_MESSAGE_LENGTH + 50)
    update = {"update_id": 4, "message": {"chat": {"id": 42}, "text": "Explain everything"}}

    telegram = MagicMock()
    telegram.send_chat_action = AsyncMock()
    telegram.send_message = AsyncMock()
    onyx = MagicMock()
    onyx.send_chat_message = AsyncMock(return_value=_make_chat_response(long_answer))

    with patch("onyx.onyxbot.telegram.client.TELEGRAM_ALLOWED_CHAT_IDS", set()):
        await _handle_update(update, telegram, onyx)  # type: ignore[arg-type]

    assert telegram.send_message.await_count == 2
