"""In-memory per-sender rate limiter.

Keyed by the sender's phone number. The bot effectively serves one person,
so a simple in-process limiter is enough; it exists so a leaked number can't
rack up unlimited API/SMS usage. It counts per worker process, so keep the
app at a single web worker (see Procfile) for a hard global cap.
"""
import threading
import time
from collections import defaultdict

import config


class RateLimiter:
    def __init__(self, per_min, per_day):
        self.per_min = per_min
        self.per_day = per_day
        self._hits = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, sender):
        """Record a hit and return True if it is within limits, else False."""
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits[sender] if now - t < 86400]
            in_last_min = sum(1 for t in hits if now - t < 60)
            if in_last_min >= self.per_min or len(hits) >= self.per_day:
                self._hits[sender] = hits
                return False
            hits.append(now)
            self._hits[sender] = hits
            return True


limiter = RateLimiter(config.RATE_LIMIT_PER_MIN, config.RATE_LIMIT_PER_DAY)
