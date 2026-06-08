"""Telegram bot — personal OpenNex assistant."""

import asyncio
import time

from onyx.configs.app_configs import TELEGRAM_ALLOWED_CHAT_IDS
from onyx.configs.app_configs import TELEGRAM_BOT_API_KEY
from onyx.configs.app_configs import TELEGRAM_BOT_TOKEN
from onyx.configs.app_configs import TELEGRAM_PERSONA_ID
from onyx.onyxbot.telegram.api_client import OnyxAPIClient
from onyx.onyxbot.telegram.constants import MAX_MESSAGE_LENGTH
from onyx.onyxbot.telegram.constants import POLL_RETRY_SLEEP
from onyx.onyxbot.telegram.exceptions import OnyxAPIConnectionError
from onyx.onyxbot.telegram.exceptions import OnyxAPIResponseError
from onyx.onyxbot.telegram.exceptions import OnyxAPITimeoutError
from onyx.onyxbot.telegram.exceptions import TelegramAPIError
from onyx.onyxbot.telegram.telegram_api import TelegramAPI
from onyx.utils.logger import setup_logger

logger = setup_logger()


def _chunk_text(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long response into chunks that fit within Telegram's message limit."""
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_length])
        text = text[max_length:]
    return chunks


def _is_chat_allowed(chat_id: int) -> bool:
    """Return True if *chat_id* is in the allowlist, or if the allowlist is empty (open)."""
    if not TELEGRAM_ALLOWED_CHAT_IDS:
        return True
    return chat_id in TELEGRAM_ALLOWED_CHAT_IDS


async def _handle_update(
    update: dict,
    telegram: TelegramAPI,
    onyx: OnyxAPIClient,
) -> None:
    """Process a single Telegram update — extract the message, call Onyx, reply."""
    message = update.get("message")
    if not message:
        return

    chat_id: int = message["chat"]["id"]
    text: str | None = message.get("text")

    if not text:
        return

    if not _is_chat_allowed(chat_id):
        logger.warning("Ignoring message from unauthorized chat_id=%s", chat_id)
        return

    logger.debug("Processing message from chat_id=%s: %s", chat_id, text[:80])

    try:
        await telegram.send_chat_action(chat_id, "typing")

        response = await onyx.send_chat_message(text)
        reply = response.answer or response.answer_citationless or "(no response)"

        for chunk in _chunk_text(reply):
            await telegram.send_message(chat_id, chunk)

    except OnyxAPIConnectionError as exc:
        logger.error("Cannot reach Onyx API: %s", exc)
        await telegram.send_message(chat_id, "Sorry, I can't reach the AI backend right now. Please try again shortly.")
    except OnyxAPITimeoutError:
        logger.error("Onyx API timed out for chat_id=%s", chat_id)
        await telegram.send_message(chat_id, "The request took too long. Please try again.")
    except OnyxAPIResponseError as exc:
        logger.error("Onyx API error: %s", exc)
        await telegram.send_message(chat_id, "An error occurred while processing your message.")
    except TelegramAPIError as exc:
        logger.error("Telegram API error while replying to chat_id=%s: %s", chat_id, exc)


async def _run_bot(token: str, api_key: str) -> None:
    """Main async event loop: long-poll Telegram, route messages through Onyx."""
    telegram = TelegramAPI(token)
    onyx = OnyxAPIClient(api_key=api_key, persona_id=TELEGRAM_PERSONA_ID)

    await telegram.initialize()
    await onyx.initialize()
    logger.info("Telegram bot started (persona_id=%s)", TELEGRAM_PERSONA_ID)
    if TELEGRAM_ALLOWED_CHAT_IDS:
        logger.info("Allowed chat IDs: %s", TELEGRAM_ALLOWED_CHAT_IDS)
    else:
        logger.warning("TELEGRAM_ALLOWED_CHAT_IDS is not set — all chats can use the bot")

    offset = 0
    try:
        while True:
            try:
                updates = await telegram.get_updates(offset=offset)
            except TelegramAPIError as exc:
                logger.error("getUpdates failed: %s — retrying in %ss", exc, POLL_RETRY_SLEEP)
                await asyncio.sleep(POLL_RETRY_SLEEP)
                continue
            except Exception as exc:
                logger.exception("Unexpected error in getUpdates: %s", exc)
                await asyncio.sleep(POLL_RETRY_SLEEP)
                continue

            for update in updates:
                update_id: int = update["update_id"]
                offset = max(offset, update_id + 1)
                try:
                    await _handle_update(update, telegram, onyx)
                except Exception as exc:
                    logger.exception("Unhandled error processing update %s: %s", update_id, exc)
    finally:
        await telegram.close()
        await onyx.close()
        logger.info("Telegram bot stopped")


def main() -> None:
    """Entry point — run with: python -m onyx.onyxbot.telegram.client"""
    from onyx.db.engine.sql_engine import SqlEngine
    from onyx.utils.variable_functionality import set_is_ee_based_on_env_variable

    logger.info("Starting OpenNex Telegram Bot...")

    SqlEngine.init_engine(pool_size=5, max_overflow=2)
    set_is_ee_based_on_env_variable()

    counter = 0
    while True:
        token = TELEGRAM_BOT_TOKEN
        api_key = TELEGRAM_BOT_API_KEY

        if not token or not api_key:
            if counter % 36 == 0:  # log once every ~3 minutes (36 * 5s)
                missing = []
                if not token:
                    missing.append("TELEGRAM_BOT_TOKEN")
                if not api_key:
                    missing.append("TELEGRAM_BOT_API_KEY")
                logger.info("Telegram bot is dormant. Missing env vars: %s", ", ".join(missing))
            counter += 1
            time.sleep(5)
            continue

        counter = 0
        try:
            asyncio.run(_run_bot(token, api_key))
        except KeyboardInterrupt:
            logger.info("Telegram bot stopped by user")
            break
        except Exception:
            logger.exception("Fatal error in Telegram bot — restarting in %ss", POLL_RETRY_SLEEP)
            time.sleep(POLL_RETRY_SLEEP)


if __name__ == "__main__":
    main()
