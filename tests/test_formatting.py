from mesh_slack_bridge.config import BridgeConfig
from mesh_slack_bridge.formatting import (
    MeshMessage,
    SlackMessage,
    mesh_to_slack,
    slack_to_mesh,
)


def make_config(**overrides) -> BridgeConfig:
    defaults = dict(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        slack_channel_id="C123",
    )
    defaults.update(overrides)
    return BridgeConfig(**defaults)


def test_mesh_to_slack_basic():
    config = make_config()
    msg = MeshMessage(sender="NodeAlpha", sender_id="!abc123", text="Hello world")
    result = mesh_to_slack(msg, config)
    assert result == "[Mesh] *NodeAlpha*: Hello world"


def test_mesh_to_slack_custom_prefix():
    config = make_config(message_prefix="[Radio]")
    msg = MeshMessage(sender="Bob", sender_id="!xyz", text="Test")
    result = mesh_to_slack(msg, config)
    assert result == "[Radio] *Bob*: Test"


def test_slack_to_mesh_basic():
    config = make_config()
    msg = SlackMessage(user="Dan", text="Hey mesh!")
    result = slack_to_mesh(msg, config)
    assert result == "Dan: Hey mesh!"


def test_slack_to_mesh_truncation():
    config = make_config(max_mesh_message_len=20)
    msg = SlackMessage(user="Dan", text="This is a very long message that exceeds the limit")
    result = slack_to_mesh(msg, config)
    assert len(result.encode("utf-8")) <= 20
    assert result.endswith("...")


def test_slack_to_mesh_exact_fit():
    config = make_config(max_mesh_message_len=220)
    msg = SlackMessage(user="Dan", text="Short")
    result = slack_to_mesh(msg, config)
    assert result == "Dan: Short"
    assert len(result.encode("utf-8")) <= 220
