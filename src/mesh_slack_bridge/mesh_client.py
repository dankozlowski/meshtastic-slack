from __future__ import annotations

import logging
import time
import threading
from typing import Callable

from pubsub import pub

from .config import BridgeConfig
from .formatting import MeshMessage

logger = logging.getLogger(__name__)

MAX_BACKOFF = 60


class MeshClient:
    def __init__(self, config: BridgeConfig, on_message: Callable[[MeshMessage], None]):
        self.config = config
        self.on_message = on_message
        self.interface = None
        self._my_node_id: str | None = None
        self._closing = False

    def _create_interface(self):
        if self.config.connection_type == "ble":
            from meshtastic.ble_interface import BLEInterface

            address = self.config.ble_address
            logger.info(
                "Connecting to Meshtastic device via BLE (address=%s)...",
                address or "auto-detect",
            )
            return BLEInterface(address=address)
        else:
            from meshtastic.serial_interface import SerialInterface

            logger.info(
                "Connecting to Meshtastic device via serial (port=%s)...",
                self.config.serial_port or "auto-detect",
            )
            return SerialInterface(devPath=self.config.serial_port)

    def connect(self):
        backoff = 1
        while not self._closing:
            iface = None
            try:
                iface = self._create_interface()
                self.interface = iface
                self._my_node_id = str(self.interface.myInfo.my_node_num)
                logger.info("Connected to Meshtastic device (node %s)", self._my_node_id)
                backoff = 1  # reset on success

                # Subscribe to events
                pub.subscribe(self._on_receive, "meshtastic.receive.text")
                pub.subscribe(self._on_connection_lost, "meshtastic.connection.lost")
                return
            except Exception:
                logger.exception("Failed to connect to Meshtastic device, retrying in %ds", backoff)
                # Clean up any partially-constructed interface so the
                # adapter is released before the next attempt.
                self.interface = None
                if iface:
                    try:
                        iface.close()
                    except Exception:
                        logger.debug("Error closing interface during cleanup", exc_info=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

    def _on_receive(self, packet, interface):
        try:
            from_id = packet.get("fromId", "unknown")

            # Ignore own messages
            if self.config.ignore_own_messages:
                from_num = str(packet.get("from", ""))
                if from_num == self._my_node_id:
                    return

            # Look up friendly name
            sender_name = from_id
            if self.interface and self.interface.nodes:
                node = self.interface.nodes.get(from_id, {})
                user_info = node.get("user", {})
                sender_name = user_info.get("longName") or user_info.get("shortName") or from_id

            text = packet.get("decoded", {}).get("text", "")
            if not text:
                return

            msg = MeshMessage(sender=sender_name, sender_id=from_id, text=text)
            self.on_message(msg)
        except Exception:
            logger.exception("Error processing mesh message")

    def _on_connection_lost(self, interface):
        if self._closing:
            return
        logger.warning("Meshtastic connection lost, attempting reconnect...")
        self._cleanup_subscriptions()
        # Reconnect in a separate thread to avoid blocking pubsub
        threading.Thread(target=self.connect, daemon=True).start()

    def send_text(self, text: str):
        if not self.interface:
            logger.error("Cannot send: not connected to Meshtastic device")
            return
        self.interface.sendText(text, channelIndex=self.config.mesh_channel)

    def _cleanup_subscriptions(self):
        for topic, listener in [
            ("meshtastic.receive.text", self._on_receive),
            ("meshtastic.connection.lost", self._on_connection_lost),
        ]:
            try:
                pub.unsubscribe(listener, topic)
            except Exception:
                logger.debug("Already unsubscribed from %s", topic)

    def close(self):
        self._closing = True
        self._cleanup_subscriptions()
        if self.interface:
            try:
                self.interface.close()
            except Exception:
                logger.exception("Error closing Meshtastic interface")
            self.interface = None
