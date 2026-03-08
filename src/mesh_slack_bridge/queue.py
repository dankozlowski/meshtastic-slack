from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class RateLimitedQueue:
    """Drains a queue at a fixed interval, calling *handler* for each item."""

    def __init__(self, name: str, handler: Callable, interval: float):
        self.name = name
        self._handler = handler
        self._interval = interval
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"queue-{name}")

    def start(self):
        self._thread.start()

    def put(self, item):
        self._queue.put(item)

    def stop(self):
        self._stop.set()
        # Unblock the queue.get() call so the thread can exit
        self._queue.put(None)
        self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            if item is None and self._stop.is_set():
                break
            try:
                self._handler(item)
            except Exception:
                logger.exception("%s queue: failed to handle item", self.name)
            # Wait before processing the next item
            self._stop.wait(self._interval)
