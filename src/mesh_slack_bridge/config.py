import os
from dataclasses import dataclass, fields
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class BridgeConfig:
    # Meshtastic
    serial_port: str | None = None
    mesh_channel: int = 0

    # Slack
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_channel_id: str = ""

    # Message formatting
    message_prefix: str = "[Mesh]"
    max_mesh_message_len: int = 220

    # Rate limiting (seconds between sends)
    slack_post_interval: float = 1.0
    mesh_send_interval: float = 2.0

    # Behavior
    ignore_own_messages: bool = True

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None


def load_config() -> BridgeConfig:
    load_dotenv()

    config_path = Path(os.environ.get("BRIDGE_CONFIG_PATH", "config.yaml"))
    yaml_data = {}
    if config_path.exists():
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f) or {}

    valid_keys = {f.name for f in fields(BridgeConfig)}
    filtered = {k: v for k, v in yaml_data.items() if k in valid_keys and v is not None}
    config = BridgeConfig(**filtered)

    # Secrets from environment (override any yaml values)
    config.slack_bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    config.slack_app_token = os.environ.get("SLACK_APP_TOKEN", "")

    # Validation
    if not config.slack_bot_token:
        raise ValueError("SLACK_BOT_TOKEN environment variable is required")
    if not config.slack_app_token:
        raise ValueError("SLACK_APP_TOKEN environment variable is required")
    if not config.slack_channel_id:
        raise ValueError("slack_channel_id must be set in config.yaml")

    return config
