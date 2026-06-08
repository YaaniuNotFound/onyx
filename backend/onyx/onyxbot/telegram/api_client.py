"""Async HTTP client for communicating with the Onyx API server."""

import aiohttp

from onyx.chat.models import ChatFullResponse
from onyx.onyxbot.telegram.constants import API_REQUEST_TIMEOUT
from onyx.onyxbot.telegram.exceptions import OnyxAPIConnectionError
from onyx.onyxbot.telegram.exceptions import OnyxAPIResponseError
from onyx.onyxbot.telegram.exceptions import OnyxAPITimeoutError
from onyx.server.query_and_chat.models import ChatSessionCreationRequest
from onyx.server.query_and_chat.models import MessageOrigin
from onyx.server.query_and_chat.models import SendMessageRequest
from onyx.utils.logger import setup_logger
from onyx.utils.variable_functionality import build_api_server_url_for_http_requests

logger = setup_logger()


class OnyxAPIClient:
    """Async HTTP client for sending chat requests to the Onyx API server.

    Simplified single-user variant of the Discord bot's OnyxAPIClient —
    no multi-tenant routing, just a fixed personal API key and persona ID.
    """

    def __init__(self, api_key: str, persona_id: int = 0, timeout: int = API_REQUEST_TIMEOUT) -> None:
        self._api_key = api_key
        self._persona_id = persona_id
        self._base_url = build_api_server_url_for_http_requests(
            respect_env_override_if_set=True
        ).rstrip("/")
        self._timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    async def initialize(self) -> None:
        if self._session is not None:
            return
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._timeout, connect=30)
        )
        logger.info("Onyx API client initialized (base_url=%s)", self._base_url)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def send_chat_message(self, message: str) -> ChatFullResponse:
        """Send a chat message to the Onyx API and return the complete response."""
        if self._session is None:
            raise OnyxAPIConnectionError("API client not initialized — call initialize() first")

        url = f"{self._base_url}/chat/send-chat-message"
        request = SendMessageRequest(
            message=message,
            stream=False,
            origin=MessageOrigin.TELEGRAMBOT,
            chat_session_info=ChatSessionCreationRequest(persona_id=self._persona_id),
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            async with self._session.post(
                url, json=request.model_dump(mode="json"), headers=headers
            ) as resp:
                if resp.status == 401:
                    raise OnyxAPIResponseError("Authentication failed — check TELEGRAM_BOT_API_KEY", status_code=401)
                if resp.status == 403:
                    raise OnyxAPIResponseError("Access denied — insufficient permissions", status_code=403)
                if resp.status >= 400:
                    error_text = await resp.text()
                    raise OnyxAPIResponseError(f"API error {resp.status}: {error_text}", status_code=resp.status)

                data = await resp.json()
                response = ChatFullResponse.model_validate(data)
                if response.error_msg:
                    logger.warning("Onyx API returned error: %s", response.error_msg)
                return response

        except aiohttp.ClientConnectorError as exc:
            raise OnyxAPIConnectionError(f"Cannot connect to Onyx API at {self._base_url}: {exc}") from exc
        except TimeoutError as exc:
            raise OnyxAPITimeoutError(f"Request timed out after {self._timeout}s") from exc
        except aiohttp.ClientError as exc:
            raise OnyxAPIConnectionError(f"HTTP client error: {exc}") from exc
