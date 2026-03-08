# Meshtastic-Slack Bridge

A Python daemon that bridges Meshtastic radio mesh network messages with a Slack channel. Designed to run headless on a Raspberry Pi.

Messages flow bidirectionally:
- **Mesh → Slack**: Radio messages appear in your Slack channel as `[Mesh] *NodeName*: message`
- **Slack → Mesh**: Slack messages are sent over the mesh as-is (the node's own identity is used)

## Prerequisites

- Python 3.10+
- A Meshtastic radio connected via USB
- A Slack workspace you can install apps to

## Slack App Setup

Create an app at https://api.slack.com/apps:

1. **Bot Token Scopes** (OAuth & Permissions):
   - `channels:history` — read messages in public channels
   - `channels:read` — list channels and get channel info
   - `chat:write` — post messages
2. **Event Subscriptions**:
   - Subscribe to `message.channels`

3. **Socket Mode**:
   - Enable Socket Mode
   - Generate an app-level token with the `connections:write` scope

4. Install the app to your workspace and invite the bot to your target channel.

## Installation

```bash
git clone <repo-url> && cd meshtastic-slack
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy the example env file and fill in your Slack tokens:

```bash
cp .env.example .env
```

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-level-token
```

Edit `config.yaml` with your Slack channel ID and preferences:

```yaml
serial_port: null          # null = auto-detect first Meshtastic device
mesh_channel: 0            # Meshtastic channel index (0 = primary)
slack_channel_id: "C07XXXXXX"
message_prefix: "[Mesh]"
max_mesh_message_len: 220
log_level: INFO
```

## Running

```bash
python -m mesh_slack_bridge
```

## Deploy on Raspberry Pi

1. Copy the project to `/opt/mesh-slack-bridge`
2. Create the venv and install dependencies as above
3. Ensure the `pi` user is in the `dialout` group for serial access:
   ```bash
   sudo usermod -aG dialout pi
   ```
4. Install the systemd service:
   ```bash
   sudo cp systemd/mesh-slack-bridge.service /etc/systemd/system/
   sudo systemctl enable --now mesh-slack-bridge
   ```
5. Check status:
   ```bash
   journalctl -u mesh-slack-bridge -f
   ```

## Project Structure

```
src/mesh_slack_bridge/
├── __main__.py       # Entry point with signal handling and logging
├── config.py         # Loads config.yaml + env vars, validates required fields
├── bridge.py         # Orchestrator wiring mesh and Slack clients together
├── mesh_client.py    # Meshtastic serial connection, pubsub, auto-reconnect
├── slack_client.py   # Slack Bolt Socket Mode app, message handling
└── formatting.py     # Message transformation and 228-byte mesh truncation
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
