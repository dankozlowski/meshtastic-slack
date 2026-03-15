# Meshtastic-Slack Bridge

A Python daemon that bridges Meshtastic radio mesh network messages with a Slack channel. Designed to run headless on a Raspberry Pi.

Messages flow bidirectionally:
- **Mesh → Slack**: Radio messages appear in your Slack channel as `[Mesh] *NodeName*: message`
- **Slack → Mesh**: Slack messages are sent over the mesh as-is (the node's own identity is used)

## Prerequisites

- Python 3.10+
- A Meshtastic radio connected via USB or Bluetooth
- A Slack workspace you can install apps to

## Slack App Setup

Create an app at https://api.slack.com/apps:

1. **Bot Token Scopes** (OAuth & Permissions):
   - `channels:history` — read messages in public channels
   - `channels:read` — list channels and get channel info
   - `chat:write` — post messages
   - For **private channels**, also add: `groups:history` and `groups:read`
2. **Event Subscriptions**:
   - Subscribe to `message.channels` (public channels)
   - For **private channels**, also subscribe to `message.groups`

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

Copy the example env file and fill in your Slack tokens

```bash
cp .env.example .env
```

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-level-token
```

Edit `config.yaml` with your Slack channel ID and preferences:

```yaml
connection_type: serial    # "serial" (USB) or "ble" (Bluetooth)
serial_port: null          # For serial: null = auto-detect first device
ble_address: null          # For ble: MAC address or device name; null = auto-detect
mesh_channel: 0            # Meshtastic channel index (0 = primary)
slack_channel_id: "C07XXXXXX"
message_prefix: "[Mesh]"
max_mesh_message_len: 220
log_level: INFO
```

### Connecting via Bluetooth (BLE)

Set `connection_type: ble` in `config.yaml`. You can either let it auto-detect the first BLE Meshtastic device or specify a device directly:

```yaml
connection_type: ble
ble_address: "Meshtastic_a724"  # BLE device name, MAC address, or null to auto-detect
```

**Finding your device name:** If you have multiple Meshtastic nodes nearby, you'll need to specify which one to connect to. Use `bluetoothctl` to scan:

```bash
sudo bluetoothctl
# then inside bluetoothctl:
scan on
# wait 10-15 seconds, look for entries with "Meshtastic" or your node name
scan off
devices
exit
```

The device name (e.g. `Meshtastic_a724` or `Hig0_a724`) is usually your node's short name plus the last few hex digits of its MAC address. Use this name as `ble_address` in `config.yaml`.

> **Tip:** Using the device name in `ble_address` is more reliable than the MAC address with the `bleak` BLE library used under the hood.

## Running

```bash
pip install -e .
python -m mesh_slack_bridge
```

## Deploy on Raspberry Pi

1. Clone the repo and install:
   ```bash
   git clone <repo-url> ~/meshtastic-slack && cd ~/meshtastic-slack
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **For USB serial connections**, ensure your user is in the `dialout` group:
   ```bash
   sudo usermod -aG dialout $USER
   ```
   Log out and back in for the group change to take effect.

3. **For Bluetooth (BLE) connections**:

   a. Ensure Bluetooth is unblocked and powered on:
   ```bash
   # Check if Bluetooth is blocked
   rfkill list

   # If soft blocked, unblock it
   sudo rfkill unblock bluetooth

   # Ensure the bluetooth service is running
   sudo systemctl start bluetooth

   # Power on the adapter
   sudo bluetoothctl power on
   ```

   > **If `power on` fails** with `org.bluez.Error.Failed`: run `rfkill unblock bluetooth` first, then restart the bluetooth service with `sudo systemctl restart bluetooth`. On some Pi models you may also need `sudo hciconfig hci0 up`. Check `dmesg | grep -i bluetooth` for firmware loading errors.

   b. Add your user to the `bluetooth` group:
   ```bash
   sudo usermod -aG bluetooth $USER
   ```
   Log out and back in for the group change to take effect.

   c. **Pair the device** (required for radios with PIN pairing enabled):
   ```bash
   sudo bluetoothctl
   # then inside bluetoothctl:
   scan on
   # wait for your Meshtastic device to appear
   scan off
   pair <MAC_ADDRESS>
   # enter PIN when prompted (default: 123456)
   trust <MAC_ADDRESS>
   exit
   ```

   d. Set `connection_type: ble` in `config.yaml` (see [Connecting via Bluetooth](#connecting-via-bluetooth-ble) above for finding your device name).

   e. **Troubleshooting BLE connections:**

   **"Error writing BLE" / PIN pairing errors:** The Meshtastic radio likely requires PIN pairing. Follow step (c) above to pair and trust the device first. You can check or change the PIN in the Meshtastic app under Bluetooth settings on the radio (default: `123456`).

   **Device not found / discovery failures:** The bridge uses the `bleak` library for BLE, which runs its own scan independently from `bluetoothctl`. If `bleak` can't find your device:
   - Verify the device is advertising by running `meshtastic --ble-scan`
   - If `bluetoothctl` sees the device but `bleak` does not, try power-cycling the Meshtastic radio and running the bridge immediately
   - If the device was previously paired via `bluetoothctl` and you're getting connection errors, try removing the pairing so `bleak` can manage the connection itself:
     ```bash
     bluetoothctl remove <MAC_ADDRESS>
     ```

   **Connection fails intermittently:** A failed BLE connection can leave the adapter in a bad state. The bridge will automatically clean up stale connections between retries, but if problems persist, try restarting the bluetooth service: `sudo systemctl restart bluetooth`

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
├── mesh_client.py    # Meshtastic connection (serial/BLE), pubsub, auto-reconnect
├── slack_client.py   # Slack Bolt Socket Mode app, message handling
└── formatting.py     # Message transformation and 228-byte mesh truncation
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
