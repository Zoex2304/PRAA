from __future__ import annotations

import os
import threading

import flet as ft
import psutil

from src.domain.config.theme_config import ThemeConfig


class DebugMetricsComponent(ft.Container):
    def __init__(self, theme: ThemeConfig, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme

    def get_thread_details(self) -> ft.Control:
        colors = self._theme.colors
        rows = []
        for t in threading.enumerate():
            name = t.name
            description = _describe_thread(name)
            daemon_tag = " [daemon]" if t.daemon else ""
            rows.append(
                ft.Text(
                    f"• {name}{daemon_tag} — {description}",
                    size=self._theme.typography.font_size_xs,
                    color=colors.text_dim,
                )
            )
        return ft.Column(controls=rows, spacing=2)

    def get_memory_details(self) -> ft.Control:
        colors = self._theme.colors
        try:
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            rss_mb = mem.rss / (1024 * 1024)
            vms_mb = mem.vms / (1024 * 1024)
            lines = [
                f"RSS: {rss_mb:.1f} MB",
                f"VMS: {vms_mb:.1f} MB",
                f"PID: {os.getpid()}",
            ]
        except Exception:
            lines = ["Unavailable"]

        return ft.Column(
            controls=[
                ft.Text(
                    line,
                    size=self._theme.typography.font_size_xs,
                    color=colors.text_dim,
                )
                for line in lines
            ],
            spacing=2,
        )


def _describe_thread(name: str) -> str:
    lower = name.lower()
    if "mainthread" in lower:
        return "Application main loop"
    if "flet" in lower:
        return "Flet UI event loop"
    if "asyncio" in lower or "async" in lower:
        return "Async event loop (EventBus dispatch)"
    if "hotkey" in lower or "pynput" in lower:
        return "Global hotkey listener"
    if "tray" in lower or "pystray" in lower:
        return "System tray icon service"
    if "audio" in lower or "playback" in lower or "sounddevice" in lower:
        return "Audio playback thread"
    if "tts" in lower or "synthesis" in lower:
        return "TTS synthesis worker"
    if "thread" in lower and "pool" in lower:
        return "Thread pool worker"
    if "watchdog" in lower or "observer" in lower:
        return "File system watcher"
    if "lingua" in lower:
        return "Language detection worker"
    return f"Background worker ({name})"
