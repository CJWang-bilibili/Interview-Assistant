"""
gui.py
------
Floating Tkinter window for Interview Assistant.

Layout
------
┌─────────────────────────────────────────────────────┐
│  🎙 Interview Assistant                  [置顶 ✓]   │
├─────────────────────────────────────────────────────┤
│  音频设备: [设备选择 ▼]  语言:[中文▼]  [● 开始监听] │
│  状态: 就绪          音量 ████░░░░░░                 │
├─────────────────────────────────────────────────────┤
│  实时识别                                            │
│  ╔═════════════════════════════════════════════╗    │
│  ║  (转录内容实时追加显示)                      ║    │
│  ╚═════════════════════════════════════════════╝    │
│         [  🗑 删除  ]        [  📋 复制到历史  ]     │
├─────────────────────────────────────────────────────┤
│  历史对话                               [清空历史]   │
│  ╔═════════════════════════════════════════════╗    │
│  ║ [14:23] 你好，欢迎参加今天的会议…           ║    │
│  ║ [14:25] 我们来讨论一下第三季度目标…         ║    │
│  ╚═════════════════════════════════════════════╝    │
└─────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import queue
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Catppuccin Mocha palette – easy on the eyes for long sessions
# ---------------------------------------------------------------------------
C = {
    "base":     "#1e1e2e",
    "surface0": "#313244",
    "surface1": "#45475a",
    "overlay":  "#6c7086",
    "text":     "#cdd6f4",
    "subtext":  "#a6adc8",
    "blue":     "#89b4fa",
    "green":    "#a6e3a1",
    "red":      "#f38ba8",
    "yellow":   "#f9e2af",
    "peach":    "#fab387",
    "mauve":    "#cba6f7",
}


class InterviewAssistantGUI:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Interview Assistant · 面试助手")
        self.root.geometry("660x740")
        self.root.minsize(500, 560)
        self.root.configure(bg=C["base"])
        self.root.attributes("-topmost", True)

        # Public callbacks – set by main.py before calling run()
        self.on_start: Optional[Callable[[], None]] = None
        self.on_stop:  Optional[Callable[[], None]] = None

        # Internal state
        self._is_listening = False
        self._device_map: Dict[str, int] = {}
        self._update_q: queue.SimpleQueue = queue.SimpleQueue()

        self._build_style()
        self._build_ui()
        self._poll_updates()

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        for widget in ("TCombobox", "TProgressbar"):
            style.configure(
                widget,
                fieldbackground=C["surface0"],
                background=C["surface0"],
                foreground=C["text"],
                troughcolor=C["surface1"],
                bordercolor=C["surface1"],
                darkcolor=C["surface0"],
                lightcolor=C["surface0"],
            )
        style.map("TCombobox", fieldbackground=[("readonly", C["surface0"])])

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = dict(padx=14, pady=8)

        # ── Header ────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C["base"])
        hdr.pack(fill=tk.X, **pad)

        tk.Label(
            hdr, text="🎙  Interview Assistant",
            font=("Helvetica", 15, "bold"),
            bg=C["base"], fg=C["blue"],
        ).pack(side=tk.LEFT)

        self._topmost_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            hdr, text="置顶", variable=self._topmost_var,
            bg=C["base"], fg=C["subtext"], activebackground=C["base"],
            selectcolor=C["surface0"], cursor="hand2",
            command=lambda: self.root.attributes("-topmost", self._topmost_var.get()),
        ).pack(side=tk.RIGHT)

        # ── Audio controls ────────────────────────────────────────────
        af = tk.LabelFrame(
            self.root, text="  音频设置  ",
            bg=C["base"], fg=C["blue"],
            font=("Helvetica", 10, "bold"),
            bd=1, relief=tk.GROOVE,
        )
        af.pack(fill=tk.X, padx=14, pady=(0, 6))

        row1 = tk.Frame(af, bg=C["base"])
        row1.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Label(row1, text="音频设备:", bg=C["base"], fg=C["text"],
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(
            row1, textvariable=self._device_var,
            width=32, state="readonly",
        )
        self._device_combo.pack(side=tk.LEFT, padx=(6, 14))

        tk.Label(row1, text="语言:", bg=C["base"], fg=C["text"],
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        self._lang_var = tk.StringVar(value="zh")
        ttk.Combobox(
            row1, textvariable=self._lang_var,
            values=["zh", "en", "auto"],
            width=6, state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 0))

        row2 = tk.Frame(af, bg=C["base"])
        row2.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._listen_btn = tk.Button(
            row2, text="▶  开始监听",
            bg=C["green"], fg=C["base"],
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT, padx=16, pady=6,
            cursor="hand2",
            command=self._toggle_listen,
        )
        self._listen_btn.pack(side=tk.LEFT)

        tk.Label(row2, text="音量:", bg=C["base"], fg=C["subtext"],
                 font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(18, 5))
        self._vol_bar = ttk.Progressbar(row2, length=130, maximum=100)
        self._vol_bar.pack(side=tk.LEFT)

        self._status_lbl = tk.Label(
            row2, text="就绪",
            bg=C["base"], fg=C["yellow"],
            font=("Helvetica", 9),
        )
        self._status_lbl.pack(side=tk.RIGHT)

        # ── Current transcription ─────────────────────────────────────
        cf = tk.LabelFrame(
            self.root, text="  实时识别  ",
            bg=C["base"], fg=C["blue"],
            font=("Helvetica", 10, "bold"),
            bd=1, relief=tk.GROOVE,
        )
        cf.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))

        self._current_box = scrolledtext.ScrolledText(
            cf, height=7, wrap=tk.WORD,
            bg=C["surface0"], fg=C["text"],
            font=("Helvetica", 12),
            relief=tk.FLAT, padx=10, pady=10,
            insertbackground=C["text"],
            selectbackground=C["blue"], selectforeground=C["base"],
        )
        self._current_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))

        btn_row = tk.Frame(cf, bg=C["base"])
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._del_btn = tk.Button(
            btn_row, text="🗑  删除",
            bg=C["red"], fg="white",
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT, padx=20, pady=6,
            cursor="hand2",
            command=self._delete_current,
        )
        self._del_btn.pack(side=tk.LEFT)

        self._copy_btn = tk.Button(
            btn_row, text="📋  复制到历史",
            bg=C["blue"], fg=C["base"],
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT, padx=20, pady=6,
            cursor="hand2",
            command=self._copy_to_history,
        )
        self._copy_btn.pack(side=tk.RIGHT)

        # ── History ───────────────────────────────────────────────────
        hf = tk.LabelFrame(
            self.root, text="  历史对话  ",
            bg=C["base"], fg=C["blue"],
            font=("Helvetica", 10, "bold"),
            bd=1, relief=tk.GROOVE,
        )
        hf.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        hist_top = tk.Frame(hf, bg=C["base"])
        hist_top.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(hist_top, text="点击「复制到历史」后，对话自动记录在此",
                 bg=C["base"], fg=C["overlay"],
                 font=("Helvetica", 9)).pack(side=tk.LEFT)

        tk.Button(
            hist_top, text="清空历史",
            bg=C["surface1"], fg=C["subtext"],
            font=("Helvetica", 9), relief=tk.FLAT, padx=10, pady=3,
            cursor="hand2",
            command=self._clear_history,
        ).pack(side=tk.RIGHT)

        self._history_box = scrolledtext.ScrolledText(
            hf, height=7, wrap=tk.WORD,
            bg=C["surface0"], fg=C["text"],
            font=("Helvetica", 11),
            relief=tk.FLAT, padx=10, pady=10,
            state=tk.DISABLED,
            selectbackground=C["mauve"], selectforeground=C["base"],
        )
        self._history_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Text tags for history colouring
        self._history_box.tag_configure(
            "ts", foreground=C["overlay"], font=("Helvetica", 9)
        )
        self._history_box.tag_configure(
            "body", foreground=C["text"], font=("Helvetica", 11)
        )
        self._history_box.tag_configure(
            "sep", foreground=C["surface1"], font=("Helvetica", 7)
        )

    # ------------------------------------------------------------------
    # Public API (called from background threads via the update queue)
    # ------------------------------------------------------------------

    def set_devices(self, devices: List[Dict]) -> None:
        """Populate the device dropdown. Call from any thread."""
        self._update_q.put(("devices", devices))

    def set_status(self, text: str) -> None:
        self._update_q.put(("status", text))

    def set_listening(self, value: bool) -> None:
        self._update_q.put(("listening", value))

    def update_volume(self, rms: float) -> None:
        """rms: 0.0 – 1.0 raw RMS; will be scaled for display."""
        self._update_q.put(("volume", min(100.0, rms * 600)))

    def append_transcription(self, text: str) -> None:
        """Append a new recognised segment to the current text box."""
        self._update_q.put(("append", text))

    def get_selected_device_id(self) -> Optional[int]:
        return self._device_map.get(self._device_var.get())

    def get_language(self) -> str:
        return self._lang_var.get()

    # ------------------------------------------------------------------
    # Button handlers (always on main thread via Tkinter events)
    # ------------------------------------------------------------------

    def _toggle_listen(self) -> None:
        if not self._is_listening:
            if self.on_start:
                self.on_start()
        else:
            if self.on_stop:
                self.on_stop()

    def _delete_current(self) -> None:
        self._current_box.delete("1.0", tk.END)

    def _copy_to_history(self) -> None:
        text = self._current_box.get("1.0", tk.END).strip()
        if not text:
            self.set_status("⚠️ 当前没有可复制的内容")
            return

        ts = datetime.now().strftime("%H:%M:%S")

        self._history_box.configure(state=tk.NORMAL)
        # Separator between entries
        if self._history_box.get("1.0", tk.END).strip():
            self._history_box.insert(tk.END, "\n" + "─" * 55 + "\n", "sep")
        self._history_box.insert(tk.END, f"[{ts}]  ", "ts")
        self._history_box.insert(tk.END, text + "\n", "body")
        self._history_box.see(tk.END)
        self._history_box.configure(state=tk.DISABLED)

        # Also copy to system clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

        # Clear current box
        self._delete_current()
        self.set_status("✅ 已复制到历史记录（同时写入剪贴板）")

    def _clear_history(self) -> None:
        self._history_box.configure(state=tk.NORMAL)
        self._history_box.delete("1.0", tk.END)
        self._history_box.configure(state=tk.DISABLED)
        self.set_status("历史记录已清空")

    # ------------------------------------------------------------------
    # Update loop – processes messages from background threads safely
    # ------------------------------------------------------------------

    def _poll_updates(self) -> None:
        try:
            while True:
                action, value = self._update_q.get_nowait()
                self._apply(action, value)
        except Exception:
            pass
        self.root.after(40, self._poll_updates)  # ~25 fps

    def _apply(self, action: str, value) -> None:
        if action == "devices":
            self._device_map = {}
            names: List[str] = []
            for dev in value:
                if dev.get("is_vbcable"):
                    label = f"[VB-CABLE] {dev['name']}"
                elif dev["is_monitor"]:
                    label = f"[系统音频] {dev['name']}"
                else:
                    label = dev["name"]
                names.append(label)
                self._device_map[label] = dev["id"]
            self._device_combo["values"] = names
            if names:
                # Priority: VB-CABLE > other system-audio monitors > first
                preferred = next(
                    (n for n in names if n.startswith("[VB-CABLE]")),
                    next(
                        (n for n in names if n.startswith("[系统音频]")),
                        names[0],
                    ),
                )
                self._device_combo.set(preferred)

        elif action == "status":
            self._status_lbl.configure(text=value)

        elif action == "volume":
            self._vol_bar["value"] = value

        elif action == "listening":
            self._is_listening = value
            if value:
                self._listen_btn.configure(
                    text="⏹  停止监听", bg=C["red"]
                )
                self._status_lbl.configure(text="🎙 监听中…", fg=C["green"])
            else:
                self._listen_btn.configure(
                    text="▶  开始监听", bg=C["green"]
                )
                self._status_lbl.configure(text="已停止", fg=C["yellow"])

        elif action == "append":
            self._current_box.insert(tk.END, value + "\n")
            self._current_box.see(tk.END)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()
