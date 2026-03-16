# BLE Reset on Connect — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional BLE adapter reset-and-pair sequence that runs once at startup before the first Meshtastic connection attempt.

**Architecture:** A new `ble_reset.py` module provides a `reset_and_pair()` function that shells out to `bluetoothctl` and `hciconfig`. The `Bridge.run()` method calls it once before `mesh.connect()`, gated by the `ble_reset_on_connect` config flag.

**Tech Stack:** Python 3.10+, subprocess, bluetoothctl, hciconfig

**Spec:** `docs/superpowers/specs/2026-03-15-ble-reset-on-connect-design.md`

**Test runner:** `.venv/bin/python -m pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/mesh_slack_bridge/ble_reset.py` | `reset_and_pair()` function — runs BLE adapter reset sequence via subprocess |
| Create | `tests/test_ble_reset.py` | Unit tests for `ble_reset.py` |
| Modify | `src/mesh_slack_bridge/config.py:27` | Add `ble_reset_on_connect: bool = False` field |
| Modify | `src/mesh_slack_bridge/bridge.py:47-49` | Call `reset_and_pair()` before `mesh.connect()` |
| Modify | `config.yaml:5` | Add `ble_reset_on_connect` example |

---

## Task 1: Add `ble_reset_on_connect` config field

**Files:**
- Modify: `src/mesh_slack_bridge/config.py:27`
- Modify: `config.yaml:5`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test for new config field**

Add to `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_load_config_ble_reset_default tests/test_config.py::test_load_config_ble_reset_enabled -v`
Expected: FAIL — `BridgeConfig` has no `ble_reset_on_connect` field

- [ ] **Step 3: Add the field to BridgeConfig**

In `src/mesh_slack_bridge/config.py`, after line 27 (`ignore_own_messages: bool = True`), add:

```python
    ble_reset_on_connect: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Update config.yaml**

In `config.yaml`, after the `ble_address` line (line 4), add:

```yaml
ble_reset_on_connect: false  # Reset BLE adapter and re-pair at startup (requires bluetoothctl, hciconfig)
```

- [ ] **Step 6: Commit**

```bash
git add src/mesh_slack_bridge/config.py tests/test_config.py config.yaml
git commit -m "feat: add ble_reset_on_connect config field"
```

---

## Task 2: Create `ble_reset.py` module

**Files:**
- Create: `src/mesh_slack_bridge/ble_reset.py`
- Create: `tests/test_ble_reset.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ble_reset.py`:

```python
import subprocess
from unittest.mock import call, patch

import pytest

from mesh_slack_bridge.ble_reset import reset_and_pair


def _ok(cmd, **kwargs):
    """Simulate a successful subprocess.run call."""
    return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")


def _fail(cmd, **kwargs):
    """Simulate a failed subprocess.run call."""
    return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="error")


class TestResetAndPairWithAddress:
    """When a BLE address is provided, all steps should run."""

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run", side_effect=_ok)
    def test_calls_commands_in_order(self, mock_run, mock_sleep):
        reset_and_pair("AA:BB:CC:DD:EE:FF")

        commands = [c.args[0] for c in mock_run.call_args_list]
        assert commands == [
            ["bluetoothctl", "remove", "AA:BB:CC:DD:EE:FF"],
            ["hciconfig", "hci0", "reset"],
            ["bluetoothctl", "power", "on"],
            ["bluetoothctl", "--timeout", "10", "scan", "on"],
            ["bluetoothctl", "pair", "AA:BB:CC:DD:EE:FF"],
            ["bluetoothctl", "trust", "AA:BB:CC:DD:EE:FF"],
        ]
        mock_sleep.assert_called_once_with(2)

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run", side_effect=_ok)
    def test_passes_subprocess_kwargs(self, mock_run, _mock_sleep):
        reset_and_pair("AA:BB:CC:DD:EE:FF")

        for c in mock_run.call_args_list:
            assert c.kwargs["check"] is False
            assert c.kwargs["capture_output"] is True
            assert c.kwargs["text"] is True
            assert "timeout" in c.kwargs


class TestResetAndPairAutoDetect:
    """When ble_address is None, address-dependent steps are skipped."""

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run", side_effect=_ok)
    def test_skips_address_steps(self, mock_run, _mock_sleep):
        reset_and_pair(None)

        commands = [c.args[0] for c in mock_run.call_args_list]
        assert commands == [
            ["hciconfig", "hci0", "reset"],
            ["bluetoothctl", "power", "on"],
            ["bluetoothctl", "--timeout", "10", "scan", "on"],
        ]


class TestResetAndPairErrorHandling:
    """Error handling: adapter reset is fatal, other failures are not."""

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run")
    def test_adapter_reset_failure_raises(self, mock_run, _mock_sleep):
        def side_effect(cmd, **kwargs):
            if cmd[0] == "hciconfig":
                return _fail(cmd)
            return _ok(cmd)

        mock_run.side_effect = side_effect

        with pytest.raises(RuntimeError, match="BLE adapter reset failed"):
            reset_and_pair("AA:BB:CC:DD:EE:FF")

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run")
    def test_remove_failure_continues(self, mock_run, _mock_sleep):
        def side_effect(cmd, **kwargs):
            if "remove" in cmd:
                return _fail(cmd)
            return _ok(cmd)

        mock_run.side_effect = side_effect

        # Should not raise
        reset_and_pair("AA:BB:CC:DD:EE:FF")

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run")
    def test_pair_failure_continues(self, mock_run, _mock_sleep):
        def side_effect(cmd, **kwargs):
            if "pair" in cmd:
                return _fail(cmd)
            return _ok(cmd)

        mock_run.side_effect = side_effect

        # Should not raise
        reset_and_pair("AA:BB:CC:DD:EE:FF")

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run")
    def test_timeout_expired_continues(self, mock_run, _mock_sleep):
        def side_effect(cmd, **kwargs):
            if "scan" in cmd:
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 10))
            return _ok(cmd)

        mock_run.side_effect = side_effect

        # Should not raise — scan timeout is non-fatal
        reset_and_pair("AA:BB:CC:DD:EE:FF")

    @patch("mesh_slack_bridge.ble_reset.time.sleep")
    @patch("mesh_slack_bridge.ble_reset.subprocess.run")
    def test_adapter_reset_timeout_raises(self, mock_run, _mock_sleep):
        def side_effect(cmd, **kwargs):
            if cmd[0] == "hciconfig":
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 10))
            return _ok(cmd)

        mock_run.side_effect = side_effect

        with pytest.raises(RuntimeError, match="BLE adapter reset failed"):
            reset_and_pair("AA:BB:CC:DD:EE:FF")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ble_reset.py -v`
Expected: FAIL — `mesh_slack_bridge.ble_reset` module does not exist

- [ ] **Step 3: Implement `ble_reset.py`**

Create `src/mesh_slack_bridge/ble_reset.py`:

```python
from __future__ import annotations

import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def reset_and_pair(ble_address: str | None) -> None:
    """Reset the BLE adapter and optionally re-pair with a device.

    Runs once at startup to work around flaky BLE on Raspberry Pi.
    Raises RuntimeError if the adapter reset itself fails.
    """
    logger.info("Starting BLE adapter reset sequence")

    # Step 1: Remove existing pairing (skip if no address)
    if ble_address:
        _run_step("remove pairing", ["bluetoothctl", "remove", ble_address], timeout=10)

    # Step 2: Reset adapter (fatal if this fails)
    result = _run_step(
        "adapter reset", ["hciconfig", "hci0", "reset"], timeout=10, fatal=True
    )
    if result is None:
        raise RuntimeError("BLE adapter reset failed")

    # Step 3: Wait for D-Bus to reinitialize
    time.sleep(2)

    # Step 4: Power on
    _run_step("power on", ["bluetoothctl", "power", "on"], timeout=10)

    # Step 5: Scan
    _run_step("scan", ["bluetoothctl", "--timeout", "10", "scan", "on"], timeout=15)

    # Step 6: Pair (skip if no address)
    if ble_address:
        _run_step("pair", ["bluetoothctl", "pair", ble_address], timeout=15)

    # Step 7: Trust (skip if no address)
    if ble_address:
        _run_step("trust", ["bluetoothctl", "trust", ble_address], timeout=10)

    logger.info("BLE adapter reset sequence complete")


def _run_step(
    name: str,
    cmd: list[str],
    *,
    timeout: int,
    fatal: bool = False,
) -> subprocess.CompletedProcess | None:
    """Run a subprocess step, logging output and handling errors."""
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
        logger.debug("BLE reset [%s] rc=%d stdout=%s stderr=%s", name, result.returncode, result.stdout.strip(), result.stderr.strip())

        if result.returncode != 0:
            if fatal:
                logger.error("BLE reset [%s] failed (rc=%d): %s", name, result.returncode, result.stderr.strip())
                return None
            logger.warning("BLE reset [%s] failed (rc=%d), continuing", name, result.returncode)

        return result
    except subprocess.TimeoutExpired:
        if fatal:
            logger.error("BLE reset [%s] timed out after %ds", name, timeout)
            return None
        logger.warning("BLE reset [%s] timed out after %ds, continuing", name, timeout)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ble_reset.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mesh_slack_bridge/ble_reset.py tests/test_ble_reset.py
git commit -m "feat: add ble_reset module for BLE adapter reset at startup"
```

---

## Task 3: Integrate into Bridge.run()

**Files:**
- Modify: `src/mesh_slack_bridge/bridge.py:47-49`

- [ ] **Step 1: Write failing test**

Add to `tests/test_ble_reset.py`:

```python
from unittest.mock import MagicMock, patch as std_patch
from mesh_slack_bridge.config import BridgeConfig


class TestBridgeIntegration:
    """Verify Bridge.run() calls reset_and_pair only when configured."""

    def _make_config(self, **overrides):
        defaults = dict(
            slack_bot_token="xoxb-test",
            slack_app_token="xapp-test",
            slack_channel_id="C123",
        )
        defaults.update(overrides)
        return BridgeConfig(**defaults)

    @std_patch("mesh_slack_bridge.bridge.reset_and_pair")
    def test_reset_called_when_ble_and_enabled(self, mock_reset):
        from mesh_slack_bridge.bridge import Bridge

        config = self._make_config(
            connection_type="ble",
            ble_address="AA:BB:CC:DD:EE:FF",
            ble_reset_on_connect=True,
        )
        bridge = Bridge(config)
        bridge.mesh = MagicMock()
        bridge.slack = MagicMock()
        bridge._stop_event = MagicMock()
        bridge._stop_event.wait.side_effect = KeyboardInterrupt

        try:
            bridge.run()
        except KeyboardInterrupt:
            pass

        mock_reset.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    @std_patch("mesh_slack_bridge.bridge.reset_and_pair")
    def test_reset_not_called_when_disabled(self, mock_reset):
        from mesh_slack_bridge.bridge import Bridge

        config = self._make_config(
            connection_type="ble",
            ble_reset_on_connect=False,
        )
        bridge = Bridge(config)
        bridge.mesh = MagicMock()
        bridge.slack = MagicMock()
        bridge._stop_event = MagicMock()
        bridge._stop_event.wait.side_effect = KeyboardInterrupt

        try:
            bridge.run()
        except KeyboardInterrupt:
            pass

        mock_reset.assert_not_called()

    @std_patch("mesh_slack_bridge.bridge.reset_and_pair")
    def test_reset_not_called_when_serial(self, mock_reset):
        from mesh_slack_bridge.bridge import Bridge

        config = self._make_config(
            connection_type="serial",
            ble_reset_on_connect=True,
        )
        bridge = Bridge(config)
        bridge.mesh = MagicMock()
        bridge.slack = MagicMock()
        bridge._stop_event = MagicMock()
        bridge._stop_event.wait.side_effect = KeyboardInterrupt

        try:
            bridge.run()
        except KeyboardInterrupt:
            pass

        mock_reset.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ble_reset.py::TestBridgeIntegration -v`
Expected: FAIL — `bridge` module does not import `reset_and_pair`

- [ ] **Step 3: Add integration to Bridge.run()**

In `src/mesh_slack_bridge/bridge.py`:

Add import at line 7 (after the other relative imports):
```python
from .ble_reset import reset_and_pair
```

Replace `bridge.py` lines 47-49:
```python
    def run(self):
        # Connect to Meshtastic (retries internally)
        self.mesh.connect()
```

With:
```python
    def run(self):
        # Optionally reset BLE adapter before first connection
        if self.config.ble_reset_on_connect and self.config.connection_type == "ble":
            reset_and_pair(self.config.ble_address)

        # Connect to Meshtastic (retries internally)
        self.mesh.connect()
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All 21 tests PASS (4 config + 5 formatting + 2 new config + 7 ble_reset + 3 bridge integration)

- [ ] **Step 5: Commit**

```bash
git add src/mesh_slack_bridge/bridge.py tests/test_ble_reset.py
git commit -m "feat: integrate BLE reset into bridge startup"
```

---

## Task 4: Final verification

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All 21 tests PASS

- [ ] **Step 2: Verify config.yaml is valid**

Run: `.venv/bin/python -c "import yaml; print(yaml.safe_load(open('config.yaml')))"`
Expected: Dict with `ble_reset_on_connect: false` included

- [ ] **Step 3: Commit any remaining changes and verify clean state**

Run: `git status`
Expected: Clean working tree
