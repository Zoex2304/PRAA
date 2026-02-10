# PRAA — Personal Read Aloud Assistant

> A lightweight, always-on system tray application that reads any text aloud using Microsoft Neural TTS voices.

## Quick Start

### Prerequisites
- Python 3.11+
- Windows 10/11
- Active internet connection (for edge-tts)

### Setup

```powershell
# Navigate to project directory
cd D:\tts-edge\praa

# Create virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Run

```powershell
python src/main.py
```

PRAA will appear silently in the Windows system tray.

### Usage

| Action | Shortcut |
|--------|----------|
| **Read clipboard aloud** | `Ctrl + Shift + R` |
| **Stop playback** | `Ctrl + Shift + S` |

1. Select any text in any application
2. Copy it (`Ctrl + C`)
3. Press `Ctrl + Shift + R`
4. Audio plays immediately

### Configuration

Edit `config.json` to customize:

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

### Build Standalone .exe

```powershell
.\build.ps1
```

Output: `dist/praa.exe` — double-click to run, no Python needed.

## Architecture

```
src/
├── application/     ← Bootstrap + Orchestrator (DI, wiring)
├── domain/          ← Business logic (7 isolated modules)
│   ├── config/      ← Pydantic settings
│   ├── hotkey/      ← Global hotkey listener (pynput)
│   ├── clipboard/   ← Clipboard capture (tkinter)
│   ├── processor/   ← Text cleaner + lang detect + chunker
│   ├── tts/         ← edge-tts synthesis
│   ├── audio/       ← sounddevice playback + queue
│   └── tray/        ← System tray icon (pystray)
└── infrastructure/  ← EventBus, events, logging
```

## Running Tests

```powershell
python -m pytest tests/ -v
```

## License

Private utility — personal use only.
