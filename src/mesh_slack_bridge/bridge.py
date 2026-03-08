from __future__ import annotations

import logging
import threading

from .config import BridgeConfig
from .formatting import MeshMessage, SlackMessage, mesh_to_slack, slack_to_mesh
from .mesh_client import MeshClient
from .slack_client import SlackClient

logger = logging.getLogger(__name__)


class Bridge:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self._stop_event = threading.Event()
        self.mesh = MeshClient(config, on_message=self._on_mesh_message)
        self.slack = SlackClient(config, on_message=self._on_slack_message)

    def _on_mesh_message(self, msg: MeshMessage):
        logger.info("Mesh -> Slack | %s: %s", msg.sender, msg.text)
        formatted = mesh_to_slack(msg, self.config)
        try:
            self.slack.post_message(formatted)
        except Exception:
            logger.exception("Failed to post to Slack")

    def _on_slack_message(self, msg: SlackMessage):
        logger.info("Slack -> Mesh | %s: %s", msg.user, msg.text)
        formatted = slack_to_mesh(msg, self.config)
        try:
            self.mesh.send_text(formatted)
        except Exception:
            logger.exception("Failed to send to mesh")

    def run(self):
        # Connect to Meshtastic (retries internally)
        self.mesh.connect()

        # Start Slack in a daemon thread (SocketModeHandler.start() blocks)
        slack_thread = threading.Thread(target=self.slack.start, daemon=True)
        slack_thread.start()

        logger.info("Bridge is running")

        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        if self._stop_event.is_set():
            return
        logger.info("Shutting down bridge...")
        self._stop_event.set()
        self.mesh.close()
        self.slack.stop()
        logger.info("Bridge shut down")
