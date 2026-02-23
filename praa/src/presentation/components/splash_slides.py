from __future__ import annotations

from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class Slide:
    icon: ft.IconData
    title: str
    body: str


SLIDES: list[Slide] = [
    Slide(
        icon=ft.Icons.CONTENT_PASTE,
        title="Instant Text Reading",
        body="Select any text, then press Ctrl+Shift+R to hear it read aloud.",
    ),
    Slide(
        icon=ft.Icons.DOCUMENT_SCANNER,
        title="Screen OCR Capture",
        body="Press Ctrl+Shift+O to capture and read text from anywhere on screen.",
    ),
    Slide(
        icon=ft.Icons.UPLOAD_FILE,
        title="Upload Documents",
        body="Upload .txt, .pdf, .docx files or images via the toolbar upload button.",
    ),
    Slide(
        icon=ft.Icons.SPEED,
        title="Playback Speed",
        body="Use [-] [+] controls while playing to change speed - re-synthesizes instantly.",
    ),
    Slide(
        icon=ft.Icons.HISTORY,
        title="Session History",
        body="Completed readings are saved. Open the History tab to replay any session.",
    ),
    Slide(
        icon=ft.Icons.TUNE,
        title="Voice & Language",
        body="The gear button lets you switch Indonesian/English voices and models in real time.",
    ),
]
