# Changelog

## 2026-04-14 — Phase 0: Core Logic

- `core/__init__.py` — создан (пустой пакет)
- `core/queue.py` — логика очереди: `load()`, `on_ctrl_v()`, `start()`
- `main.py` — точка входа с хардкодед массивом
- `requirements.txt` — keyboard, pyperclip

## 2026-04-15 — Финальная сборка

- `ui/tray.py` — новый: system tray (pystray + PIL иконка), меню Показать / Выход
- `ui/window.py` — X закрывает в трей, `_show_from_tray`, `_quit`; `_init_tray` заменяет `_store_hwnd`
- `installer.iss` — новый: Inno Setup скрипт (ярлык на рабочем столе, автозапуск, русский язык)
- `build.spec` — добавлены hidden imports: pystray, PIL
- `requirements.txt` — добавлены pystray, Pillow, pyinstaller
- `README.md` — переписан полностью

## 2026-04-15 — Phase 3 + Bugfix

- `core/queue.py` — исправлен баг: Ctrl+V теперь не перехватывается когда ClipQueue в фокусе (WinAPI GetForegroundWindow)
- `core/parser.py` — расширен кастомный режим: regex_split, regex_findall; добавлен transform() с prefix/suffix
- `core/config.py` — новые поля: custom_mode, regex_pattern, transform_prefix/suffix, groq_api_key
- `core/groq_client.py` — новый: Groq API (llama-3.3-70b-versatile), strip markdown из ответа
- `ui/window.py` — AI секция (инструкция + Load with AI, фоновый поток); расширённые настройки (кастомный режим, паттерн, трансформация, API ключ)
- `requirements.txt` — добавлен groq

## 2026-04-15 — Phase 2: Stable v1

- `core/config.py` — новый модуль: load/save config.json, поддержка frozen .exe
- `core/parser.py` — добавлена стратегия "custom" с кастомным разделителем
- `core/queue.py` — `sleep_ms` из конфига, `change_hotkey()`, `start(hotkey)`
- `ui/window.py` — панель настроек (⚙), сохранение позиции окна, стратегия "Кастомный"
- `main.py` — загрузка config.json, передача hotkey в queue.start()
- `config.json` — создан с дефолтами
- `build.spec` — PyInstaller конфиг с `uac_admin=True`, `console=False`
- `README.md` — написан

## 2026-04-14 — Phase 1: MVP UI

- `core/queue.py` — убран `keyboard.wait()` из `start()`, добавлен `on_complete` колбэк
- `core/parser.py` — стратегии парсинга: lines, comma, sentences
- `ui/__init__.py` — создан (пустой пакет)
- `ui/window.py` — customtkinter floating окно: Input Mode + Active Mode, прозрачность, always-on-top
- `main.py` — переписан: запускает UI + keyboard хук
- `requirements.txt` — добавлен customtkinter
