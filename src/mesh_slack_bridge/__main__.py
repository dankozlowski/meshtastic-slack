import logging
import signal
import sys

from .config import load_config
from .bridge import Bridge


def setup_logging(level: str, log_file: str | None):
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger("mesh_slack_bridge")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        root.addHandler(fh)


def main():
    config = load_config()
    setup_logging(config.log_level, config.log_file)

    bridge = Bridge(config)

    def handle_signal(sig, frame):
        bridge.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logger = logging.getLogger("mesh_slack_bridge")
    logger.info("Starting Meshtastic-Slack Bridge")
    bridge.run()


if __name__ == "__main__":
    main()
