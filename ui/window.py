import customtkinter as ctk
from core import queue, parser

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
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ClipQueue")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.configure(fg_color=BG)

        self.bind("<FocusIn>", lambda e: self.attributes("-alpha", 1.0))
        self.bind("<FocusOut>", lambda e: self.attributes("-alpha", 0.85))

        self._show_input()
        self._position_bottom_right()

    def _position_bottom_right(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw - 295}+{sh - 360}")

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _show_input(self):
        self._clear()
        self.geometry("280x320")

        self.txt = ctk.CTkTextbox(self, width=250, height=140,
                                   fg_color=DIM, text_color=TEXT,
                                   border_width=0)
        self.txt.insert("0.0", "вставьте текст\nсюда...")
        self.txt.pack(pady=(12, 5), padx=15)

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
        self.preview.pack(pady=8)

    def _load(self):
        raw = self.txt.get("0.0", "end").strip()
        placeholder = "вставьте текст\nсюда..."
        if not raw or raw == placeholder:
            return

        strat = STRAT_MAP.get(self.strat_var.get(), "lines")
        items = parser.parse(raw, strat)
        if not items:
            self.preview.configure(text="Preview: пусто")
            return

        preview = " ".join(f"[{x}]" for x in items[:3])
        if len(items) > 3:
            preview += f" +{len(items) - 3}"
        self.preview.configure(text=f"Найдено {len(items)}: {preview}")

        queue.load(items)
        queue.on_complete = self._on_done
        self._show_active(items)

    def _show_active(self, items):
        self._clear()
        self.geometry("280x180")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(10, 4))
        ctk.CTkLabel(top, text="ClipQueue", text_color=TEXT,
                     font=("", 13, "bold")).pack(side="left")
        self.prog = ctk.CTkLabel(top, text=f"0/{len(items)}",
                                  text_color=ACCENT)
        self.prog.pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, height=70,
                                                  fg_color=DIM, border_width=0)
        self.list_frame.pack(fill="x", padx=15, pady=4)
        self._refresh_list()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        self.pause_btn = ctk.CTkButton(row, text="Pause", command=self._pause,
                                        fg_color="#333", hover_color="#444",
                                        width=115)
        self.pause_btn.pack(side="left", padx=4)
        ctk.CTkButton(row, text="Reset", command=self._reset,
                      fg_color="#333", hover_color="#444",
                      width=115).pack(side="left", padx=4)

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
        if queue.active:
            self._poll()

    def _reset(self):
        queue.active = False
        self._show_input()

    def _on_done(self):
        self.after(0, lambda: self.prog.configure(
            text=f"{len(queue.items)}/{len(queue.items)}"))
        self.after(0, self._refresh_list)
