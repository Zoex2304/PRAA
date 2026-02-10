# PRAA — User Cheat Sheet

**Personal Read Aloud Assistant**
*Instant text-to-speech for any application on Windows.*

---

## 🚀 How to Run
1. **Exe Mode**: Double-click `praa.exe` in the folder.
   - *Note: The app runs in the background. Look for the teal speech bubble icon in your system tray (bottom-right).*
2. **Source Mode**: Run `python src/main.py` from the command line.

---

## ⌨️ Hotkeys
| Hotkey | Action | Description |
|:-------|:-------|:------------|
| **`Ctrl + Shift + R`** | **READ** | Copies selected text and starts reading aloud. |
| **`Ctrl + Shift + S`** | **STOP** | Instantly stops reading and clears the queue. |

> *Tip: You can change these hotkeys in `config.json`.*

---

## 🖱️ System Tray Controls
*Right-click the **teal speech bubble icon** in your taskbar:*

- **▶ Resume / ⏸ Pause**: Control playback.
- **⏹ Stop**: Stop reading completely.
- **Speed**: Change reading speed on the fly (0.75x to 2.0x).
- **Voice**: Switch between **Ardi (Male)** and **Gadis (Female)**.
- **Exit**: Close the application completely.

---

## 🧠 Smart Features (Automatic)
- **Language Detection**: Automatically switches voices if you select English (US) vs. Indonesian text.
- **Text Cleaning**: Skips confidentially reading URLs (`http://...`), emojis, and Markdown symbols.
- **Smart Chunking**: Reads long documents smoothly by breaking them into natural sentences.
- **Reactive Config**: Change speed or voice mid-session via the tray menu, and it remembers your choice.

---

## ⚙️ Advanced Config (`config.json`)
*Edit this file with Notepad to customize defaults:*

```json
{
  "voice_gender": "female",       // Default voice: "male" or "female"
  "speed_rate": 1.25,             // Default reading speed
  "hotkey_read": "<ctrl>+<shift>+r",
  "hotkey_stop": "<ctrl>+<shift>+s",
  "language_preference": "auto"   // "auto", "id", or "en"
}
```
```
*Note: Config changes via tray menu are saved automatically.*

---

## 🛡️ Troubleshooting

### "Threat Blocked" / Antivirus Warning
If Windows Defender blocks `praa.exe` (e.g. `Program:Win32/Contebrew.A!ml`), this is a **False Positive**.
- **Why?** Our app listens for hotkeys (`Ctrl+Shift+R`) globally. Antivirus AI often marks *unsigned* apps that "listen to keyboards" as suspicious.
- **Safety**: You built this from source code (`src/`), so it is 100% safe.
- **Fix**:
  1. Open **Windows Security** > **Virus & threat protection**.
  2. Click **Protection history**.
  3. Find the "Threat blocked" item and select **Actions** > **Allow on device**.
  4. OR: Add the folder `D:\tts-edge` to **Exclusions**.

