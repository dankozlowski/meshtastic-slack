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
