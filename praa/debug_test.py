"""
PRAA Debug Script — Test pynput + pystray independently.

Run this script, then:
1. Check if a tray icon appears (green square in taskbar).
2. Press any keys — you should see them printed.
3. Press Ctrl+Shift+R — check if it's detected.
4. Press ESC to exit.
"""
import sys
import threading
from pynput import keyboard

print("=" * 50)
print("  PRAA DEBUGGER")
print("=" * 50)

# ---- TEST 1: pystray tray icon ----
print("\n[TEST 1] Tray Icon...")
try:
    from PIL import Image
    import pystray

    img = Image.new("RGB", (64, 64), (0, 200, 0))  # Green square
    icon = pystray.Icon("debug", img, "DEBUG TRAY")

    def run_icon():
        icon.run()

    t = threading.Thread(target=run_icon, daemon=True)
    t.start()
    print("  → pystray started on thread. Look for GREEN SQUARE in taskbar tray area.")
    print("  → If not visible, click the ↑ arrow next to the clock.")
except Exception as e:
    print(f"  → FAILED: {e}")

# ---- TEST 2: pynput keyboard listener ----
print("\n[TEST 2] Keyboard Listener...")
print("  Press keys to see what pynput reports.")
print("  Press Ctrl+Shift+R to test hotkey detection.")
print("  Press ESC to exit.\n")

pressed_keys = set()

def on_press(key):
    pressed_keys.add(key)
    # Print key info
    if isinstance(key, keyboard.KeyCode):
        print(f"  KEY PRESS: KeyCode  char={key.char!r}  vk={getattr(key, 'vk', '?')}")
    else:
        print(f"  KEY PRESS: {key}")

    # Check Ctrl+Shift+R combo
    normalized = set()
    for k in pressed_keys:
        if k == keyboard.Key.ctrl_r:
            normalized.add(keyboard.Key.ctrl_l)
        elif k == keyboard.Key.shift_r:
            normalized.add(keyboard.Key.shift)
        elif isinstance(k, keyboard.KeyCode) and k.vk is not None:
            normalized.add(keyboard.KeyCode.from_vk(k.vk))
        else:
            normalized.add(k)

    target = frozenset({
        keyboard.Key.ctrl_l,
        keyboard.Key.shift,
        keyboard.KeyCode.from_vk(82),  # 82 = ord('R'), matches by vk code
    })

    if target.issubset(normalized):
        print("\n  ✅ HOTKEY DETECTED: Ctrl+Shift+R matched!")
        print(f"     Raw pressed: {pressed_keys}")
        print(f"     Normalized:  {normalized}")
    else:
        # Show what's missing
        missing = target - normalized
        if missing and len(pressed_keys) >= 2:
            print(f"     (Missing for hotkey: {missing})")

def on_release(key):
    pressed_keys.discard(key)
    if key == keyboard.Key.esc:
        print("\nESC pressed — exiting.")
        return False

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

print("\nDebug complete.")
