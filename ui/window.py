import ctypes
import threading
from ctypes import byref, c_int
import pyperclip
import customtkinter as ctk
from core import queue, parser, config, groq_client, log
from ui import tray

W = 400
H_PILL = 52
H_FULL = 390
ANIM_STEPS = 6
ANIM_MS = 18

COLLAPSED = 0
EXPANDED_INPUT = 1
EXPANDED_ACTIVE = 2


def _palette(name):
    if name not in ("light", "dark"):
        name = "light"
    if name == "light":
        return dict(
            bg="#FFFFFF", dim="#f5f5f5", text="#1a1a1a",
            placeholder="#999999", accent="#6c63ff",
            progress_bg="#e8e8e8", hover_accent="#5a52d5",
            muted="#aaaaaa", label_sec="#555555", key_hint="#777777",
            pill_border="#dedede", error="#ff6b6b",
        )
    return dict(
        bg="#1a1a1a", dim="#2a2a2a", text="#e0e0e0",
        placeholder="#888888", accent="#6c63ff",
        progress_bg="#333333", hover_accent="#5a52d5",
        muted="#888888", label_sec="#aaaaaa", key_hint="#888888",
        pill_border="#444444", error="#ff6b6b",
    )

STRAT_MAP = {
    "По строкам": "lines",
    "По запятым": "comma",
    "По предложениям": "sentences",
    "Кастомный": "custom",
}

CUSTOM_MODES = {
    "Разделитель": "delimiter",
    "Regex split": "regex_split",
    "Regex findall": "regex_findall",
}


class App(ctk.CTk):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.lg = log.get()
        queue.sleep_ms = cfg["sleep_ms"]

        ut = cfg.get("ui_theme", "light")
        if ut not in ("light", "dark"):
            ut = "light"
            self.cfg["ui_theme"] = ut
        self.c = _palette(ut)
        ctk.set_appearance_mode("dark" if ut == "dark" else "light")

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=self.c["bg"])

        self._state = COLLAPSED
        self._drag_x = self._drag_y = 0
        self._dragged = False
        self._anim_id = None
        self._placeholder = True
        self._settings_open = False
        self._tray = None
        self._list_labels = []
        self._last_queue_len = -1
        self._screen_w = self.winfo_screenwidth()
        self._screen_h = self.winfo_screenheight()

        x = (self._screen_w - W) // 2
        y = self._screen_h - 40 - H_PILL
        self.geometry(f"{W}x{H_PILL}+{x}+{y}")

        self._build_pill_bar()
        self._build_content_frame()
        self._bind_drag_surfaces()
        self.update_idletasks()
        self._apply_dwm()
        self._restore_position()
        self.after(300, self._init_tray)

    # ---------------------------------------------------------------- WinAPI

    def _apply_dwm(self):
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
        self._hwnd = hwnd
        try:
            dwmapi = ctypes.windll.dwmapi
        except Exception:
            return
        try:
            dwmapi.DwmSetWindowAttribute(hwnd, 33, byref(c_int(2)), 4)
        except Exception:
            pass
        try:
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, (ex | 0x80) & ~0x80000)
        except Exception:
            pass

    def _apply_theme(self):
        ut = self.cfg.get("ui_theme", "light")
        if ut not in ("light", "dark"):
            ut = "light"
            self.cfg["ui_theme"] = ut
        self.c = _palette(ut)
        ctk.set_appearance_mode("dark" if ut == "dark" else "light")
        self.configure(fg_color=self.c["bg"])
        self._content_outer.configure(fg_color=self.c["bg"])
        self._pill.configure(
            fg_color=self.c["bg"], border_color=self.c["pill_border"])
        self._pill_icon.configure(text_color=self.c["accent"])
        self._pill_btn.configure(
            fg_color=self.c["accent"], hover_color=self.c["hover_accent"])
        self._sync_pill_label()

    def _sync_pill_label(self):
        if self._state == COLLAPSED:
            if queue.active and queue.items and queue.idx < len(queue.items):
                item = queue.items[queue.idx]
                s = item if len(item) <= 28 else item[:25] + "..."
                self._pill_label.configure(
                    text=f"→ {s}  {queue.idx}/{len(queue.items)}",
                    text_color=self.c["accent"])
            else:
                self._pill_label.configure(
                    text="ClipQueue", text_color=self.c["placeholder"])
        elif self._state == EXPANDED_INPUT:
            self._pill_label.configure(
                text="Вставьте текст", text_color=self.c["text"])
        else:
            self._pill_label.configure(text_color=self.c["accent"])

    def _apply_noactivate(self, on):
        try:
            ex = ctypes.windll.user32.GetWindowLongW(self._hwnd, -20)
            if on:
                ctypes.windll.user32.SetWindowLongW(self._hwnd, -20, ex | 0x08000000)
            else:
                ctypes.windll.user32.SetWindowLongW(self._hwnd, -20, ex & ~0x08000000)
        except Exception:
            pass

    # ---------------------------------------------------------------- tray / pos

    def _init_tray(self):
        self._tray = tray.start(self._show_from_tray, self._quit)

    def _restore_position(self):
        x, y = self.cfg.get("window_x"), self.cfg.get("window_y")
        if x is not None and y is not None:
            self._screen_h = y + self.winfo_height() + 40
            self.geometry(f"{W}x{H_PILL}+{x}+{y}")

    def _save_pos(self):
        self.cfg["window_x"] = self.winfo_x()
        self.cfg["window_y"] = self.winfo_y()
        config.save(self.cfg)

    def _show_from_tray(self, icon=None, item=None):
        self.after(0, self.deiconify)
        self.after(50, lambda: self.attributes("-topmost", True))

    def _quit(self, icon=None, item=None):
        self._save_pos()
        if self._tray:
            self._tray.stop()
        self.after(0, self.destroy)

    # ---------------------------------------------------------------- build

    def _build_pill_bar(self):
        self._pill = ctk.CTkFrame(
            self, fg_color=self.c["bg"], height=H_PILL,
            border_width=1, border_color=self.c["pill_border"],
        )
        self._pill.pack(side="bottom", fill="x")
        self._pill.pack_propagate(False)

        self._pill_icon = ctk.CTkLabel(
            self._pill, text="📎", width=40,
            text_color=self.c["accent"], font=("", 18))
        self._pill_icon.pack(side="left", padx=(10, 0))

        self._pill_btn = ctk.CTkButton(
            self._pill, text="↑", width=36, height=36,
            fg_color=self.c["accent"], hover_color=self.c["hover_accent"],
            text_color="white", font=("", 16, "bold"),
            command=self._on_pill_click,
        )
        self._pill_btn.pack(side="right", padx=(0, 10))

        self._gear_btn = ctk.CTkButton(
            self._pill, text="⚙", width=30, height=30,
            fg_color="transparent", hover_color=self.c["dim"],
            text_color=self.c["muted"], font=("", 13),
            command=self._on_gear_click,
        )
        self._gear_btn.pack(side="right", padx=(0, 4))

        self._pill_label = ctk.CTkLabel(
            self._pill, text="ClipQueue",
            text_color=self.c["placeholder"], font=("", 13), anchor="w",
        )
        self._pill_label.pack(side="left", fill="x", expand=True, padx=8)

        for w in [self._pill, self._pill_icon, self._pill_label,
                  self._pill_btn, self._gear_btn]:
            w.bind("<ButtonPress-1>", self._start_drag_proxy)
            w.bind("<B1-Motion>", self._do_drag)
            w.bind("<ButtonRelease-1>", self._on_drag_release)

    def _build_content_frame(self):
        self._content_outer = ctk.CTkFrame(self, fg_color=self.c["bg"])
        self._content_outer.pack(side="top", fill="both", expand=True)

    def _drag_blocked(self, w):
        cur = w
        while cur and cur != self:
            if isinstance(cur, (ctk.CTkTextbox, ctk.CTkEntry, ctk.CTkOptionMenu)):
                return True
            try:
                wc = cur.winfo_class()
            except Exception:
                wc = ""
            if wc in ("Text", "Entry"):
                return True
            cur = getattr(cur, "master", None)
        return False

    def _start_drag_proxy(self, e):
        if self._drag_blocked(e.widget):
            return
        self._start_drag(e)

    def _on_drag_release(self, _e=None):
        if self._dragged:
            self._save_pos()

    def _bind_drag_surfaces(self):
        self._content_outer.bind("<ButtonPress-1>", self._start_drag_proxy)
        self._content_outer.bind("<B1-Motion>", self._do_drag)
        self._content_outer.bind("<ButtonRelease-1>", self._on_drag_release)

    def _wire_outer_drag(self, outer):
        outer.bind("<ButtonPress-1>", self._start_drag_proxy)
        outer.bind("<B1-Motion>", self._do_drag)
        outer.bind("<ButtonRelease-1>", self._on_drag_release)

    # ---------------------------------------------------------------- state

    def _set_state(self, new_state):
        self._state = new_state
        self._settings_open = False

        if new_state == COLLAPSED:
            self._pill_btn.configure(text="↑")
            self._sync_pill_label()
            self._apply_noactivate(False)
            self._animate_to(H_PILL)

        elif new_state == EXPANDED_INPUT:
            self._pill_btn.configure(text="↓")
            self._sync_pill_label()
            self._apply_noactivate(False)
            self._build_input_panel()
            self._animate_to(H_FULL)

        elif new_state == EXPANDED_ACTIVE:
            self._pill_btn.configure(text="↓")
            self._sync_pill_label()
            self._apply_noactivate(True)
            self._build_active_panel()
            self._animate_to(H_FULL)

    def _on_pill_click(self):
        if self._dragged:
            self._dragged = False
            return
        if self._state == COLLAPSED:
            self._set_state(EXPANDED_INPUT)
        else:
            self._set_state(COLLAPSED)

    def _on_gear_click(self):
        if self._dragged:
            self._dragged = False
            return
        if self._state == COLLAPSED:
            self._set_state(EXPANDED_INPUT)
            self.after(ANIM_STEPS * ANIM_MS + 20, self._toggle_settings)
        else:
            self._toggle_settings()

    # ---------------------------------------------------------------- animate

    def _animate_to(self, target_h):
        if self._anim_id:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
        if abs(self.winfo_height() - target_h) > 20:
            self._content_outer.pack_forget()
        self._anim_step(self.winfo_height(), target_h, 0)

    def _anim_step(self, start, target, step):
        t = step / ANIM_STEPS
        t = t * t * (3 - 2 * t)
        h = int(start + (target - start) * t)
        y = self._screen_h - 40 - h
        self.wm_geometry(f"{W}x{h}+{self.winfo_x()}+{y}")
        if step < ANIM_STEPS:
            self._anim_id = self.after(
                ANIM_MS, lambda: self._anim_step(start, target, step + 1))
        else:
            self._anim_id = None
            self._content_outer.pack(side="top", fill="both", expand=True)

    # ---------------------------------------------------------------- drag

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()
        self._dragged = False

    def _do_drag(self, e):
        if abs(e.x_root - self.winfo_x() - self._drag_x) > 3 or \
           abs(e.y_root - self.winfo_y() - self._drag_y) > 3:
            self._dragged = True
        new_x = e.x_root - self._drag_x
        new_y = e.y_root - self._drag_y
        self._screen_h = new_y + self.winfo_height() + 40
        self.geometry(f"{W}x{self.winfo_height()}+{new_x}+{new_y}")

    # ---------------------------------------------------------------- input

    def _build_input_panel(self):
        for w in self._content_outer.winfo_children():
            w.destroy()
        self._list_labels = []
        self._last_queue_len = -1

        outer = ctk.CTkFrame(self._content_outer, fg_color=self.c["bg"])
        outer.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self._wire_outer_drag(outer)

        self.txt = ctk.CTkTextbox(
            outer, fg_color="#f8f8f8", text_color=self.c["placeholder"],
            border_width=1, border_color="#e0e0e0", font=("", 13),
        )
        self.txt.insert("0.0", "вставьте текст сюда...")
        self._placeholder = True
        self.txt.pack(fill="both", expand=True, pady=(0, 4))

        ctk.CTkFrame(outer, height=1, fg_color=self.c["progress_bg"]).pack(
            fill="x", pady=(0, 5))

        def _focus_in(e):
            queue.pause_hook()
            if self._placeholder:
                self.txt.delete("0.0", "end")
                self.txt.configure(text_color=self.c["text"])
                self._placeholder = False

        def _focus_out(e):
            queue.resume_hook()
            if not self.txt.get("0.0", "end").strip():
                self.txt.delete("0.0", "end")
                self.txt.insert("0.0", "вставьте текст сюда...")
                self.txt.configure(text_color=self.c["placeholder"])
                self._placeholder = True

        self.txt.bind("<FocusIn>", _focus_in)
        self.txt.bind("<FocusOut>", _focus_out)
        self.bind("<FocusIn>", lambda e: queue.pause_hook())
        self.bind("<FocusOut>", lambda e: queue.resume_hook())

        # AI row
        ai_row = ctk.CTkFrame(outer, fg_color="transparent")
        ai_row.pack(fill="x", pady=(0, 4))
        self.ai_entry = ctk.CTkEntry(
            ai_row, fg_color=self.c["dim"], text_color=self.c["text"],
            border_width=0, font=("", 12),
            placeholder_text="инструкция для AI...",
        )
        self.ai_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            ai_row, text="AI", width=48, height=30,
            fg_color=self.c["accent"], hover_color=self.c["hover_accent"],
            text_color="white", font=("", 12),
            command=self._load_ai,
        ).pack(side="left")

        ctk.CTkFrame(outer, height=1, fg_color=self.c["progress_bg"]).pack(
            fill="x", pady=(0, 6))

        # footer
        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x")

        self.strat_var = ctk.StringVar(value="По строкам")
        ctk.CTkOptionMenu(
            footer, values=list(STRAT_MAP),
            variable=self.strat_var,
            fg_color=self.c["dim"], button_color=self.c["accent"],
            text_color=self.c["text"], width=130,
            dropdown_fg_color=self.c["bg"], font=("", 12),
        ).pack(side="left")

        def _do_paste():
            try:
                text = pyperclip.paste()
            except Exception:
                return
            if not text:
                return
            if self._placeholder:
                self.txt.delete("0.0", "end")
                self.txt.configure(text_color=self.c["text"])
                self._placeholder = False
            self.txt.delete("0.0", "end")
            self.txt.insert("0.0", text)

        def _do_clear():
            self.txt.delete("0.0", "end")
            self.txt.insert("0.0", "вставьте текст сюда...")
            self.txt.configure(text_color=self.c["placeholder"])
            self._placeholder = True

        ctk.CTkButton(
            footer, text="✕", width=32, height=30,
            fg_color="transparent", hover_color=self.c["dim"],
            text_color=self.c["muted"], font=("", 14),
            command=_do_clear,
        ).pack(side="right")
        ctk.CTkButton(
            footer, text="📋", width=32, height=30,
            fg_color="transparent", hover_color=self.c["dim"],
            text_color=self.c["text"], font=("", 14),
            command=_do_paste,
        ).pack(side="right")
        ctk.CTkButton(
            footer, text="Load →", width=80, height=30,
            fg_color=self.c["accent"], hover_color=self.c["hover_accent"],
            text_color="white", font=("", 12),
            command=self._load,
        ).pack(side="right", padx=(6, 0))

        self.status_label = ctk.CTkLabel(
            footer, text="", text_color=self.c["muted"], font=("", 11))
        self.status_label.pack(side="left", padx=(8, 0))

    # ---------------------------------------------------------------- active

    def _build_active_panel(self):
        for w in self._content_outer.winfo_children():
            w.destroy()
        self._list_labels = []
        self._last_queue_len = -1

        outer = ctk.CTkFrame(self._content_outer, fg_color=self.c["bg"])
        outer.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self._wire_outer_drag(outer)

        self._list_scroll = ctk.CTkScrollableFrame(
            outer, fg_color=self.c["dim"], border_width=0)
        self._list_scroll.pack(fill="both", expand=True, pady=(0, 6))

        self.prog_bar = ctk.CTkProgressBar(
            outer, height=6, fg_color=self.c["progress_bg"],
            progress_color=self.c["accent"])
        self.prog_bar.set(0)
        self.prog_bar.pack(fill="x", pady=(0, 4))

        ctk.CTkFrame(outer, height=1, fg_color=self.c["progress_bg"]).pack(
            fill="x", pady=(0, 6))

        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x")

        self.pause_btn = ctk.CTkButton(
            footer, text="⏸", width=36, height=30,
            fg_color=self.c["dim"], hover_color=self.c["progress_bg"],
            text_color=self.c["text"], font=("", 14),
            command=self._pause,
        )
        self.pause_btn.pack(side="left")

        ctk.CTkButton(
            footer, text="✕", width=36, height=30,
            fg_color=self.c["dim"], hover_color=self.c["progress_bg"],
            text_color=self.c["muted"], font=("", 14),
            command=self._reset,
        ).pack(side="left", padx=(6, 0))

        self.prog_label = ctk.CTkLabel(
            footer, text="0 / 0", text_color=self.c["accent"], font=("", 12))
        self.prog_label.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            footer, text="⚙", width=36, height=30,
            fg_color="transparent", hover_color=self.c["dim"],
            text_color=self.c["muted"], font=("", 14),
            command=self._toggle_settings,
        ).pack(side="right")

        self._poll()

    # ---------------------------------------------------------------- settings

    def _toggle_settings(self):
        self._settings_open = not self._settings_open
        if self._settings_open:
            self._build_settings_panel()
        else:
            if self._state == EXPANDED_ACTIVE:
                self._build_active_panel()
            else:
                self._build_input_panel()

    def _build_settings_panel(self):
        for w in self._content_outer.winfo_children():
            w.destroy()

        outer = ctk.CTkFrame(self._content_outer, fg_color=self.c["bg"])
        outer.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self._wire_outer_drag(outer)

        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkButton(
            hdr, text="← Назад", width=80, height=28,
            fg_color="transparent", hover_color=self.c["dim"],
            text_color=self.c["accent"], font=("", 12),
            command=self._toggle_settings,
        ).pack(side="left")
        ctk.CTkLabel(hdr, text="Настройки", text_color=self.c["text"],
                     font=("", 13, "bold")).pack(side="left", padx=8)

        scroll = ctk.CTkScrollableFrame(outer, fg_color=self.c["dim"], border_width=0)
        scroll.pack(fill="both", expand=True)
        self._populate_settings(scroll)

    def _populate_settings(self, scroll):
        def section(label):
            ctk.CTkLabel(scroll, text=label, text_color=self.c["accent"],
                         font=("", 11, "bold"), anchor="w"
                         ).pack(fill="x", padx=8, pady=(8, 2))

        def row(label, default, width=80, show=None):
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(f, text=label, text_color=self.c["label_sec"],
                         width=130, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=width, fg_color=self.c["bg"],
                             text_color=self.c["text"], border_width=1,
                             border_color=self.c["progress_bg"], show=show)
            e.insert(0, str(default))
            e.pack(side="left")
            return e

        self._dirty = False

        section("Основное")
        self.e_sleep = row("Задержка (ms):", self.cfg.get("sleep_ms", 15))
        self.e_hotkey = row("Хоткей:", self.cfg.get("hotkey", "ctrl+v"), width=120)

        section("Кастомный парсинг")
        f_mode = ctk.CTkFrame(scroll, fg_color="transparent")
        f_mode.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(f_mode, text="Режим:", text_color=self.c["label_sec"],
                     width=130, anchor="w").pack(side="left")
        cur_mode = next((k for k, v in CUSTOM_MODES.items()
                         if v == self.cfg.get("custom_mode", "delimiter")),
                        "Разделитель")
        self.custom_mode_var = ctk.StringVar(value=cur_mode)
        ctk.CTkOptionMenu(f_mode, values=list(CUSTOM_MODES),
                          variable=self.custom_mode_var,
                          fg_color=self.c["bg"], button_color=self.c["progress_bg"],
                          text_color=self.c["text"], width=120,
                          dropdown_fg_color=self.c["bg"]).pack(side="left")

        self.e_delim = row(
            "Разделитель / паттерн:",
            self.cfg.get("delimiter", ";") if
            self.cfg.get("custom_mode", "delimiter") == "delimiter"
            else self.cfg.get("regex_pattern", ""),
            width=100,
        )

        section("Трансформация")
        self.e_prefix = row("Префикс:", self.cfg.get("transform_prefix", ""))
        self.e_suffix = row("Суффикс:", self.cfg.get("transform_suffix", ""))

        section("AI (Groq)")
        f_model = ctk.CTkFrame(scroll, fg_color="transparent")
        f_model.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(f_model, text="Модель:", text_color=self.c["label_sec"],
                     width=130, anchor="w").pack(side="left")
        self.model_var = ctk.StringVar(
            value=self.cfg.get("groq_model", "llama-3.3-70b-versatile"))
        ctk.CTkOptionMenu(
            f_model,
            values=[
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "llama3-70b-8192",
                "llama3-8b-8192",
                "gemma2-9b-it",
            ],
            variable=self.model_var,
            fg_color=self.c["bg"], button_color=self.c["progress_bg"],
            text_color=self.c["text"],
            width=165, dropdown_fg_color=self.c["bg"],
        ).pack(side="left")

        self.e_apikey = row("API ключ:", self.cfg.get("groq_api_key", ""),
                            width=150, show="*")

        self.key_status = ctk.CTkLabel(
            scroll,
            text="ключ задан" if self.cfg.get("groq_api_key") else "",
            text_color=self.c["key_hint"], anchor="w",
        )
        self.key_status.pack(fill="x", padx=10, pady=(0, 4))

        section("Внешний вид")
        f_theme = ctk.CTkFrame(scroll, fg_color="transparent")
        f_theme.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(f_theme, text="Тема:", text_color=self.c["label_sec"],
                     width=130, anchor="w").pack(side="left")
        cur_th = self.cfg.get("ui_theme", "light")
        if cur_th not in ("light", "dark"):
            cur_th = "light"
        self.theme_var = ctk.StringVar(
            value="Светлая" if cur_th == "light" else "Тёмная")
        ctk.CTkOptionMenu(
            f_theme,
            values=["Светлая", "Тёмная"],
            variable=self.theme_var,
            fg_color=self.c["bg"], button_color=self.c["progress_bg"],
            text_color=self.c["text"], width=120,
            dropdown_fg_color=self.c["bg"],
        ).pack(side="left")

        self.btn_save = ctk.CTkButton(
            scroll, text="Сохранить",
            command=self._save_settings,
            fg_color=self.c["accent"], hover_color=self.c["hover_accent"],
            height=28, width=240,
            state="disabled",
        )
        self.btn_save.pack(pady=(6, 10), padx=8)

        def mark_dirty(*_):
            if self._dirty:
                return
            self._dirty = True
            try:
                self.btn_save.configure(state="normal")
            except Exception:
                pass

        for e in [self.e_sleep, self.e_hotkey, self.e_delim,
                  self.e_prefix, self.e_suffix, self.e_apikey]:
            e.bind("<KeyRelease>", lambda _e: mark_dirty())

        self.custom_mode_var.trace_add("write", mark_dirty)
        self.model_var.trace_add("write", mark_dirty)
        self.theme_var.trace_add("write", mark_dirty)

    def _save_settings(self):
        try:
            ms = int(self.e_sleep.get())
        except ValueError:
            ms = 15
        new_hotkey = self.e_hotkey.get().strip() or "ctrl+v"
        mode = CUSTOM_MODES.get(self.custom_mode_var.get(), "delimiter")
        pat_or_delim = self.e_delim.get() or ";"

        self.cfg["sleep_ms"] = ms
        self.cfg["custom_mode"] = mode
        self.cfg["transform_prefix"] = self.e_prefix.get()
        self.cfg["transform_suffix"] = self.e_suffix.get()
        self.cfg["groq_api_key"] = self.e_apikey.get().strip()
        self.cfg["groq_model"] = self.model_var.get()

        if mode == "delimiter":
            self.cfg["delimiter"] = pat_or_delim
        else:
            self.cfg["regex_pattern"] = pat_or_delim

        queue.sleep_ms = ms

        if new_hotkey != self.cfg.get("hotkey"):
            self.cfg["hotkey"] = new_hotkey
            queue.change_hotkey(new_hotkey)

        self.cfg["ui_theme"] = (
            "dark" if self.theme_var.get() == "Тёмная" else "light")

        config.save(self.cfg)
        self._apply_theme()
        self.lg.info(
            "settings saved sleep_ms=%s hotkey=%s model=%s key_set=%s theme=%s",
            ms, new_hotkey, self.cfg.get("groq_model"),
            bool(self.cfg.get("groq_api_key")), self.cfg.get("ui_theme"),
        )
        self._dirty = False
        self._toggle_settings()

    # ---------------------------------------------------------------- load

    def _get_items_from_text(self):
        if self._placeholder:
            return None
        raw = self.txt.get("0.0", "end").strip()
        if not raw:
            return None
        strat = STRAT_MAP.get(self.strat_var.get(), "lines")
        items = parser.parse(
            raw, strat,
            delimiter=self.cfg.get("delimiter", ";"),
            custom_mode=self.cfg.get("custom_mode", "delimiter"),
            regex_pattern=self.cfg.get("regex_pattern", ""),
        )
        items = parser.transform(
            items,
            prefix=self.cfg.get("transform_prefix", ""),
            suffix=self.cfg.get("transform_suffix", ""),
        )
        return items

    def _load(self):
        items = self._get_items_from_text()
        if not items:
            return
        self.lg.info("load queue items=%d", len(items))
        queue.load(items)
        queue.on_complete = self._on_done
        self._pill_label.configure(
            text=f"{len(items)} элементов", text_color=self.c["accent"])
        self._set_state(EXPANDED_ACTIVE)

    def _load_ai(self):
        api_key = self.cfg.get("groq_api_key", "").strip()
        if not api_key:
            try:
                self.status_label.configure(
                    text="⚠ API ключ не задан", text_color=self.c["error"])
            except Exception:
                pass
            self.lg.warning("ai load: no api key")
            return
        instruction = self.ai_entry.get().strip()
        if not instruction:
            try:
                self.status_label.configure(
                    text="⚠ Нужна инструкция", text_color=self.c["error"])
            except Exception:
                pass
            return
        if self._placeholder:
            return
        raw = self.txt.get("0.0", "end").strip()
        if not raw:
            return

        try:
            self.status_label.configure(
                text="AI думает...", text_color=self.c["muted"])
        except Exception:
            pass
        self.lg.info("ai load start")

        def run():
            try:
                model = self.cfg.get("groq_model", "llama-3.3-70b-versatile")
                items = groq_client.extract(api_key, instruction, raw, model=model)
                items = parser.transform(
                    items,
                    prefix=self.cfg.get("transform_prefix", ""),
                    suffix=self.cfg.get("transform_suffix", ""),
                )
                self.after(0, lambda: self._on_ai_done(items))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_ai_error(m))

        threading.Thread(target=run, daemon=True).start()

    def _on_ai_done(self, items):
        if not items:
            try:
                self.status_label.configure(text="AI: пустой результат")
            except Exception:
                pass
            self.lg.info("ai done: empty")
            return
        self.lg.info("ai done items=%d", len(items))
        queue.load(items)
        queue.on_complete = self._on_done
        self._pill_label.configure(
            text=f"{len(items)} элементов", text_color=self.c["accent"])
        self._set_state(EXPANDED_ACTIVE)

    def _on_ai_error(self, msg):
        try:
            self.status_label.configure(
                text=f"AI: {msg[:50]}", text_color=self.c["error"])
        except Exception:
            pass
        self.lg.error("ai error: %s", msg)

    # ---------------------------------------------------------------- poll

    def _poll(self):
        if not queue.active:
            return
        n, idx = len(queue.items), queue.idx
        try:
            self.prog_label.configure(text=f"{idx} / {n}")
            self.prog_bar.set(idx / n if n else 0)
        except Exception:
            return
        self._sync_pill_label()

        if n != self._last_queue_len:
            for w in self._list_scroll.winfo_children():
                w.destroy()
            self._list_labels = []
            for i, item in enumerate(queue.items):
                lbl = ctk.CTkLabel(
                    self._list_scroll,
                    text=f"{'→' if i == idx else '  '} {item}",
                    text_color=self.c["accent"] if i == idx else self.c["text"],
                    anchor="w", font=("", 12),
                )
                lbl.pack(fill="x", padx=4, pady=1)
                self._list_labels.append(lbl)
            self._last_queue_len = n
        else:
            for i, lbl in enumerate(self._list_labels):
                lbl.configure(
                    text=f"{'→' if i == idx else '  '} {queue.items[i]}",
                    text_color=self.c["accent"] if i == idx else self.c["text"],
                )

        self.after(100, self._poll)

    def _pause(self):
        queue.active = not queue.active
        self.pause_btn.configure(text="▶" if not queue.active else "⏸")
        self.lg.info("pause toggled active=%s", queue.active)
        if queue.active:
            self._poll()

    def _reset(self):
        queue.reset()
        self.lg.info("reset")
        self._set_state(COLLAPSED)

    def _on_done(self):
        self.after(0, lambda: self._set_state(COLLAPSED))
