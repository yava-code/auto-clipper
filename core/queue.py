import os
import ctypes
import time
import keyboard
import pyperclip

from core import log

items = []
idx = 0
active = False
on_complete = None
sleep_ms = 15
_hotkey = "ctrl+v"
_hook_registered = False

_our_pid = os.getpid()


def _clipqueue_focused():
    fg = ctypes.windll.user32.GetForegroundWindow()
    if not fg:
        return False
    pid = ctypes.c_ulong(0)
    ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    return pid.value == _our_pid


def _register():
    global _hook_registered
    if _hook_registered:
        return
    keyboard.add_hotkey(_hotkey, _on_ctrl_v, suppress=False)
    _hook_registered = True
    log.get().info("hook registered %s", _hotkey)


def _unregister():
    global _hook_registered
    if not _hook_registered:
        return
    try:
        keyboard.remove_hotkey(_hotkey)
    except Exception:
        pass
    _hook_registered = False
    log.get().info("hook unregistered")


def load(arr):
    global items, idx, active
    if not arr:
        return
    items = arr
    idx = 0
    active = True
    pyperclip.copy(items[0])
    _register()
    log.get().info("queue loaded items=%d", len(arr))


def reset():
    global active
    active = False
    _unregister()
    log.get().info("queue reset")


def _on_ctrl_v():
    global idx, active
    if _clipqueue_focused():
        # our window is focused — let native paste happen, don't advance
        return
    if not active:
        return

    log.get().info("ctrl+v advance idx=%d/%d", idx, len(items))
    time.sleep(sleep_ms / 1000)

    idx += 1
    if idx < len(items):
        pyperclip.copy(items[idx])
    else:
        active = False
        _unregister()
        log.get().info("queue complete")
        if on_complete:
            on_complete()


def start(hotkey="ctrl+v"):
    """Store hotkey — does NOT register hook. Hook is registered only when queue loads."""
    global _hotkey
    _hotkey = hotkey
    log.get().info("queue init hotkey=%s", hotkey)


def change_hotkey(new_hotkey):
    global _hotkey
    was_registered = _hook_registered
    _unregister()
    _hotkey = new_hotkey
    log.get().info("hotkey changed to %s", new_hotkey)
    if was_registered:
        _register()
