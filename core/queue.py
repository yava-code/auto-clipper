import time
import keyboard
import pyperclip

items = []
idx = 0
active = False
on_complete = None


def load(arr):
    global items, idx, active
    items = arr
    idx = 0
    active = True
    pyperclip.copy(items[0])


def on_ctrl_v():
    global idx, active
    if not active:
        keyboard.send('ctrl+v')
        return

    keyboard.send('ctrl+v')
    time.sleep(0.015)

    idx += 1
    if idx < len(items):
        pyperclip.copy(items[idx])
    else:
        active = False
        if on_complete:
            on_complete()


def start():
    keyboard.add_hotkey('ctrl+v', on_ctrl_v, suppress=True)
