"""Bounded monotonic TTL/LRU cache with defensive copies for world queries."""
import copy
import math
import time
from collections import OrderedDict
from threading import RLock


class TTLCache:
    def __init__(self, ttl_s, *, max_entries=512, clock=time.monotonic):
        if isinstance(ttl_s, bool) or not isinstance(ttl_s, (int, float)) or not math.isfinite(ttl_s) or ttl_s <= 0:
            raise ValueError('TTL must be finite and positive')
        if type(max_entries) is not int or max_entries <= 0:
            raise ValueError('Cache capacity must be positive')
        self.ttl_s, self.max_entries, self.clock = ttl_s, max_entries, clock
        self._items = OrderedDict();self._lock = RLock()

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:return None
            if self.clock() >= item[0]:
                del self._items[key];return None
            self._items.move_to_end(key)
            return copy.deepcopy(item[1])

    def set(self, key, value):
        with self._lock:
            self._items[key] = (self.clock()+self.ttl_s, copy.deepcopy(value))
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:self._items.popitem(last=False)
