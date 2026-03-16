from __future__ import annotations

import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def reset_and_pair(ble_address: str | None, ble_pin: str = "123456") -> None:
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

    # Step 5: BLE scan (le transport for Meshtastic devices)
    _run_step("scan", ["bluetoothctl", "--timeout", "10", "scan", "le"], timeout=15)

    # Step 6: Pair with PIN (skip if no address)
    # bluetoothctl pair prompts for a PIN interactively, so we script
    # the full session: set the agent, pair, supply the PIN, then trust.
    if ble_address:
        script = (
            f"agent on\n"
            f"default-agent\n"
            f"pair {ble_address}\n"
            f"{ble_pin}\n"
            f"trust {ble_address}\n"
            f"exit\n"
        )
        _run_step(
            "pair and trust",
            ["bluetoothctl"],
            timeout=30,
            stdin_text=script,
        )

    logger.info("BLE adapter reset sequence complete")


def _run_step(
    name: str,
    cmd: list[str],
    *,
    timeout: int,
    fatal: bool = False,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess | None:
    """Run a subprocess step, logging output and handling errors."""
    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout,
            input=stdin_text,
        )
        logger.debug(
            "BLE reset [%s] rc=%d stdout=%s stderr=%s",
            name,
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip(),
        )

        if result.returncode != 0:
            if fatal:
                logger.error(
                    "BLE reset [%s] failed (rc=%d): %s",
                    name,
                    result.returncode,
                    result.stderr.strip(),
                )
                return None
            logger.warning(
                "BLE reset [%s] failed (rc=%d), continuing", name, result.returncode
            )

        return result
    except subprocess.TimeoutExpired:
        if fatal:
            logger.error("BLE reset [%s] timed out after %ds", name, timeout)
            return None
        logger.warning("BLE reset [%s] timed out after %ds, continuing", name, timeout)
        return None
