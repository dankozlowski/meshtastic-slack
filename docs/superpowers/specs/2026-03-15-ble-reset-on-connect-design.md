# BLE Reset on Connect

## Problem

BLE connections to Meshtastic devices on Raspberry Pi are unreliable at startup. The adapter often needs a manual reset cycle (remove pairing, reset adapter, re-scan, re-pair) before a stable connection can be established.

## Solution

Add an optional startup BLE reset sequence, controlled by a config flag, that runs once before the first connection attempt.

## Prerequisites

- **OS**: Raspberry Pi OS with BlueZ installed (`bluetoothctl`, `hciconfig`)
- **Permissions**: The process must run as root or with `CAP_NET_ADMIN` (for `hciconfig reset`) and membership in the `bluetooth` group (for `bluetoothctl`). The existing systemd service runs as `pi` in the `dialout` group — the `bluetooth` group must also be added.
- **Adapter**: Assumes `hci0`. Multi-adapter support is out of scope.
- **Note**: `hciconfig` is deprecated on newer BlueZ (5.50+). If this becomes an issue on newer RPi OS versions, a `btmgmt` fallback can be added later.

## Config

New field in `BridgeConfig`:

```python
ble_reset_on_connect: bool = False
```

Only takes effect when `connection_type` is `"ble"`. Ignored for serial connections.

## New Module: `ble_reset.py`

Single public function:

```python
def reset_and_pair(ble_address: str | None) -> None
```

Runs these steps in order via `subprocess.run(check=False, capture_output=True, text=True, timeout=...)`:

1. **Remove existing pairing** — `bluetoothctl remove <address>` (skip if address is `None`) — timeout 10s
2. **Reset adapter** — `hciconfig hci0 reset` — timeout 10s
3. **Sleep 2s** — allow D-Bus to reinitialize after adapter reset
4. **Power on** — `bluetoothctl power on` — timeout 10s
5. **Scan** — `bluetoothctl --timeout 10 scan on` — timeout 15s
6. **Pair** — `bluetoothctl pair <address>` (skip if address is `None`) — timeout 15s
7. **Trust** — `bluetoothctl trust <address>` (skip if address is `None`) — timeout 10s

### Auto-detect mode limitation

When `ble_address` is `None` (auto-detect), steps 1, 6, and 7 are skipped. Only the adapter reset, power on, and scan are performed. Pairing is left to the Meshtastic library's auto-detect logic.

### Error handling

- All `subprocess.run()` calls use `check=False`, `capture_output=True`, `text=True`.
- Each step logs its stdout/stderr at DEBUG and any failures at WARNING.
- `subprocess.TimeoutExpired` is caught per-step and logged as WARNING.
- Non-critical step failures (e.g., remove fails because no existing pairing) are logged and skipped.
- Adapter reset failure (step 2) raises `RuntimeError` — nothing else works without it.

## Integration

In `bridge.py`, inside `run()`, before `self.mesh.connect()`:

```python
def run(self):
    if self.config.ble_reset_on_connect and self.config.connection_type == "ble":
        reset_and_pair(self.config.ble_address)
    self.mesh.connect()
    # ...
```

This runs exactly once at startup. The `connect()` method is also called by `_on_connection_lost` for reconnects — by placing the reset in `bridge.py` instead of `mesh_client.py`, we guarantee it only runs once.

If `reset_and_pair` raises `RuntimeError`, it propagates up and the app exits with a clear error.

## Testing

Unit tests mock `subprocess.run` to verify:

- Correct commands called in order with exact argument lists
- Address-dependent steps skipped when `ble_address` is `None`
- Non-critical failures don't raise
- Adapter reset failure raises `RuntimeError`
- `subprocess.TimeoutExpired` is handled gracefully
- Integration guard: not called when `ble_reset_on_connect` is `False`
- Integration guard: not called when `connection_type` is `"serial"`

Manual integration test on RPi with a real Meshtastic device should be performed before release.

## Files Changed

- `src/mesh_slack_bridge/config.py` — add `ble_reset_on_connect` field
- `src/mesh_slack_bridge/ble_reset.py` — new module
- `src/mesh_slack_bridge/bridge.py` — call `reset_and_pair` before `mesh.connect()`
- `config.yaml` — add `ble_reset_on_connect` example
- `tests/test_ble_reset.py` — new tests
