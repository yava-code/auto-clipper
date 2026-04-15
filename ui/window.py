import ctypes
import threading
import pyperclip
import customtkinter as ctk
from core import queue, parser, config, groq_client, log
from ui import tray

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#1a1a1a"
ACCENT = "#6c63ff"
TEXT = "#e0e0e0"
DIM = "#2a2a2a"

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

        self.title("ClipQueue")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.configure(fg_color=BG)

        self.bind("<FocusIn>", lambda e: self.attributes("-alpha", 1.0))
        self.bind("<FocusOut>", lambda e: self.attributes("-alpha", 0.85))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._settings_open = False
        self._tray = None
        self._show_input()
        self._restore_position()
        self.after(300, self._init_tray)

    def _init_tray(self):
        queue.own_hwnd = ctypes.windll.user32.FindWindowW(None, "ClipQueue")
        self._tray = tray.start(self._show_from_tray, self._quit)

    def _restore_position(self):
        self.update_idletasks()
        x, y = self.cfg.get("window_x"), self.cfg.get("window_y")
        if x is None or y is None:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x, y = sw - 295, sh - 420
        self.geometry(f"+{x}+{y}")

    def _save_pos(self):
        self.cfg["window_x"] = self.winfo_x()
        self.cfg["window_y"] = self.winfo_y()
        config.save(self.cfg)

    def _on_close(self):
        # minimise to tray instead of quitting
        self._save_pos()
        self.withdraw()

    def _show_from_tray(self, icon=None, item=None):
        self.after(0, self.deiconify)
        self.after(50, lambda: self.attributes("-topmost", True))

    def _quit(self, icon=None, item=None):
        self._save_pos()
        if self._tray:
            self._tray.stop()
        self.after(0, self.destroy)

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------ input

    def _show_input(self):
        self._clear()
        self._settings_open = False
        self.geometry("280x390")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(header, text="ClipQueue", text_color=TEXT,
                     font=("", 13, "bold")).pack(side="left")
        ctk.CTkButton(header, text="⚙", width=28, height=24,
                      fg_color="transparent", hover_color=DIM,
                      text_color="#888", command=self._toggle_settings
                      ).pack(side="right")

        # textbox + paste button row
        txt_row = ctk.CTkFrame(self, fg_color="transparent")
        txt_row.pack(pady=(6, 2), padx=15, fill="x")

        self.txt = ctk.CTkTextbox(txt_row, width=210, height=120,
                                   fg_color=DIM, text_color="#666", border_width=0)
        self._placeholder = True
        self.txt.insert("0.0", "вставьте текст сюда...")
        self.txt.pack(side="left")

        btn_col = ctk.CTkFrame(txt_row, fg_color="transparent")
        btn_col.pack(side="left", padx=(4, 0), anchor="n")

        def _do_paste():
            try:
                text = pyperclip.paste()
            except Exception:
                return
            if not text:
                return
            if self._placeholder:
                self.txt.delete("0.0", "end")
                self.txt.configure(text_color=TEXT)
                self._placeholder = False
            self.txt.delete("0.0", "end")
            self.txt.insert("0.0", text)

        def _do_clear():
            self.txt.delete("0.0", "end")
            self.txt.insert("0.0", "вставьте текст сюда...")
            self.txt.configure(text_color="#666")
            self._placeholder = True

        ctk.CTkButton(btn_col, text="📋", width=32, height=56,
                      fg_color=DIM, hover_color="#3a3a3a",
                      text_color=TEXT, command=_do_paste,
                      font=("", 16)).pack(pady=(0, 4))
        ctk.CTkButton(btn_col, text="✕", width=32, height=56,
                      fg_color=DIM, hover_color="#3a3a3a",
                      text_color="#888", command=_do_clear,
                      font=("", 14)).pack()

        # explicit bindings so tkinter handles them regardless of keyboard lib state
        def _ctrl_a(e):
            self.txt.tag_add("sel", "0.0", "end")
            return "break"

        def _ctrl_v(e):
            if self._placeholder:
                self.txt.delete("0.0", "end")
                self.txt.configure(text_color=TEXT)
                self._placeholder = False
            # let tkinter's built-in paste proceed
            self.txt.event_generate("<<Paste>>")
            return "break"

        self.txt.bind("<Control-a>", _ctrl_a)
        self.txt.bind("<Control-A>", _ctrl_a)
        self.txt.bind("<Control-v>", _ctrl_v)
        self.txt.bind("<Control-V>", _ctrl_v)

        self.strat_var = ctk.StringVar(value="По строкам")
        ctk.CTkOptionMenu(self, values=list(STRAT_MAP),
                          variable=self.strat_var,
                          fg_color=DIM, button_color=ACCENT,
                          text_color=TEXT, width=250,
                          dropdown_fg_color=DIM).pack(pady=5, padx=15)

        ctk.CTkButton(self, text="Load Queue", command=self._load,
                      fg_color=ACCENT, hover_color="#5a52d5",
                      text_color="white", width=250).pack(pady=5, padx=15)

        self.preview = ctk.CTkLabel(self, text="Preview: —",
                                     text_color="#888", wraplength=250)
        self.preview.pack(pady=(4, 0))

        # AI section
        sep = ctk.CTkFrame(self, height=1, fg_color="#333")
        sep.pack(fill="x", padx=15, pady=8)

        ctk.CTkLabel(self, text="AI (Groq)", text_color="#666",
                     font=("", 11)).pack(anchor="w", padx=17)

        self.ai_entry = ctk.CTkEntry(self, width=250, height=30,
                                      fg_color=DIM, text_color=TEXT,
                                      border_color="#444",
                                      placeholder_text="что выделить из текста...")
        self.ai_entry.pack(padx=15, pady=(3, 5))

        self.ai_btn = ctk.CTkButton(self, text="Load with AI", command=self._load_ai,
                                     fg_color="#2d2b50", hover_color="#3d3b6a",
                                     text_color=TEXT, width=250)
        self.ai_btn.pack(padx=15)

        self.settings_frame = ctk.CTkScrollableFrame(
            self, fg_color=DIM, corner_radius=6, height=220)

    # ---------------------------------------------------------------- settings

    def _toggle_settings(self):
        self._settings_open = not self._settings_open
        if self._settings_open:
            self._build_settings_panel()
            self.settings_frame.pack(fill="x", padx=15, pady=(8, 8))
            self.geometry("280x640")
        else:
            self.settings_frame.pack_forget()
            self.geometry("280x390")

    def _build_settings_panel(self):
        for w in self.settings_frame.winfo_children():
            w.destroy()

        def section(label):
            ctk.CTkLabel(self.settings_frame, text=label, text_color=ACCENT,
                         font=("", 11, "bold"), anchor="w"
                         ).pack(fill="x", padx=8, pady=(8, 2))

        def row(label, default, width=80, show=None):
            f = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(f, text=label, text_color="#aaa", width=120,
                         anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=width, fg_color=BG,
                              text_color=TEXT, border_color="#444",
                              show=show)
            e.insert(0, str(default))
            e.pack(side="left")
            return e

        self._dirty = False

        # General
        section("Основное")
        self.e_sleep = row("Задержка (ms):", self.cfg.get("sleep_ms", 15))
        self.e_hotkey = row("Хоткей:", self.cfg.get("hotkey", "ctrl+v"), width=120)

        # Custom parsing
        section("Кастомный парсинг")

        f_mode = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        f_mode.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(f_mode, text="Режим:", text_color="#aaa",
                     width=120, anchor="w").pack(side="left")
        cur_mode = next((k for k, v in CUSTOM_MODES.items()
                         if v == self.cfg.get("custom_mode", "delimiter")),
                        "Разделитель")
        self.custom_mode_var = ctk.StringVar(value=cur_mode)
        ctk.CTkOptionMenu(f_mode, values=list(CUSTOM_MODES),
                          variable=self.custom_mode_var,
                          fg_color=BG, button_color="#444",
                          text_color=TEXT, width=120,
                          dropdown_fg_color=BG).pack(side="left")

        self.e_delim = row("Разделитель / паттерн:",
                            self.cfg.get("delimiter", ";") if
                            self.cfg.get("custom_mode", "delimiter") == "delimiter"
                            else self.cfg.get("regex_pattern", ""), width=100)

        # Transform
        section("Трансформация")
        self.e_prefix = row("Префикс:", self.cfg.get("transform_prefix", ""))
        self.e_suffix = row("Суффикс:", self.cfg.get("transform_suffix", ""))

        # AI
        section("AI (Groq)")

        f_model = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        f_model.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(f_model, text="Модель:", text_color="#aaa",
                     width=70, anchor="w").pack(side="left")
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
            fg_color=BG, button_color="#444", text_color=TEXT,
            width=165, dropdown_fg_color=BG,
        ).pack(side="left")

        self.e_apikey = row("API ключ:", self.cfg.get("groq_api_key", ""),
                            width=150, show="*")

        self.key_status = ctk.CTkLabel(
            self.settings_frame,
            text="ключ успешно добавлен" if self.cfg.get("groq_api_key") else "",
            text_color="#777",
            anchor="w",
        )
        self.key_status.pack(fill="x", padx=10, pady=(0, 4))

        self.btn_save = ctk.CTkButton(
            self.settings_frame, text="Сохранить",
            command=self._save_settings,
            fg_color=ACCENT, hover_color="#5a52d5",
            height=28, width=248,
            state="disabled",
        )
        self.btn_save.pack(pady=(6, 10), padx=8)

        def mark_dirty(*_):
            if self._dirty:
                return
            self._dirty = True
            try:
                self.btn_save.configure(state="normal", fg_color=ACCENT)
            except Exception:
                pass

        for e in [self.e_sleep, self.e_hotkey, self.e_delim, self.e_prefix, self.e_suffix, self.e_apikey]:
            e.bind("<KeyRelease>", lambda _e: mark_dirty())

        self.custom_mode_var.trace_add("write", mark_dirty)
        self.model_var.trace_add("write", mark_dirty)

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

        config.save(self.cfg)
        self.lg.info("settings saved sleep_ms=%s hotkey=%s model=%s key_set=%s",
                     ms, new_hotkey, self.cfg.get("groq_model"),
                     bool(self.cfg.get("groq_api_key")))
        self._dirty = False
        try:
            self.btn_save.configure(state="disabled", fg_color="#333")
        except Exception:
            pass
        self.key_status.configure(
            text="ключ успешно добавлен" if self.cfg.get("groq_api_key") else ""
        )
        self._toggle_settings()

    # ------------------------------------------------------------------ load

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
        self.lg.info("load queue manual items=%d", len(items))
        preview = " ".join(f"[{x}]" for x in items[:3])
        if len(items) > 3:
            preview += f" +{len(items) - 3}"
        self.preview.configure(text=f"Найдено {len(items)}: {preview}")
        queue.load(items)
        queue.on_complete = self._on_done
        self._show_active(items)

    def _load_ai(self):
        api_key = self.cfg.get("groq_api_key", "").strip()
        if not api_key:
            self.preview.configure(text="⚠ API ключ не задан — открой ⚙ и добавь",
                                   text_color="#ff6b6b")
            self.lg.warning("ai load blocked: no api key")
            return
        instruction = self.ai_entry.get().strip()
        if not instruction:
            self.preview.configure(text="⚠ Напиши инструкцию для AI")
            self.lg.info("ai load blocked: empty instruction")
            return
        if self._placeholder:
            return
        raw = self.txt.get("0.0", "end").strip()
        if not raw:
            return

        self.ai_btn.configure(state="disabled", text="Загружаю...")
        self.preview.configure(text="AI думает...", text_color="#888")
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
        self.ai_btn.configure(state="normal", text="Load with AI")
        if not items:
            self.preview.configure(text="AI: пустой результат")
            self.lg.info("ai done: empty items")
            return
        self.lg.info("ai done items=%d", len(items))
        preview = " ".join(f"[{x}]" for x in items[:3])
        if len(items) > 3:
            preview += f" +{len(items) - 3}"
        self.preview.configure(text=f"AI нашёл {len(items)}: {preview}")
        queue.load(items)
        queue.on_complete = self._on_done
        self._show_active(items)

    def _on_ai_error(self, msg):
        self.ai_btn.configure(state="normal", text="Load with AI")
        self.preview.configure(text=f"AI ошибка: {msg[:60]}", text_color="#ff6b6b")
        self.lg.error("ai error: %s", msg)

    # ----------------------------------------------------------------- active

    def _show_active(self, items):
        self._clear()
        self.geometry("280x180")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(10, 4))
        ctk.CTkLabel(top, text="ClipQueue", text_color=TEXT,
                     font=("", 13, "bold")).pack(side="left")
        self.prog = ctk.CTkLabel(top, text=f"0/{len(items)}", text_color=ACCENT)
        self.prog.pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, height=70,
                                                  fg_color=DIM, border_width=0)
        self.list_frame.pack(fill="x", padx=15, pady=4)
        self._refresh_list()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        self.pause_btn = ctk.CTkButton(row, text="Pause", command=self._pause,
                                        fg_color="#333", hover_color="#444", width=115)
        self.pause_btn.pack(side="left", padx=4)
        ctk.CTkButton(row, text="Reset", command=self._reset,
                      fg_color="#333", hover_color="#444", width=115).pack(side="left", padx=4)

        self._poll()

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, item in enumerate(queue.items):
            color = ACCENT if i == queue.idx else TEXT
            prefix = "→ " if i == queue.idx else "   "
            ctk.CTkLabel(self.list_frame, text=f"{prefix}{item}",
                          text_color=color, anchor="w").pack(fill="x", padx=4)

    def _poll(self):
        if not queue.active:
            return
        self.prog.configure(text=f"{queue.idx}/{len(queue.items)}")
        self._refresh_list()
        self.after(100, self._poll)

    def _pause(self):
        queue.active = not queue.active
        self.pause_btn.configure(text="Resume" if not queue.active else "Pause")
        self.lg.info("pause toggled active=%s", queue.active)
        if queue.active:
            self._poll()

    def _reset(self):
        queue.reset()
        self.lg.info("reset")
        self._show_input()

    def _on_done(self):
        self.after(0, lambda: self.prog.configure(
            text=f"{len(queue.items)}/{len(queue.items)}"))
        self.after(0, self._refresh_list)
