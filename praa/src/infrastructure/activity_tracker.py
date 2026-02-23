from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class ActivityEntry:
    component: str
    activity: str
    detail: str = ""

    @property
    def summary(self) -> str:
        return f"{self.activity}: {self.detail}" if self.detail else self.activity


class ActivityTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._activities: dict[str, ActivityEntry] = {}

    def report(self, component: str, activity: str, detail: str = "") -> None:
        thread_name = threading.current_thread().name
        entry = ActivityEntry(component, activity, detail)
        with self._lock:
            self._activities[component] = entry
            # Also index by caller's thread name so debug_page can look up by t.name
            if thread_name != component:
                self._activities[thread_name] = entry

    def clear(self, component: str) -> None:
        with self._lock:
            self._activities.pop(component, None)

    def get_all(self) -> dict[str, ActivityEntry]:
        with self._lock:
            return dict(self._activities)

    def get(self, component: str) -> ActivityEntry | None:
        with self._lock:
            return self._activities.get(component)
