import threading
from PIL import Image, ImageDraw
import pystray


def _make_img():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 63, 63], radius=14, fill='#6c63ff')
    # three bars = queue
    for i, (y, w) in enumerate([(14, 36), (26, 28), (38, 20)]):
        d.rectangle([14, y, 14 + w, y + 7], fill='white')
    return img


def start(on_show, on_quit):
    icon = pystray.Icon(
        "ClipQueue",
        _make_img(),
        "ClipQueue",
        menu=pystray.Menu(
            pystray.MenuItem("Показать", on_show, default=True),
            pystray.MenuItem("Выход", on_quit),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
