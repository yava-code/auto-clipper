//! ClipQueue — native Win32 backend
//! WH_KEYBOARD_LL requires NO admin (unlike Python `keyboard` lib).
//! Pre-load strategy: clipboard is filled BEFORE user presses Ctrl+V.

#![windows_subsystem = "windows"]

use std::iter::once;
use std::sync::{
    atomic::{AtomicBool, AtomicIsize, AtomicUsize, Ordering::SeqCst},
    Mutex,
};
use windows::core::{w, PCWSTR};
use windows::Win32::{
    Foundation::*,
    Graphics::{Dwm::*, Gdi::*},
    System::{DataExchange::*, LibraryLoader::GetModuleHandleW, Memory::*},
    UI::{Input::KeyboardAndMouse::*, WindowsAndMessaging::*},
};

// ─── control ids ─────────────────────────────────────────────────────────────
const ID_EDIT: i32      = 101;
const ID_COMBO: i32     = 102;
const ID_BTN_LOAD: i32  = 103;
const ID_LIST: i32      = 104;
const ID_BTN_PAUSE: i32 = 105;
const ID_BTN_RESET: i32 = 106;
const ID_PROGRESS: i32  = 107;
const ID_PREVIEW: i32   = 108;
const TIMER_ADV: usize  = 1;

// ─── Win32 style/message values not re-exported by the crate ─────────────────
const ES_MULTILINE: u32    = 0x0004;
const ES_WANTRETURN: u32   = 0x1000;
const ES_AUTOVSCROLL: u32  = 0x0040;
const CBS_DROPDOWNLIST: u32 = 3;
const LBS_NOTIFY: u32      = 0x0001;
const WM_CTLCOLOREDIT: u32    = 0x0133;
const WM_CTLCOLORLISTBOX: u32 = 0x0134;
const WM_CTLCOLORSTATIC: u32  = 0x0138;
const LB_RESETCONTENT: u32 = 0x0184;
const LB_ADDSTRING: u32    = 0x0180;
const LB_SETTOPINDEX: u32  = 0x0197;
const CB_ADDSTRING: u32    = 0x0143;
const CB_SETCURSEL: u32    = 0x014E;
const CB_GETCURSEL: u32    = 0x0147;
const WM_SETFONT: u32      = 0x0030;
const CF_UNICODETEXT: u32  = 13;

// ─── colors — COLORREF is 0x00BBGGRR ─────────────────────────────────────────
const C_BG:  COLORREF = COLORREF(0x001a1a1a);
const C_DIM: COLORREF = COLORREF(0x002a2a2a);
const C_TXT: COLORREF = COLORREF(0x00e0e0e0);

// ─── global state ─────────────────────────────────────────────────────────────
static HWND_MAIN:   AtomicIsize = AtomicIsize::new(0);
static HOOK_H:      AtomicIsize = AtomicIsize::new(0);
static Q_ACTIVE:    AtomicBool  = AtomicBool::new(false);
static PAUSED:      AtomicBool  = AtomicBool::new(false);
static Q_IDX:       AtomicUsize = AtomicUsize::new(0);
static SLEEP_MS:    AtomicUsize = AtomicUsize::new(15);
static ACTIVE_MODE: AtomicBool  = AtomicBool::new(false);
static Q_ITEMS:     Mutex<Vec<String>> = Mutex::new(Vec::new());
static BG_BRUSH:    AtomicIsize = AtomicIsize::new(0);
static DIM_BRUSH:   AtomicIsize = AtomicIsize::new(0);

// ─── entry ────────────────────────────────────────────────────────────────────
fn main() {
    unsafe {
        let hmod = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
        let hi   = HINSTANCE(hmod.0);

        BG_BRUSH.store(CreateSolidBrush(C_BG).0, SeqCst);
        DIM_BRUSH.store(CreateSolidBrush(C_DIM).0, SeqCst);

        let cls = w!("CQ");
        let wc  = WNDCLASSW {
            style:         CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc:   Some(wnd_proc),
            hInstance:     hi,
            lpszClassName: cls,
            hbrBackground: HBRUSH(BG_BRUSH.load(SeqCst)),
            hCursor:       LoadCursorW(HINSTANCE(0), IDC_ARROW).unwrap_or_default(),
            ..Default::default()
        };
        RegisterClassW(&wc);

        let sw = GetSystemMetrics(SM_CXSCREEN);
        let sh = GetSystemMetrics(SM_CYSCREEN);

        let hwnd = CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TOOLWINDOW,
            cls,
            w!("ClipQueue"),
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
            sw - 295, sh - 370,
            280, 320,
            HWND(0), HMENU(0), hi,
            None,
        );

        HWND_MAIN.store(hwnd.0, SeqCst);

        // dark title bar (Windows 10 20H1+)
        let dark = BOOL(1);
        let _ = DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            &dark as *const BOOL as *const _,
            std::mem::size_of::<BOOL>() as u32,
        );

        // 85% opacity when unfocused
        let _ = SetLayeredWindowAttributes(hwnd, COLORREF(0), 217, LWA_ALPHA);

        ShowWindow(hwnd, SW_SHOW);
        let _ = UpdateWindow(hwnd);

        // WH_KEYBOARD_LL works without admin — key advantage over Python version
        let hook = SetWindowsHookExW(WH_KEYBOARD_LL, Some(kbhook), HINSTANCE(0), 0)
            .unwrap_or_default();
        HOOK_H.store(hook.0, SeqCst);

        let mut msg = MSG::default();
        while GetMessageW(&mut msg, HWND(0), 0, 0).0 > 0 {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        let _ = UnhookWindowsHookEx(HHOOK(HOOK_H.load(SeqCst)));
        let _ = DeleteObject(HGDIOBJ(BG_BRUSH.load(SeqCst)));
        let _ = DeleteObject(HGDIOBJ(DIM_BRUSH.load(SeqCst)));
    }
}

// ─── window procedure ─────────────────────────────────────────────────────────
unsafe extern "system" fn wnd_proc(
    hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM,
) -> LRESULT {
    match msg {
        WM_CREATE => {
            create_all_controls(hwnd);
            show_input_mode(hwnd);
            LRESULT(0)
        }

        WM_COMMAND => {
            let id = (wp.0 & 0xFFFF) as i32;
            match id {
                ID_BTN_LOAD  => { btn_load(hwnd);  LRESULT(0) }
                ID_BTN_PAUSE => { btn_pause(hwnd); LRESULT(0) }
                ID_BTN_RESET => { btn_reset(hwnd); LRESULT(0) }
                _ => DefWindowProcW(hwnd, msg, wp, lp),
            }
        }

        WM_TIMER => {
            if wp.0 == TIMER_ADV {
                let _ = KillTimer(hwnd, TIMER_ADV);
                on_timer(hwnd);
            }
            LRESULT(0)
        }

        WM_ERASEBKGND => {
            let hdc = HDC(wp.0 as isize);
            let mut rc = RECT::default();
            let _ = GetClientRect(hwnd, &mut rc);
            FillRect(hdc, &rc, HBRUSH(BG_BRUSH.load(SeqCst)));
            LRESULT(1)
        }

        // dark controls
        x if x == WM_CTLCOLOREDIT
            || x == WM_CTLCOLORLISTBOX
            || x == WM_CTLCOLORSTATIC =>
        {
            let hdc = HDC(wp.0 as isize);
            SetTextColor(hdc, C_TXT);
            SetBkColor(hdc, C_DIM);
            LRESULT(DIM_BRUSH.load(SeqCst))
        }

        WM_ACTIVATE => {
            let inactive = (wp.0 & 0xFFFF) as u32 == 0; // WA_INACTIVE = 0
            let alpha: u8 = if inactive { 217 } else { 255 };
            let _ = SetLayeredWindowAttributes(hwnd, COLORREF(0), alpha, LWA_ALPHA);
            DefWindowProcW(hwnd, msg, wp, lp)
        }

        WM_DESTROY => {
            let _ = UnhookWindowsHookEx(HHOOK(HOOK_H.load(SeqCst)));
            PostQuitMessage(0);
            LRESULT(0)
        }

        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

// ─── keyboard hook — no admin needed with WH_KEYBOARD_LL ─────────────────────
unsafe extern "system" fn kbhook(
    code: i32, wp: WPARAM, lp: LPARAM,
) -> LRESULT {
    if code >= 0 {
        let info = &*(lp.0 as *const KBDLLHOOKSTRUCT);
        let is_down = wp.0 as u32 == WM_KEYDOWN || wp.0 as u32 == WM_SYSKEYDOWN;

        if is_down && info.vkCode == u32::from(VK_V.0) {
            let ctrl = GetKeyState(VK_CONTROL.0 as i32) < 0;
            let own  = GetForegroundWindow().0 == HWND_MAIN.load(SeqCst);

            if ctrl && Q_ACTIVE.load(SeqCst) && !PAUSED.load(SeqCst) && !own {
                // clipboard already pre-loaded — let Ctrl+V pass through,
                // then advance queue after SLEEP_MS via SetTimer (no blocking!)
                let _ = SetTimer(
                    HWND(HWND_MAIN.load(SeqCst)),
                    TIMER_ADV,
                    SLEEP_MS.load(SeqCst) as u32,
                    None,
                );
            }
        }
    }
    CallNextHookEx(HHOOK(0), code, wp, lp)
}

// ─── timer: advance queue ─────────────────────────────────────────────────────
unsafe fn on_timer(hwnd: HWND) {
    let next = Q_IDX.load(SeqCst) + 1;
    let items = Q_ITEMS.lock().unwrap();

    if next < items.len() {
        Q_IDX.store(next, SeqCst);
        clip_set(&items[next]);
        drop(items);
        update_list(hwnd);
        update_progress(hwnd);
    } else {
        Q_ACTIVE.store(false, SeqCst);
        drop(items);
        set_ctrl_text(hwnd, ID_PROGRESS, "Готово ✓");
        update_list(hwnd);
    }
}

// ─── button handlers ──────────────────────────────────────────────────────────
unsafe fn btn_load(hwnd: HWND) {
    let raw = get_ctrl_text(hwnd, ID_EDIT);
    if raw.trim().is_empty() { return; }

    let strategy = {
        let combo = GetDlgItem(hwnd, ID_COMBO);
        SendMessageW(combo, CB_GETCURSEL, WPARAM(0), LPARAM(0)).0 as usize
    };
    let parsed = parse(&raw, strategy);
    if parsed.is_empty() { return; }

    let preview: String = parsed.iter().take(3)
        .map(|s| format!("[{}]", s))
        .collect::<Vec<_>>().join(" ");
    let info = if parsed.len() > 3 {
        format!("{} +{}", preview, parsed.len() - 3)
    } else {
        preview
    };
    set_ctrl_text(hwnd, ID_PREVIEW, &format!("Найдено {}: {}", parsed.len(), info));

    clip_set(&parsed[0]);
    let mut items = Q_ITEMS.lock().unwrap();
    *items = parsed;
    drop(items);

    Q_IDX.store(0, SeqCst);
    Q_ACTIVE.store(true, SeqCst);
    PAUSED.store(false, SeqCst);

    show_active_mode(hwnd);
}

unsafe fn btn_pause(hwnd: HWND) {
    let now = PAUSED.load(SeqCst);
    PAUSED.store(!now, SeqCst);
    let label = if !now { "Resume" } else { "Pause" };
    set_ctrl_text(hwnd, ID_BTN_PAUSE, label);
}

unsafe fn btn_reset(hwnd: HWND) {
    Q_ACTIVE.store(false, SeqCst);
    PAUSED.store(false, SeqCst);
    Q_IDX.store(0, SeqCst);
    show_input_mode(hwnd);
}

// ─── ui: create all controls once ────────────────────────────────────────────
unsafe fn create_all_controls(hwnd: HWND) {
    let hi = HINSTANCE(GetWindowLongPtrW(hwnd, GWLP_HINSTANCE));
    let font = GetStockObject(DEFAULT_GUI_FONT);

    macro_rules! mkctrl {
        ($cls:expr, $text:expr, $style:expr, $x:expr,$y:expr,$w:expr,$h:expr, $id:expr) => {{
            let ctrl = CreateWindowExW(
                WINDOW_EX_STYLE::default(),
                $cls, $text, $style,
                $x, $y, $w, $h,
                hwnd, HMENU($id as isize), hi, None,
            );
            SendMessageW(ctrl, WM_SETFONT, WPARAM(font.0 as usize), LPARAM(1));
            ctrl
        }};
    }

    // ── input mode ──
    mkctrl!(
        w!("EDIT"), w!(""),
        WS_CHILD | WS_VISIBLE | WS_BORDER | WS_VSCROLL
            | WINDOW_STYLE(ES_MULTILINE | ES_WANTRETURN | ES_AUTOVSCROLL),
        15, 30, 250, 120, ID_EDIT
    );

    let combo = mkctrl!(
        w!("COMBOBOX"), w!(""),
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | WINDOW_STYLE(CBS_DROPDOWNLIST),
        15, 160, 250, 120, ID_COMBO
    );
    for s in ["По строкам\0", "По запятым\0", "По предложениям\0", "Кастомный\0"] {
        let ws: Vec<u16> = s.encode_utf16().collect();
        SendMessageW(combo, CB_ADDSTRING, WPARAM(0), LPARAM(ws.as_ptr() as isize));
    }
    SendMessageW(combo, CB_SETCURSEL, WPARAM(0), LPARAM(0));

    mkctrl!(
        w!("BUTTON"), w!("Load Queue"),
        WS_CHILD | WS_VISIBLE,
        15, 195, 250, 28, ID_BTN_LOAD
    );

    mkctrl!(
        w!("STATIC"), w!("Preview: —"),
        WS_CHILD | WS_VISIBLE | WINDOW_STYLE(0x0040), // SS_LEFTNOWORDWRAP
        15, 233, 250, 18, ID_PREVIEW
    );

    // ── active mode (hidden initially) ──
    mkctrl!(
        w!("STATIC"), w!("0/0"),
        WS_CHILD | WINDOW_STYLE(0x0001), // SS_RIGHT
        170, 8, 95, 18, ID_PROGRESS
    );

    mkctrl!(
        w!("LISTBOX"), w!(""),
        WS_CHILD | WS_VSCROLL | WS_BORDER | WINDOW_STYLE(LBS_NOTIFY),
        15, 30, 250, 80, ID_LIST
    );

    mkctrl!(
        w!("BUTTON"), w!("Pause"),
        WS_CHILD,
        15, 120, 118, 28, ID_BTN_PAUSE
    );

    mkctrl!(
        w!("BUTTON"), w!("Reset"),
        WS_CHILD,
        147, 120, 118, 28, ID_BTN_RESET
    );
}

unsafe fn show_input_mode(hwnd: HWND) {
    ACTIVE_MODE.store(false, SeqCst);
    for id in [ID_EDIT, ID_COMBO, ID_BTN_LOAD, ID_PREVIEW] {
        show_ctrl(hwnd, id, true);
    }
    for id in [ID_PROGRESS, ID_LIST, ID_BTN_PAUSE, ID_BTN_RESET] {
        show_ctrl(hwnd, id, false);
    }
    let _ = SetWindowPos(hwnd, HWND(0), 0, 0, 280, 270,
        SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
    let _ = InvalidateRect(hwnd, None, TRUE);
}

unsafe fn show_active_mode(hwnd: HWND) {
    ACTIVE_MODE.store(true, SeqCst);
    for id in [ID_EDIT, ID_COMBO, ID_BTN_LOAD, ID_PREVIEW] {
        show_ctrl(hwnd, id, false);
    }
    for id in [ID_PROGRESS, ID_LIST, ID_BTN_PAUSE, ID_BTN_RESET] {
        show_ctrl(hwnd, id, true);
    }
    update_list(hwnd);
    update_progress(hwnd);
    let _ = SetWindowPos(hwnd, HWND(0), 0, 0, 280, 165,
        SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
    let _ = InvalidateRect(hwnd, None, TRUE);
}

unsafe fn show_ctrl(hwnd: HWND, id: i32, visible: bool) {
    let h = GetDlgItem(hwnd, id);
    if h.0 != 0 {
        ShowWindow(h, if visible { SW_SHOW } else { SW_HIDE });
    }
}

// ─── ui helpers ───────────────────────────────────────────────────────────────
unsafe fn update_list(hwnd: HWND) {
    let list = GetDlgItem(hwnd, ID_LIST);
    if list.0 == 0 { return; }
    SendMessageW(list, LB_RESETCONTENT, WPARAM(0), LPARAM(0));

    let items = Q_ITEMS.lock().unwrap();
    let idx   = Q_IDX.load(SeqCst);

    for (i, item) in items.iter().enumerate() {
        let line = if i == idx {
            format!("→ {}\0", item)
        } else {
            format!("   {}\0", item)
        };
        let ws: Vec<u16> = line.encode_utf16().collect();
        SendMessageW(list, LB_ADDSTRING, WPARAM(0), LPARAM(ws.as_ptr() as isize));
    }
    if idx < items.len() {
        SendMessageW(list, LB_SETTOPINDEX,
            WPARAM(idx.saturating_sub(1)), LPARAM(0));
    }
}

unsafe fn update_progress(hwnd: HWND) {
    let items = Q_ITEMS.lock().unwrap();
    let idx   = Q_IDX.load(SeqCst);
    set_ctrl_text(hwnd, ID_PROGRESS, &format!("{}/{}", idx, items.len()));
}

unsafe fn set_ctrl_text(hwnd: HWND, id: i32, text: &str) {
    let h = GetDlgItem(hwnd, id);
    if h.0 != 0 {
        let ws: Vec<u16> = text.encode_utf16().chain(once(0)).collect();
        let _ = SetWindowTextW(h, PCWSTR(ws.as_ptr()));
    }
}

unsafe fn get_ctrl_text(hwnd: HWND, id: i32) -> String {
    let h = GetDlgItem(hwnd, id);
    if h.0 == 0 { return String::new(); }
    let len = GetWindowTextLengthW(h) as usize;
    if len == 0 { return String::new(); }
    let mut buf = vec![0u16; len + 1];
    GetWindowTextW(h, &mut buf);
    String::from_utf16_lossy(&buf[..len])
}

// ─── clipboard (UTF-16 for Cyrillic / any Unicode) ────────────────────────────
unsafe fn clip_set(text: &str) {
    if OpenClipboard(HWND(0)).is_err() { return; }
    let _ = EmptyClipboard();

    let wide: Vec<u16> = text.encode_utf16().chain(once(0u16)).collect();
    let bytes = wide.len() * 2;

    let hmem = match GlobalAlloc(GMEM_MOVEABLE, bytes) {
        Ok(h) => h,
        Err(_) => { let _ = CloseClipboard(); return; }
    };

    let ptr = GlobalLock(hmem) as *mut u16;
    std::ptr::copy_nonoverlapping(wide.as_ptr(), ptr, wide.len());
    let _ = GlobalUnlock(hmem);

    let _ = SetClipboardData(CF_UNICODETEXT, HANDLE(hmem.0 as isize));
    let _ = CloseClipboard();
}

// ─── parser ───────────────────────────────────────────────────────────────────
fn parse(text: &str, strategy: usize) -> Vec<String> {
    match strategy {
        // По строкам
        0 => text.lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty())
            .collect(),
        // По запятым
        1 => text.split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect(),
        // По предложениям
        2 => {
            let mut out = Vec::new();
            let mut buf = String::new();
            for ch in text.chars() {
                buf.push(ch);
                if matches!(ch, '.' | '!' | '?') {
                    let t = buf.trim().to_string();
                    if !t.is_empty() { out.push(t); }
                    buf.clear();
                }
            }
            if !buf.trim().is_empty() { out.push(buf.trim().to_string()); }
            out
        }
        // Кастомный — по пробельным символам
        _ => text.split_whitespace()
            .map(|s| s.to_string())
            .collect(),
    }
}
