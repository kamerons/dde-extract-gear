"""Tests for task.redis_updates (Redis key contract)."""

import json
import unittest

from task.redis_updates import update_task_progress, update_task_status


class MockRedis:
    """Minimal Redis mock to verify key layout and expiry."""

    def __init__(self):
        self.calls = []

    def hset(self, name, mapping=None, **kwargs):
        if mapping is None:
            mapping = kwargs
        self.calls.append(("hset", name, dict(mapping)))

    def setex(self, name, time, value):
        self.calls.append(("setex", name, time, value))


class TestRedisUpdates(unittest.TestCase):
    def test_update_task_status_completed(self):
        r = MockRedis()
        update_task_status(r, "tid-1", "completed", results={"epochs": 5})
        self.assertEqual(len(r.calls), 2)
        self.assertEqual(r.calls[0][0], "hset")
        self.assertEqual(r.calls[0][1], "task:tid-1:meta")
        self.assertEqual(r.calls[0][2], {"status": "completed"})
        self.assertEqual(r.calls[1][0], "setex")
        self.assertEqual(r.calls[1][1], "task:tid-1:result")
        self.assertEqual(r.calls[1][2], 3600)
        self.assertEqual(json.loads(r.calls[1][3]), {"epochs": 5})

    def test_update_task_status_failed(self):
        r = MockRedis()
        update_task_status(r, "tid-2", "failed", error="Something broke")
        self.assertEqual(len(r.calls), 2)
        self.assertEqual(r.calls[0][1], "task:tid-2:meta")
        self.assertEqual(r.calls[0][2], {"status": "failed"})
        self.assertEqual(r.calls[1][1], "task:tid-2:error")
        self.assertEqual(r.calls[1][3], "Something broke")

    def test_update_task_progress(self):
        r = MockRedis()
        update_task_progress(r, "tid-3", evaluated=10, total_planned=100, partial_results={"loss": 0.5})
        self.assertEqual(len(r.calls), 2)
        self.assertEqual(r.calls[0][0], "hset")
        self.assertEqual(r.calls[0][1], "task:tid-3:meta")
        self.assertEqual(r.calls[0][2], {"evaluated": "10", "total_planned": "100"})
        self.assertEqual(r.calls[1][0], "setex")
        self.assertEqual(r.calls[1][1], "task:tid-3:result")
        self.assertEqual(json.loads(r.calls[1][3]), {"loss": 0.5})


if __name__ == "__main__":
    unittest.main()
