# Changelog

## 2026-04-14 — Phase 0: Core Logic

- `core/__init__.py` — создан (пустой пакет)
- `core/queue.py` — логика очереди: `load()`, `on_ctrl_v()`, `start()`
- `main.py` — точка входа с хардкодед массивом
- `requirements.txt` — keyboard, pyperclip

## 2026-04-14 — Phase 1: MVP UI

- `core/queue.py` — убран `keyboard.wait()` из `start()`, добавлен `on_complete` колбэк
- `core/parser.py` — стратегии парсинга: lines, comma, sentences
- `ui/__init__.py` — создан (пустой пакет)
- `ui/window.py` — customtkinter floating окно: Input Mode + Active Mode, прозрачность, always-on-top
- `main.py` — переписан: запускает UI + keyboard хук
- `requirements.txt` — добавлен customtkinter
