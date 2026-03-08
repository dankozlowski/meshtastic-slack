from __future__ import annotations

import logging
from typing import Callable

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import BridgeConfig
from .formatting import SlackMessage

logger = logging.getLogger(__name__)


class SlackClient:
    def __init__(self, config: BridgeConfig, on_message: Callable[[SlackMessage], None]):
        self.config = config
        self.on_message = on_message
        self._user_cache: dict[str, str] = {}
        self._handler: SocketModeHandler | None = None

        self.app = App(token=config.slack_bot_token)
        self._register_handlers()

    def _register_handlers(self):
        @self.app.event("message")
        def handle_message(event, client):
            # Only process messages from the configured channel
            if event.get("channel") != self.config.slack_channel_id:
                return

            # Ignore bot messages and subtypes (edits, joins, etc.)
            if event.get("bot_id") or event.get("subtype"):
                return

            user_id = event.get("user", "")
            if not user_id:
                return

            display_name = self._get_user_name(client, user_id)
            text = event.get("text", "")
            if not text:
                return

            msg = SlackMessage(user=display_name, text=text)
            self.on_message(msg)

    def _get_user_name(self, client, user_id: str) -> str:
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            result = client.users_info(user=user_id)
            profile = result["user"]["profile"]
            name = profile.get("display_name") or result["user"].get("real_name") or user_id
            self._user_cache[user_id] = name
            return name
        except Exception:
            logger.exception("Failed to look up Slack user %s", user_id)
            return user_id

    def post_message(self, text: str):
        self.app.client.chat_postMessage(
            channel=self.config.slack_channel_id,
            text=text,
        )

    def start(self):
        logger.info("Starting Slack Socket Mode connection...")
        self._handler = SocketModeHandler(self.app, self.config.slack_app_token)
        self._handler.start()

    def stop(self):
        if self._handler:
            try:
                self._handler.close()
            except Exception:
                logger.exception("Error closing Slack handler")
