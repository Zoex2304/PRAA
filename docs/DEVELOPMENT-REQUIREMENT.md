# PRAA — Personal Read Aloud Assistant
### Project Blueprint v1.0
> *Private Local Utility Tool for Audio-First Content Consumption*

---

## Table of Contents
1. [Problem Statement](#1-problem-statement)
2. [Solution Idea](#2-solution-idea)
3. [System Architecture](#3-system-architecture)
4. [Feature Requirements](#4-feature-requirements)
5. [Technology Stack](#5-technology-stack)
6. [Project Structure](#6-project-structure)
7. [Local Deployment Strategy](#7-local-deployment-strategy)
8. [Build Phase Roadmap](#8-build-phase-roadmap)
9. [Constraints & Assumptions](#9-constraints--assumptions)

---

## 1. Problem Statement

### Context
As a software engineer with an audio-first learning style, consuming written content across multiple platforms is inefficient and cognitively exhausting. Information is fragmented across various surfaces, and each platform has its own native reading behavior — none of which are unified or optimized for a personal listening workflow.

### Pain Points

| # | Problem | Impact |
|---|---------|--------|
| 1 | Content is scattered across Chrome, Edge, WhatsApp Web, PDFs, and READMEs | High context-switching cost |
| 2 | Native Read Aloud features are platform-locked (Edge only, WhatsApp only, etc.) | No unified experience |
| 3 | No global hotkey that works across all applications | Requires manual, per-app interaction |
| 4 | No control over voice, speed, or language preference | Poor personalization |
| 5 | No offline-capable, private, self-owned solution | Dependency on third-party UX |

### Core Question
> *How can a software engineer consume any text content from any application, instantly, using a single keyboard shortcut — without switching tools or breaking flow?*

---

## 2. Solution Idea

### Vision
A **lightweight, always-on system tray application** that runs silently in the Windows taskbar. It listens for a global hotkey, captures clipboard content, and reads it aloud using Microsoft Neural TTS voices — from any application, at any time.

### Core User Flow
```
User selects text anywhere
        │
        ▼
Ctrl + C  (copy)
        │
        ▼
Ctrl + Shift + R  (trigger PRAA hotkey)
        │
        ▼
PRAA processes text → cleans → detects language → synthesizes
        │
        ▼
🔊 Audio plays immediately
```

### Design Principles
- **Zero friction** — 2 keystrokes max to trigger
- **Zero dependency** — no browser extension, no cloud account required
- **Zero UI intrusion** — lives in the system tray, invisible during normal workflow
- **Privacy first** — all processing stays local; only TTS synthesis call leaves the machine

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────┐
│                   PRAA Application                   │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │              INPUT LAYER                    │    │
│  │  ┌──────────────┐  ┌─────────────────────┐  │    │
│  │  │ Global Hotkey│  │  Clipboard Listener │  │    │
│  │  │ (pynput)     │  │  (tkinter built-in) │  │    │
│  │  └──────┬───────┘  └──────────┬──────────┘  │    │
│  └─────────┼──────────────────────┼─────────────┘    │
│            └──────────┬───────────┘                  │
│                       ▼                              │
│  ┌─────────────────────────────────────────────┐    │
│  │            PROCESSING LAYER                 │    │
│  │  ┌────────────┐  ┌──────────┐  ┌─────────┐  │    │
│  │  │Text Cleaner│  │ Lang Det │  │Chunking │  │    │
│  │  │  (regex)   │  │ (lingua) │  │ Engine  │  │    │
│  │  └────────────┘  └──────────┘  └─────────┘  │    │
│  └─────────────────────────────────────────────┘    │
│                       ▼                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              TTS LAYER                      │    │
│  │         edge-tts  (async engine)            │    │
│  │    id-ID-ArdiNeural / id-ID-GadisNeural     │    │
│  │    en-US-BrianNeural (auto fallback)        │    │
│  └─────────────────────────────────────────────┘    │
│                       ▼                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              OUTPUT LAYER                   │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  │    │
│  │  │  Audio Playback  │  │  Queue Manager   │  │    │
│  │  │sounddevice+      │  │  (FIFO buffer)   │  │    │
│  │  │soundfile         │  │                  │  │    │
│  │  └──────────────────┘  └──────────────────┘  │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │           CONTROL LAYER                     │    │
│  │  System Tray (pystray) + Config (pydantic)  │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## 4. Feature Requirements

### 4.1 Core Features (Phase 1 — MVP)

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F01 | Global Hotkey Trigger | `Ctrl+Shift+R` to read clipboard content | MUST |
| F02 | Stop Hotkey | `Ctrl+Shift+S` to stop current playback | MUST |
| F03 | Clipboard Capture | Read text from system clipboard at trigger time | MUST |
| F04 | TTS Synthesis | Convert text to audio via edge-tts | MUST |
| F05 | Audio Playback | Stream and play synthesized audio | MUST |
| F06 | System Tray Icon | Persistent tray icon with right-click menu | MUST |

### 4.2 Quality-of-Life Features (Phase 2)

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F07 | Text Cleaner | Strip URLs, emojis, special characters before TTS | SHOULD |
| F08 | Language Auto-Detect | Switch voice automatically (ID → EN or vice versa) | SHOULD |
| F09 | Speed Control | Configurable rate: 0.75x / 1x / 1.25x / 1.5x | SHOULD |
| F10 | Voice Switcher | Toggle Male (Ardi) / Female (Gadis) from tray menu | SHOULD |
| F11 | Queue System | Buffer multiple clipboard reads if triggered rapidly | SHOULD |
| F12 | Pause/Resume | Hotkey or tray button to pause mid-reading | SHOULD |

### 4.3 Nice-to-Have Features (Phase 3)

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F13 | Reading History | Log of all text read, viewable from tray | COULD |
| F14 | Save to MP3 | Export last reading to audio file | COULD |
| F15 | Mini Floating Widget | Always-on-top mini window with playback controls | COULD |
| F16 | Chunk Progress Indicator | Show progress in tray tooltip during long reads | COULD |

---

## 5. Technology Stack

### Final Stack Selection

| Layer | Library | Version | Justification |
|-------|---------|---------|---------------|
| **TTS Engine** | `edge-tts` | latest | Microsoft Neural voices, Indonesian support, free |
| **System Tray** | `pystray` + `Pillow` | latest | Most mature tray library for Python on Windows |
| **Global Hotkey / Input** | `pynput` | latest | Actively maintained, cross-platform, no admin rights |
| **Clipboard Access** | `tkinter` (built-in) | stdlib | Zero install, reliable on Windows |
| **Audio Playback** | `sounddevice` + `soundfile` | latest | Lightweight, precise buffer control, no overhead |
| **Language Detection** | `lingua-language-detector` | latest | High accuracy, modern, offline capable |
| **Config Management** | `pydantic` | v2 | Type-safe settings, validation, JSON serializable |
| **Packaging** | `Nuitka` | latest | Smaller binary, faster startup vs PyInstaller |
| **Runtime** | `Python` | 3.11+ | Async support, performance improvements |

### Voice Roster

| Voice ID | Language | Gender | Use Case |
|----------|----------|--------|----------|
| `id-ID-ArdiNeural` | Indonesian | Male | Default voice |
| `id-ID-GadisNeural` | Indonesian | Female | Alternate voice |
| `en-US-BrianNeural` | English | Male | Auto-fallback for EN text |

### Installation Command
```powershell
pip install edge-tts pystray Pillow pynput sounddevice soundfile lingua-language-detector pydantic nuitka
```

---

## 6. Project Structure

```
praa/
│
├── src/
│   ├── main.py               ← Entry point, bootstraps app
│   ├── tray.py               ← System tray icon & menu
│   ├── hotkey.py             ← Global hotkey listener
│   ├── clipboard.py          ← Clipboard capture logic
│   ├── processor.py          ← Text cleaner + chunker + lang detect
│   ├── tts_engine.py         ← edge-tts async wrapper
│   ├── player.py             ← Audio playback + queue manager
│   └── config.py             ← Pydantic settings model
│
├── assets/
│   └── icon.png              ← Tray icon image
│
├── config.json               ← User-editable settings file
├── requirements.txt          ← All dependencies
├── build.ps1                 ← Nuitka build script
└── README.md                 ← Usage documentation
```

---

## 7. Local Deployment Strategy

### 7.1 Development Mode (Run from Source)

**Prerequisites:**
- Python 3.11+
- Virtual environment active
- All dependencies installed via `requirements.txt`

**Steps:**
1. Clone or create project directory at `D:\tts-edge\praa`
2. Activate virtual environment: `venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python src/main.py`
5. App appears silently in Windows system tray

### 7.2 Production Mode (Standalone .exe)

**Build with Nuitka:**
```powershell
python -m nuitka --standalone --onefile --windows-disable-console `
  --windows-icon-from-ico=assets/icon.ico `
  --output-filename=praa.exe `
  src/main.py
```

**Deploy:**
```
dist/
├── praa.exe       ← Double-click to run, no Python needed
└── config.json    ← Copy alongside .exe for user config
```

### 7.3 Auto-Start on Windows Boot (Optional)

Place a shortcut of `praa.exe` in:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```
PRAA will launch automatically on every Windows login.

---

## 8. Build Phase Roadmap

### Phase 1 — Core Engine (MVP)
> Goal: Text in clipboard → spoken out loud via hotkey

- [ ] Project scaffolding & virtual environment setup
- [ ] `config.py` — Pydantic settings model (voice, hotkey, speed)
- [ ] `clipboard.py` — Capture clipboard text via tkinter
- [ ] `tts_engine.py` — Async edge-tts synthesis to temp audio file
- [ ] `player.py` — Play audio using sounddevice + soundfile
- [ ] `hotkey.py` — Register `Ctrl+Shift+R` and `Ctrl+Shift+S` globally via pynput
- [ ] `main.py` — Wire all components together
- [ ] **Milestone:** Select text anywhere → hotkey → audio plays ✅

### Phase 2 — Tray & Playback Control
> Goal: App lives in system tray with full controls

- [ ] `tray.py` — System tray icon using pystray
- [ ] Tray right-click menu: Play, Pause, Stop, Exit
- [ ] Tray tooltip showing current status (idle / playing / paused)
- [ ] Pause/Resume functionality in player
- [ ] **Milestone:** App runs headless, controlled from tray ✅

### Phase 3 — Intelligence & Polish
> Goal: Smart text processing and user configuration

- [ ] `processor.py` — Text cleaner (strip URLs, emojis, markdown symbols)
- [ ] Language detection via `lingua` → auto voice switching
- [ ] Chunking engine for long texts (split by sentence boundary)
- [ ] Queue system for multiple rapid clipboard triggers
- [ ] Speed control configurable from tray menu
- [ ] Voice switcher (Ardi ↔ Gadis) from tray menu
- [ ] **Milestone:** Production-quality, smart reading experience ✅

### Phase 4 — Packaging & Distribution
> Goal: Single .exe for personal use, no Python required

- [ ] Nuitka build script (`build.ps1`)
- [ ] Bundle `config.json` alongside binary
- [ ] Test cold-start from `.exe` on clean environment
- [ ] Optional: Windows startup shortcut setup
- [ ] **Milestone:** `praa.exe` — double-click and done ✅

---

## 9. Constraints & Assumptions

### Technical Constraints
- Requires active internet connection for edge-tts synthesis (calls Microsoft Edge endpoint)
- edge-tts is an **unofficial** library — endpoint may change without notice
- Not suitable for offline-only environments without additional fallback TTS

### Assumptions
- Target OS: **Windows 10/11** only (system tray & hotkey behavior is OS-specific)
- User runs one instance at a time (no multi-instance handling required)
- Text content is clean Unicode (no special binary or OCR-extracted garbage)

### Out of Scope (v1.0)
- OCR (reading text from images or screenshots)
- Browser extension integration
- Mobile platform support
- Cloud sync of reading history
- Multi-language sentence mixing (per-sentence language switch)

---

*Blueprint prepared for: Personal Software Engineering Utility*
*Stack finalized: 2025 | Target Platform: Windows 10/11 | Runtime: Python 3.11+*
