import threading
import time

from mesh_slack_bridge.queue import RateLimitedQueue


def test_queue_delivers_in_order():
    results = []
    q = RateLimitedQueue("test", results.append, interval=0)
    q.start()
    q.put("a")
    q.put("b")
    q.put("c")
    # Give worker time to drain
    time.sleep(0.1)
    q.stop()
    assert results == ["a", "b", "c"]


def test_queue_rate_limits():
    timestamps = []

    def record(_item):
        timestamps.append(time.monotonic())

    q = RateLimitedQueue("test", record, interval=0.1)
    q.start()
    q.put(1)
    q.put(2)
    q.put(3)
    time.sleep(0.5)
    q.stop()
    assert len(timestamps) == 3
    # Each gap should be >= interval
    for i in range(1, len(timestamps)):
        assert timestamps[i] - timestamps[i - 1] >= 0.09  # small tolerance


def test_queue_handler_exception_does_not_stop_processing():
    results = []

    def handler(item):
        if item == "bad":
            raise RuntimeError("boom")
        results.append(item)

    q = RateLimitedQueue("test", handler, interval=0)
    q.start()
    q.put("good")
    q.put("bad")
    q.put("also good")
    time.sleep(0.1)
    q.stop()
    assert results == ["good", "also good"]


def test_queue_stop_is_clean():
    q = RateLimitedQueue("test", lambda x: None, interval=0)
    q.start()
    q.stop()
    assert not q._thread.is_alive()
