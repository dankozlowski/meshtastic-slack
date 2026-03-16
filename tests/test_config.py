import os
import pytest
from unittest.mock import patch

from mesh_slack_bridge.config import load_config


def test_load_config_missing_bot_token(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text('slack_channel_id: "C123"\n')

    env = {
        "BRIDGE_CONFIG_PATH": str(config_file),
        "SLACK_APP_TOKEN": "xapp-test",
    }
    # Remove SLACK_BOT_TOKEN if present
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="SLACK_BOT_TOKEN"):
            load_config()


def test_load_config_missing_app_token(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text('slack_channel_id: "C123"\n')

    env = {
        "BRIDGE_CONFIG_PATH": str(config_file),
        "SLACK_BOT_TOKEN": "xoxb-test",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="SLACK_APP_TOKEN"):
            load_config()


def test_load_config_missing_channel(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("mesh_channel: 0\n")

    env = {
        "BRIDGE_CONFIG_PATH": str(config_file),
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_APP_TOKEN": "xapp-test",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="slack_channel_id"):
            load_config()


def test_load_config_success(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        'slack_channel_id: "C999"\n'
        "mesh_channel: 2\n"
        'message_prefix: "[Radio]"\n'
    )

    env = {
        "BRIDGE_CONFIG_PATH": str(config_file),
        "SLACK_BOT_TOKEN": "xoxb-real",
        "SLACK_APP_TOKEN": "xapp-real",
    }
    with patch.dict(os.environ, env, clear=True):
        config = load_config()

    assert config.slack_channel_id == "C999"
    assert config.mesh_channel == 2
    assert config.message_prefix == "[Radio]"
    assert config.slack_bot_token == "xoxb-real"
    assert config.slack_app_token == "xapp-real"


def test_load_config_ble_reset_default(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text('slack_channel_id: "C123"\n')

    env = {
        "BRIDGE_CONFIG_PATH": str(config_file),
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_APP_TOKEN": "xapp-test",
    }
    with patch.dict(os.environ, env, clear=True):
        config = load_config()

    assert config.ble_reset_on_connect is False


def test_load_config_ble_reset_enabled(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        'slack_channel_id: "C123"\n'
        "ble_reset_on_connect: true\n"
    )

    env = {
        "BRIDGE_CONFIG_PATH": str(config_file),
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_APP_TOKEN": "xapp-test",
    }
    with patch.dict(os.environ, env, clear=True):
        config = load_config()

    assert config.ble_reset_on_connect is True
