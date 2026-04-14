from ui.window import App
from core import queue, config

cfg = config.load()
app = App(cfg)
queue.start(cfg["hotkey"])
app.mainloop()
