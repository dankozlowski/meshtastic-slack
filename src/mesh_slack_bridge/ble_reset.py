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

    # Step 6: Pair with PIN and trust (skip if no address)
    if ble_address:
        _pair_with_pin(ble_address, ble_pin)

    logger.info("BLE adapter reset sequence complete")


def _pair_with_pin(ble_address: str, ble_pin: str) -> None:
    """Pair and trust a BLE device using pexpect to handle the interactive PIN prompt."""
    import pexpect

    logger.info("Pairing with %s (PIN: %s)", ble_address, ble_pin)
    try:
        child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=30)
        child.expect(r"#|$")

        # Register agent
        child.sendline("agent on")
        child.expect(r"Agent registered|Agent is already registered")

        child.sendline("default-agent")
        child.expect(r"Default agent request successful")

        # Pair
        child.sendline(f"pair {ble_address}")

        # Wait for PIN prompt or success
        index = child.expect([
            r"Enter passkey",       # PIN prompt
            r"Passkey",             # Passkey display/confirm
            r"Pairing successful",  # Already worked without PIN
            r"Failed to pair",      # Pairing failed
            r"not available",       # Device not found
            pexpect.TIMEOUT,
        ], timeout=20)

        if index == 0 or index == 1:
            child.sendline(ble_pin)
            child.expect([r"Pairing successful", r"Failed", pexpect.TIMEOUT], timeout=15)
            logger.info("PIN sent for pairing")
        elif index == 2:
            logger.info("Pairing successful (no PIN required)")
        elif index == 3:
            logger.warning("Pairing failed")
        elif index == 4:
            logger.warning("Device not available for pairing")
        else:
            logger.warning("Pairing timed out")

        # Trust
        child.sendline(f"trust {ble_address}")
        child.expect([r"trust succeeded", r"Failed", pexpect.TIMEOUT], timeout=10)

        child.sendline("exit")
        child.close()
        logger.info("Pair and trust complete")
    except pexpect.exceptions.ExceptionPexpect:
        logger.exception("Error during BLE pairing")


def _run_step(
    name: str,
    cmd: list[str],
    *,
    timeout: int,
    fatal: bool = False,
) -> subprocess.CompletedProcess | None:
    """Run a subprocess step, logging output and handling errors."""
    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout
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
