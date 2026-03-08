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


def slack_to_mesh(msg: SlackMessage, config: BridgeConfig) -> str | None:
    """Return the message text, or None if it exceeds the mesh byte limit."""
    text = msg.text
    if len(text.encode("utf-8")) > config.max_mesh_message_len:
        return None
    return text
