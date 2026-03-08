from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import BridgeConfig


@dataclass
class MeshMessage:
    sender: str
    sender_id: str
    text: str


@dataclass
class SlackMessage:
    text: str


def mesh_to_slack(msg: MeshMessage, config: BridgeConfig) -> str:
    return f"{config.message_prefix} *{msg.sender}*: {msg.text}"


def slack_to_mesh(msg: SlackMessage, config: BridgeConfig) -> str:
    text = msg.text
    max_len = config.max_mesh_message_len
    encoded = text.encode("utf-8")
    if len(encoded) > max_len:
        # Truncate to fit, leaving room for "..."
        truncated = encoded[: max_len - 3].decode("utf-8", errors="ignore")
        text = truncated + "..."
    return text
