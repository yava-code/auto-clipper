# Changelog

## 2026-04-14 — Phase 0: Core Logic

- `core/__init__.py` — создан (пустой пакет)
- `core/queue.py` — логика очереди: `load()`, `on_ctrl_v()`, `start()`
- `main.py` — точка входа с хардкодед массивом
- `requirements.txt` — keyboard, pyperclip

## 2026-04-15 — Bugfixes Round 4: paste button + key bindings

- `ui/window.py` — кнопка 📋 (paste из clipboard) и ✕ (очистить) рядом с textbox — обходит любые проблемы с keyboard hook
- `ui/window.py` — явные tkinter bindings для Ctrl+A (select all) и Ctrl+V (paste + clear placeholder)

## 2026-04-15 — Bugfixes Round 3: textbox fix

- `core/queue.py` — полная переработка архитектуры hook: `start()` теперь только сохраняет hotkey; hook регистрируется ТОЛЬКО при `load()` и снимается при завершении/reset; во время input mode никакого перехвата клавиш нет совсем → Ctrl+V/A/C/X в textbox работают нативно
- `core/queue.py` — добавлен `reset()` для явного снятия hook + сброса состояния
- `ui/window.py` — placeholder в textbox: click-to-clear (серый текст исчезает при фокусе, возвращается когда пусто); больше не надо вручную выделять и удалять
- `ui/window.py` — `_reset()` вызывает `queue.reset()` вместо прямого `queue.active = False`

## 2026-04-15 — Bugfixes Round 2

- `core/queue.py` — критический фикс: `suppress=False` вместо `suppress=True` — нативный Ctrl+V больше не перехватывается (clipboard pre-load работает без suppress); убран `keyboard.send()` из hook (бесконечный цикл)
- `core/config.py` — авто-загрузка API ключа из `.env` (форматы `GROQ_API_KEY=...` и raw `gsk_...`); добавлено логирование
- `core/groq_client.py` — добавлено логирование запросов/ответов; улучшена обработка ошибок парсинга JSON
- `ui/window.py` — ошибки AI и отсутствие ключа подсвечиваются красным; обновлён список моделей Groq (убраны deprecated)

## 2026-04-15 — Bugfixes + Tests

- `core/queue.py` — исправлен баг: `_clipqueue_focused()` теперь сравнивает по PID (GetWindowThreadProcessId), а не по HWND — работает когда фокус у дочернего виджета (textbox)
- `core/queue.py` — исправлен баг: `load([])` теперь возвращает early (не краш IndexError)
- `ui/window.py` — settings panel заменена на CTkScrollableFrame (height=220) — фикс скролла
- `ui/window.py` — добавлен выбор модели Groq (OptionMenu: 5 моделей) в настройках и конфиге
- `core/config.py` — новое поле `groq_model` (default: llama-3.3-70b-versatile)
- `.gitignore` — переписан с glob паттернами (убраны хардкодед имена файлов)
- `native/src/main.rs` — исправлен под windows crate 0.52: `use windows::core::w`, убраны Option<> обёртки для HWND/HMENU, CreateWindowExW возвращает HWND напрямую, GlobalAlloc возвращает Result<HGLOBAL>, OpenClipboard возвращает Result, добавлена константа CF_UNICODETEXT=13
- `tests/test_parser.py` — новый: 17 тестов (Lines, Comma, Sentences, Custom, Transform)
- `tests/test_queue.py` — новый: 6 тестов (load поведение, state, defaults)

## 2026-04-15 — Phase 4: Native Rust

- `native/Cargo.toml` — workspace: windows 0.58, embed-resource, release profile (opt-z, lto, strip)
- `native/clipqueue.manifest` — `asInvoker` (NO admin), DPI PerMonitorV2
- `native/clipqueue.rc` — resource script для embed-resource
- `native/build.rs` — embed manifest через embed-resource crate
- `native/src/main.rs` — полная Win32 реализация:
  - WH_KEYBOARD_LL без admin (ключевое отличие от Python)
  - Pre-load стратегия + SetTimer вместо sleep (hook не блокируется)
  - Dark mode через DwmSetWindowAttribute + WM_CTLCOLORxxx
  - Input mode / Active mode переключение через ShowWindow
  - UTF-16 clipboard для Cyrillic / любого Unicode
  - AlwaysOnTop + 85% opacity через WS_EX_LAYERED

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
