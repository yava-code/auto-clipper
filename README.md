# ClipQueue

Paste multiple items one by one with Ctrl+V. No alt-tabbing. No manual copying.

Load a list -> switch to your target app -> Ctrl+V x N. The queue advances automatically.

## Install & Run

```
pip install -r requirements.txt
python main.py        # must run as Administrator
```

The app minimises to the system tray when you close the window. Right-click the tray icon to quit.

## Build .exe

```
pyinstaller build.spec
```

Output: `dist/ClipQueue.exe` - auto-requests UAC on launch, no Python needed.

## Build installer

1. Build the .exe first (see above)
2. Open `installer.iss` with [Inno Setup 6](https://jrsoftware.org/isinfo.php)
3. Click Compile - installer appears in `dist/`

## Usage

1. Paste or type your list in the text area
2. Choose a split strategy
3. Click **Load Queue**
4. Switch to your target app and press Ctrl+V repeatedly

## Parse strategies

| Strategy | Splits on |
|----------|-----------|
| Lines | newlines |
| Comma | `,` |
| Sentences | `.` `!` `?` |
| Custom - Delimiter | any character you set in settings |
| Custom - Regex split | `re.split(pattern, text)` |
| Custom - Regex findall | `re.findall(pattern, text)` |

## Transform (settings)

Add a **prefix** and/or **suffix** to every extracted item.
Example: prefix `"` + suffix `"` wraps each item in quotes.

## AI parser (Groq)

1. Add your [Groq API key](https://console.groq.com) in the gear settings
2. Write a plain-language instruction: `"extract all email addresses"`
3. Click **Load with AI**

Uses `llama-3.3-70b-versatile`. Falls back gracefully if the API is unavailable.

## Settings

| Key | Default | Notes |
|-----|---------|-------|
| sleep_ms | 15 | Delay after paste. Use 30-50ms for Excel/SAP |
| hotkey | ctrl+v | Hotkey to intercept |
| custom_mode | delimiter | delimiter / regex_split / regex_findall |
| delimiter | ; | Used in delimiter mode |
| regex_pattern | | Used in regex modes |
| transform_prefix | | Prepended to each item |
| transform_suffix | | Appended to each item |
| groq_api_key | | Optional - enables AI parser |

Saved to `config.json` next to the executable.

---

## Native version (Phase 4)

Located in `native/`. Rust + raw Win32 — no Python, no admin, ~2MB.

```
cd native
cargo build --release
# output: native/target/release/ClipQueue.exe
```

**Key advantages over the Python version:**

| | Python | Native |
|-|--------|--------|
| Admin required | Yes (keyboard lib) | **No** (WH_KEYBOARD_LL) |
| Startup | ~3s | instant |
| Binary size | ~40MB | ~2MB |
| Runtime | Python + deps | none |

The native version uses `WH_KEYBOARD_LL` (low-level keyboard hook) which Windows allows
without elevation. The hook never blocks — it uses `SetTimer` instead of `sleep()`.
