from __future__ import annotations

import logging
from typing import Callable

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import BridgeConfig
from .formatting import SlackMessage
from .queue import RateLimitedQueue

logger = logging.getLogger(__name__)


class SlackClient:
    def __init__(self, config: BridgeConfig, on_message: Callable[[SlackMessage], None]):
        self.config = config
        self.on_message = on_message
        self._handler: SocketModeHandler | None = None

        self.app = App(token=config.slack_bot_token)
        self._register_handlers()

        self._post_queue = RateLimitedQueue(
            "slack-post", self._do_post, config.slack_post_interval
        )

    def _register_handlers(self):
        @self.app.event("message")
        def handle_message(event, client):
            # Only process messages from the configured channel
            if event.get("channel") != self.config.slack_channel_id:
                return

            # Ignore bot messages and subtypes (edits, joins, etc.)
            if event.get("bot_id") or event.get("subtype"):
                return

            text = event.get("text", "")
            if not text:
                return

            msg = SlackMessage(text=text)
            self.on_message(msg)

    def post_message(self, text: str):
        self._post_queue.put(text)

    def _do_post(self, text: str):
        self.app.client.chat_postMessage(
            channel=self.config.slack_channel_id,
            text=text,
        )

    def start(self):
        logger.info("Starting Slack Socket Mode connection...")
        self._post_queue.start()
        self._handler = SocketModeHandler(self.app, self.config.slack_app_token)
        self._handler.start()

    def stop(self):
        self._post_queue.stop()
        if self._handler:
            try:
                self._handler.close()
            except Exception:
                logger.exception("Error closing Slack handler")
