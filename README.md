<div align="center">

# 🔊 PRAA
### Personal Read Aloud Assistant

**Read anything, from anywhere, with a single keystroke.**

*A lightweight Windows desktop app that converts any text — clipboard, screen, or file — into natural-sounding speech using Microsoft Neural TTS voices.*

---

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![TTS Engine](https://img.shields.io/badge/TTS-Microsoft%20Neural-00B0F0?style=for-the-badge&logo=microsoftedge&logoColor=white)](https://github.com/rany2/edge-tts)
[![UI](https://img.shields.io/badge/UI-Flet-7C3AED?style=for-the-badge&logo=flutter&logoColor=white)](https://flet.dev/)
[![License](https://img.shields.io/badge/License-Personal%20Use-gray?style=for-the-badge)](./LICENSE)

</div>

---

## What is PRAA?

PRAA is a personal productivity tool built for audio-first content consumption. It lives silently in your Windows system tray and listens for a global hotkey. The moment you press it, any text on your clipboard is instantly converted to natural-sounding speech — no browser extension, no cloud account, no friction.

> *"Copy text. Press a hotkey. Listen. That's it."*

---

## Features

| | Feature | Description |
|---|---|---|
| ⌨️ | **Global Hotkey** | Trigger reading from any app — no window switching |
| 🧠 | **Auto Language Detection** | Seamlessly switches between Indonesian and English voices |
| 🖱️ | **OCR Screen Capture** | Drag-select any text on screen, even if it's not copyable |
| 📄 | **File Upload** | Read aloud from PDF, DOCX, TXT, and image files |
| 🎛️ | **Speed Control** | Adjust reading rate from 0.75x to 2.0x on the fly |
| 🔁 | **Smart Queue** | Rapid-fire triggers are buffered and played in sequence |
| 🧹 | **Text Cleaner** | Strips URLs, emojis, and Markdown symbols before reading |
| 📜 | **Session History** | Searchable log of everything you've read |
| 💾 | **Export Audio** | Save any reading session as an audio file |
| 🖥️ | **Floating Widget** | Compact always-on-top overlay with playback controls |

---

## Quick Start

### Prerequisites

Before you begin, make sure you have:

- **Windows 10 or 11** (required)
- **Python 3.11 or newer** — [Download here](https://www.python.org/downloads/)
- **An internet connection** (required for TTS synthesis via Microsoft Edge endpoint)
- **Git** (optional, for cloning)

> **Check your Python version:**
> ```powershell
> python --version
> ```
> You should see `Python 3.11.x` or higher.

---

### Step 1 — Get the code

**Option A: Clone with Git**
```powershell
git clone https://github.com/YOUR_USERNAME/praa.git
cd praa
```

**Option B: Download ZIP**

Click the green **Code** button at the top of this page → **Download ZIP** → Extract it → Open the folder.

---

### Step 2 — Set up the environment

Navigate into the `praa/` subfolder, then create and activate a virtual environment:

```powershell
cd praa

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\Activate.ps1
```

> **Execution policy error?** Run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

### Step 3 — Install dependencies

```powershell
pip install -r requirements.txt
```

> This may take a few minutes on first install — PaddleOCR downloads model weights.

---

### Step 4 — Run the app

```powershell
python src/main.py
```

PRAA will launch and appear as a **teal speech bubble icon** in your Windows system tray (bottom-right corner of the taskbar).

---

## How to Use

### The Basics (Clipboard → Speech)

1. Select any text in any application
2. Press `Ctrl + C` to copy it
3. Press `Ctrl + Shift + R` to read it aloud
4. Press `Ctrl + Shift + S` to stop

```
Select text  →  Ctrl+C  →  Ctrl+Shift+R  →  🔊
```

---

### Hotkeys

| Hotkey | Action |
|:---|:---|
| `Ctrl + Shift + R` | Read clipboard aloud |
| `Ctrl + Shift + S` | Stop playback immediately |

---

### OCR Screen Capture

Read text that you **cannot copy** (images, locked PDFs, video subtitles, etc.):

1. Click the **OCR button** in the PRAA widget (or system tray)
2. Your screen dims — drag to select any region
3. PRAA extracts the text and reads it aloud automatically

---

### File Upload

Read entire documents aloud:

1. Click the **Upload button** in the widget
2. Select a file: `.pdf`, `.docx`, `.txt`, `.md`, or an image
3. PRAA extracts the text and starts reading

---

### System Tray Controls

Right-click the **teal speech bubble** in your taskbar:

- **Resume / Pause** — control playback
- **Stop** — stop and clear the queue
- **Speed** — change reading rate (0.75x → 2.0x)
- **Voice** — switch between Ardi (Male) and Gadis (Female)
- **Exit** — close the app completely

---

## Configuration

Edit `praa/config.json` with any text editor to set your defaults:

```json
{
  "hotkey_read": "<ctrl>+<shift>+r",
  "hotkey_stop": "<ctrl>+<shift>+s",
  "voice_id": "id-ID-ArdiNeural",
  "voice_en": "en-US-BrianNeural",
  "voice_gender": "male",
  "speed_rate": 1.0,
  "language_preference": "auto"
}
```

| Key | Options | Description |
|:---|:---|:---|
| `voice_gender` | `"male"` / `"female"` | Default voice |
| `speed_rate` | `0.75` – `2.0` | Reading speed multiplier |
| `language_preference` | `"auto"` / `"id"` / `"en"` | Language detection mode |
| `hotkey_read` | Any key combo | Global read hotkey |
| `hotkey_stop` | Any key combo | Global stop hotkey |

> Changes made via the tray menu are saved to `config.json` automatically.

---

## Available Voices

| Voice | Language | Gender |
|:---|:---|:---|
| `id-ID-ArdiNeural` | Indonesian | Male (default) |
| `id-ID-GadisNeural` | Indonesian | Female |
| `en-US-BrianNeural` | English (US) | Male (auto-fallback) |

PRAA automatically detects if the text is Indonesian or English and switches voices accordingly when `language_preference` is set to `"auto"`.

---

## Build a Standalone .exe

Want to run PRAA without Python? Build a single portable executable:

```powershell
# From the praa/ directory with venv active
.\build.ps1
```

Output: `dist/praa.exe` — double-click to run. No Python installation needed.

> **To auto-start on Windows boot:** Place a shortcut of `praa.exe` in:
> ```
> %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
> ```

---

## Troubleshooting

<details>
<summary><b>Antivirus / Windows Defender blocks praa.exe</b></summary>

This is a **false positive**. PRAA listens for global hotkeys — antivirus AI sometimes flags unsigned apps that do this as suspicious.

**Fix:**
1. Open **Windows Security** → **Virus & threat protection**
2. Click **Protection history**
3. Find the blocked item → **Actions** → **Allow on device**
4. Or add the project folder to **Exclusions**

You can verify safety by building from source yourself using `build.ps1`.

</details>

<details>
<summary><b>App starts but no audio plays</b></summary>

- Check your default audio output device in Windows Sound settings
- Make sure your internet connection is active (TTS requires a Microsoft Edge endpoint call)
- Try increasing the reading speed — very slow speeds can sometimes cause buffering issues

</details>

<details>
<summary><b>OCR captures the wrong text or crops incorrectly</b></summary>

- On high-DPI displays (125% / 150% scaling), drag the selection slightly larger than the text area
- Make sure the text has sufficient contrast against the background
- Very small fonts (under 12pt) may reduce accuracy

</details>

<details>
<summary><b>pip install fails for PaddleOCR</b></summary>

Use the pinned versions:
```powershell
pip install "paddlepaddle>=2.6,<3.0" "paddleocr>=2.7,<3.0"
```

PaddleOCR 3.x has an unresolved oneDNN bug on Windows — stick to 2.x.

</details>

---

## Architecture

<details>
<summary><b>Show project structure</b></summary>

```
praa/src/
├── main.py                  ← Entry point
├── application/             ← Bootstrap + Orchestrator (dependency wiring)
├── domain/                  ← Core business logic (isolated modules)
│   ├── config/              ← Pydantic settings
│   ├── hotkey/              ← Global hotkey listener (pynput)
│   ├── clipboard/           ← Clipboard capture
│   ├── processor/           ← Text cleaner + language detect + chunker
│   ├── tts/                 ← edge-tts synthesis engine
│   ├── audio/               ← sounddevice playback + queue
│   ├── ocr/                 ← PaddleOCR screen capture pipeline
│   ├── upload/              ← File text extraction (PDF, DOCX, images)
│   └── tray/                ← System tray icon (pystray)
├── infrastructure/          ← EventBus, logging, database
│   └── database/            ← SQLAlchemy 2.0 (sessions, app state)
└── presentation/            ← Flet UI layer
    ├── app.py               ← Root window + layout
    ├── pages/               ← Home, History, Debug, Logs, Manage
    └── components/          ← Reusable UI components
```

**Event flow:**
```
Hotkey → TextCaptured → TextProcessed → SynthesisComplete → PlaybackStarted → PlaybackStopped
```

</details>

---

## Tech Stack

| Layer | Library |
|:---|:---|
| TTS Engine | [edge-tts](https://github.com/rany2/edge-tts) |
| UI Framework | [Flet](https://flet.dev/) |
| OCR | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| Audio Playback | sounddevice + soundfile |
| Language Detection | lingua-language-detector |
| Database | SQLAlchemy 2.0 |
| Config | Pydantic v2 |
| Screen Capture | mss |

---

<div align="center">

Built for personal use · Windows 10/11 · Python 3.11+

</div>
