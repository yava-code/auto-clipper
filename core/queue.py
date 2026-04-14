import ctypes
import time
import keyboard
import pyperclip

items = []
idx = 0
active = False
on_complete = None
sleep_ms = 15
own_hwnd = None   # set by window after creation
_hotkey = None


def load(arr):
    global items, idx, active
    items = arr
    idx = 0
    active = True
    pyperclip.copy(items[0])


def _clipqueue_focused():
    if own_hwnd is None:
        return False
    return ctypes.windll.user32.GetForegroundWindow() == own_hwnd


def on_ctrl_v():
    global idx, active
    if _clipqueue_focused() or not active:
        keyboard.send('ctrl+v')
        return

    keyboard.send('ctrl+v')
    time.sleep(sleep_ms / 1000)

    idx += 1
    if idx < len(items):
        pyperclip.copy(items[idx])
    else:
        active = False
        if on_complete:
            on_complete()


def start(hotkey="ctrl+v"):
    global _hotkey
    _hotkey = hotkey
    keyboard.add_hotkey(hotkey, on_ctrl_v, suppress=True)


def change_hotkey(new_hotkey):
    global _hotkey
    if _hotkey:
        try:
            keyboard.remove_hotkey(_hotkey)
        except Exception:
            pass
    _hotkey = new_hotkey
    keyboard.add_hotkey(new_hotkey, on_ctrl_v, suppress=True)
