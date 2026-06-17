"""
GeoAnalyzer - Portable Street View AI Analyzer
Single-file app. Build with: pyinstaller --onefile --windowed app.py
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import time
import base64
import os
import io
from datetime import datetime
from pathlib import Path
import mss
import mss.tools
from PIL import Image, ImageTk
import openai

# ─── Theme ───────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

ACCENT    = "#3ecf8e"
BG_DARK   = "#0f0f0f"
BG_SURF   = "#1a1a1a"
BG_ELEV   = "#222222"
BORDER    = "#2a2a2a"
TEXT_SEC  = "#888888"
TEXT_MUTE = "#555555"
DANGER    = "#ef4444"
WARN      = "#f59e0b"

CONF_COLORS = {"high": ACCENT, "medium": WARN, "low": DANGER}

# ─── Data dir ────────────────────────────────────────────────────────────────
APPDATA = Path(os.environ.get("APPDATA", Path.home())) / "GeoAnalyzer"
LOGS_DIR = APPDATA / "prediction-logs"
SETTINGS_FILE = APPDATA / "settings.json"
APPDATA.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


def save_settings(data):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def save_log(entry):
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"predictions-{today}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_logs(limit=50):
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"predictions-{today}.jsonl"
    if not log_file.exists():
        return []
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    result = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            result.append(json.loads(line))
        except Exception:
            pass
        if len(result) >= limit:
            break
    return result


# ─── DPI scale helper ────────────────────────────────────────────────────────
def _get_dpi_scale():
    """Return physical/logical pixel ratio for the primary monitor."""
    try:
        with mss.mss() as sct:
            phys_w = sct.monitors[1]["width"]
        tmp = tk.Tk()
        tmp.withdraw()
        log_w = tmp.winfo_screenwidth()
        tmp.destroy()
        return phys_w / log_w if log_w > 0 else 1.0
    except Exception:
        return 1.0


# ─── Screen region selector ──────────────────────────────────────────────────
class RegionSelector:
    """Full-screen transparent overlay to draw a selection rectangle."""

    def __init__(self, callback):
        self.callback = callback
        self._dpi = _get_dpi_scale()   # e.g. 1.25 at 125% Windows scaling

        self.root = tk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.35)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="crosshair", bg="black")
        self.root.title("Select Region")

        self.canvas = tk.Canvas(self.root, bg="black", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        label = tk.Label(
            self.root,
            text="Click and drag to select the Street View area  •  ESC to cancel",
            bg="#0f0f0f", fg="#3ecf8e",
            font=("Segoe UI", 13),
            padx=16, pady=8
        )
        label.place(relx=0.5, rely=0.5, anchor="center")

        self.start_x = self.start_y = 0
        self.rect_id = None
        self.label = label

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _on_press(self, e):
        self.start_x, self.start_y = e.x, e.y
        self.label.place_forget()
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def _on_drag(self, e):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, e.x, e.y,
            outline="#3ecf8e", width=2, fill="#3ecf8e11"
        )
        # Size label
        w = abs(e.x - self.start_x)
        h = abs(e.y - self.start_y)
        self.canvas.delete("size_label")
        self.canvas.create_text(
            e.x + 10, e.y + 10,
            text=f"{w}×{h}", fill="#3ecf8e",
            font=("Consolas", 11), anchor="nw", tags="size_label"
        )

    def _on_release(self, e):
        x1, y1 = min(self.start_x, e.x), min(self.start_y, e.y)
        x2, y2 = max(self.start_x, e.x), max(self.start_y, e.y)
        w, h = x2 - x1, y2 - y1
        self.root.destroy()
        if w > 20 and h > 20:
            # Scale logical pixels → physical pixels (fixes Windows DPI scaling)
            d = self._dpi
            self.callback({
                "x": int(x1 * d),
                "y": int(y1 * d),
                "width": int(w * d),
                "height": int(h * d)
            })


# ─── OpenAI Vision ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a GeoGuessr expert. Analyze the Street View image and respond ONLY with a valid JSON object (no markdown, no code blocks) with this exact structure:
{
  "country": "string or null",
  "city": "string or null",
  "exact_location": "string or null",
  "coordinates": { "lat": number_or_null, "lng": number_or_null },
  "confidence": "high|medium|low",
  "clues": ["string", ...]
}
Focus on: road signs, language, vegetation, architecture, road markings, sun angle, license plates, driving side."""


def analyze_image(base64_img: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=400,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}",
                            "detail": "low"
                        }
                    },
                    {"type": "text", "text": "Where is this? Respond only with JSON."}
                ]
            }
        ]
    )
    text = (response.choices[0].message.content or "{}").strip()
    try:
        return json.loads(text)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return {"error": "parse_error", "raw": text}


def capture_region(region: dict) -> str:
    """Capture region and return base64 JPEG."""
    with mss.mss() as sct:
        monitor = {
            "left": region["x"],
            "top": region["y"],
            "width": region["width"],
            "height": region["height"]
        }
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        # Resize if too large
        max_w = 1280
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()


# ─── Main App Window ─────────────────────────────────────────────────────────
class GeoAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        self.region = self.settings.get("region", None)
        self.api_key = self.settings.get("api_key", "")
        self.running = False
        self._capture_thread = None
        self._stop_event = threading.Event()
        self.predictions = []

        self._build_window()
        self._build_ui()

    # ── Window setup ──────────────────────────────────────────────────────────
    def _build_window(self):
        self.title("GeoAnalyzer")
        self.geometry("420x660")
        self.minsize(380, 580)
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.configure(fg_color=BG_DARK)
        self.overrideredirect(False)
        # Keep always on top even when other windows focused
        self.bind("<FocusIn>", lambda e: self.attributes("-topmost", True))

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Title bar
        title_frame = ctk.CTkFrame(self, fg_color=BG_SURF, corner_radius=0, height=44)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame, text="🌍  GeoAnalyzer",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=ACCENT
        ).pack(side="left", padx=14)

        ctk.CTkButton(
            title_frame, text="×", width=32, height=28,
            fg_color="transparent", hover_color="#3a1515",
            text_color=TEXT_SEC, font=ctk.CTkFont(size=18),
            command=self.destroy
        ).pack(side="right", padx=6)

        ctk.CTkButton(
            title_frame, text="─", width=32, height=28,
            fg_color="transparent", hover_color=BG_ELEV,
            text_color=TEXT_SEC, font=ctk.CTkFont(size=18),
            command=self.iconify
        ).pack(side="right")

        # Error banner (hidden by default)
        self.error_var = tk.StringVar()
        self.error_frame = ctk.CTkFrame(self, fg_color="#2a1515", corner_radius=6)
        self.error_label = ctk.CTkLabel(
            self.error_frame, textvariable=self.error_var,
            text_color="#ff7070", font=ctk.CTkFont(size=12),
            wraplength=360
        )
        self.error_label.pack(side="left", padx=10, pady=6)
        ctk.CTkButton(
            self.error_frame, text="×", width=24, height=24,
            fg_color="transparent", text_color=TEXT_MUTE,
            command=self._hide_error
        ).pack(side="right", padx=6)

        # Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        ctrl_frame.pack(fill="x", padx=12, pady=(10, 0))

        btn_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_row.pack(fill="x")

        self.start_btn = ctk.CTkButton(
            btn_row, text="▶  Start", height=36,
            fg_color=ACCENT, hover_color="#2ea873",
            text_color="#000000", font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=self._toggle_capture
        )
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.region_btn = ctk.CTkButton(
            btn_row, text="🔲  Select Region", height=36,
            fg_color=BG_SURF, hover_color=BG_ELEV,
            text_color=TEXT_SEC, font=ctk.CTkFont("Segoe UI", 12),
            border_width=1, border_color=BORDER,
            command=self._open_selector
        )
        self.region_btn.pack(side="left", expand=True, fill="x")

        # Status bar
        status_frame = ctk.CTkFrame(ctrl_frame, fg_color=BG_SURF, corner_radius=6)
        status_frame.pack(fill="x", pady=(8, 0))

        self.status_dot = ctk.CTkLabel(
            status_frame, text="●", text_color=TEXT_MUTE,
            font=ctk.CTkFont(size=10), width=24
        )
        self.status_dot.pack(side="left", padx=(10, 0))

        self.status_label = ctk.CTkLabel(
            status_frame, text="Idle",
            text_color=TEXT_MUTE, font=ctk.CTkFont("Segoe UI", 12)
        )
        self.status_label.pack(side="left", padx=4)

        self.region_label = ctk.CTkLabel(
            status_frame, text="No region selected",
            text_color=TEXT_MUTE, font=ctk.CTkFont("Consolas", 10)
        )
        self.region_label.pack(side="right", padx=10)
        self._update_region_label()

        # Tabs
        self.tab_view = ctk.CTkTabview(
            self, fg_color=BG_DARK,
            segmented_button_fg_color=BG_SURF,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color="#2ea873",
            segmented_button_unselected_color=BG_SURF,
            segmented_button_unselected_hover_color=BG_ELEV,
            text_color=TEXT_SEC,
        )
        self.tab_view.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        self.tab_view.add("📍 Predict")
        self.tab_view.add("📋 Logs")
        self.tab_view.add("⚙ Settings")

        self._build_predict_tab()
        self._build_logs_tab()
        self._build_settings_tab()

    # ── Predict Tab ───────────────────────────────────────────────────────────
    def _build_predict_tab(self):
        tab = self.tab_view.tab("📍 Predict")

        self.predict_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent", corner_radius=0
        )
        self.predict_scroll.pack(fill="both", expand=True)

        self.empty_label = ctk.CTkLabel(
            self.predict_scroll,
            text="🌍\n\nSelect a region and press Start\nto begin analyzing Street View",
            text_color=TEXT_MUTE,
            font=ctk.CTkFont("Segoe UI", 13),
            justify="center"
        )
        self.empty_label.pack(pady=60)

    def _add_prediction_card(self, pred: dict, ts: str):
        r = pred

        # Remove empty label
        if self.empty_label.winfo_ismapped():
            self.empty_label.pack_forget()

        card = ctk.CTkFrame(
            self.predict_scroll,
            fg_color=BG_SURF, corner_radius=8,
            border_width=1, border_color=ACCENT if len(self.predictions) == 0 else BORDER
        )
        card.pack(fill="x", pady=(0, 8))

        if "error" in r:
            ctk.CTkLabel(
                card, text=f"⚠ Parse error\n{r.get('raw', '')[:120]}",
                text_color=DANGER, font=ctk.CTkFont(size=11),
                wraplength=340, justify="left"
            ).pack(padx=12, pady=10)
            return

        # Header row
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))

        country_text = r.get("country") or "—"
        city_text = r.get("city") or ""

        ctk.CTkLabel(
            header, text=country_text,
            font=ctk.CTkFont("Segoe UI", 17, "bold"),
            text_color="#f0f0f0"
        ).pack(side="left")

        conf = (r.get("confidence") or "").lower()
        conf_color = CONF_COLORS.get(conf, TEXT_MUTE)
        ctk.CTkLabel(
            header,
            text=f"● {conf.upper() if conf else '—'}",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=conf_color
        ).pack(side="right")

        if city_text:
            ctk.CTkLabel(
                card, text=f"📍 {city_text}",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=TEXT_SEC, anchor="w"
            ).pack(fill="x", padx=12, pady=(0, 6))

        # Exact location
        exact = r.get("exact_location")
        if exact:
            exact_frame = ctk.CTkFrame(card, fg_color=BG_ELEV, corner_radius=5)
            exact_frame.pack(fill="x", padx=12, pady=(0, 6))
            ctk.CTkLabel(
                exact_frame, text=f"🏛  {exact}",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color="#f0f0f0", anchor="w", wraplength=340
            ).pack(padx=10, pady=6, fill="x")

        # Coordinates
        coords = r.get("coordinates") or {}
        lat, lng = coords.get("lat"), coords.get("lng")
        coord_text = f"{lat:.4f}, {lng:.4f}" if lat is not None and lng is not None else "—"
        coord_frame = ctk.CTkFrame(card, fg_color=BG_ELEV, corner_radius=5)
        coord_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(
            coord_frame, text="Coordinates",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE
        ).pack(anchor="w", padx=10, pady=(6, 0))
        ctk.CTkLabel(
            coord_frame, text=coord_text,
            font=ctk.CTkFont("Consolas", 12), text_color=ACCENT
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Clues
        clues = r.get("clues") or []
        if clues:
            ctk.CTkLabel(
                card, text="Clues detected",
                font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE, anchor="w"
            ).pack(fill="x", padx=12)
            clues_frame = ctk.CTkFrame(card, fg_color="transparent")
            clues_frame.pack(fill="x", padx=10, pady=(2, 8))
            row_frame = ctk.CTkFrame(clues_frame, fg_color="transparent")
            row_frame.pack(fill="x")
            for i, clue in enumerate(clues[:6]):
                ctk.CTkLabel(
                    row_frame, text=clue,
                    font=ctk.CTkFont("Segoe UI", 11),
                    text_color=TEXT_SEC,
                    fg_color=BG_ELEV, corner_radius=999,
                    padx=8, pady=2
                ).grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="w")

        # Time
        ctk.CTkLabel(
            card, text=ts,
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE
        ).pack(anchor="e", padx=12, pady=(0, 8))

    # ── Logs Tab ──────────────────────────────────────────────────────────────
    def _build_logs_tab(self):
        tab = self.tab_view.tab("📋 Logs")

        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            btn_row, text="↻ Refresh", height=30,
            fg_color=BG_SURF, hover_color=BG_ELEV,
            text_color=TEXT_SEC, border_width=1, border_color=BORDER,
            command=self._refresh_logs
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        ctk.CTkButton(
            btn_row, text="📁 Open Folder", height=30,
            fg_color=BG_SURF, hover_color=BG_ELEV,
            text_color=TEXT_SEC, border_width=1, border_color=BORDER,
            command=lambda: os.startfile(str(LOGS_DIR))
        ).pack(side="left", expand=True, fill="x")

        self.logs_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent", corner_radius=0)
        self.logs_scroll.pack(fill="both", expand=True)

        self.logs_empty = ctk.CTkLabel(
            self.logs_scroll,
            text="📋\n\nNo logs today yet.\nStart capturing to generate predictions.",
            text_color=TEXT_MUTE, font=ctk.CTkFont("Segoe UI", 12), justify="center"
        )
        self.logs_empty.pack(pady=40)

    def _refresh_logs(self):
        for w in self.logs_scroll.winfo_children():
            w.destroy()
        logs = load_logs()
        if not logs:
            self.logs_empty = ctk.CTkLabel(
                self.logs_scroll,
                text="📋\n\nNo logs today yet.",
                text_color=TEXT_MUTE, font=ctk.CTkFont("Segoe UI", 12), justify="center"
            )
            self.logs_empty.pack(pady=40)
            return

        ctk.CTkLabel(
            self.logs_scroll,
            text=f"Last {len(logs)} predictions (today)",
            text_color=TEXT_MUTE, font=ctk.CTkFont("Segoe UI", 10)
        ).pack(anchor="w", pady=(0, 6))

        for entry in logs:
            r = entry.get("prediction", {})
            ts = entry.get("timestamp", "")
            conf = (r.get("confidence") or "").lower()
            conf_color = CONF_COLORS.get(conf, TEXT_MUTE)

            row = ctk.CTkFrame(
                self.logs_scroll, fg_color=BG_SURF,
                corner_radius=6, border_width=1, border_color=BORDER
            )
            row.pack(fill="x", pady=(0, 4))

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            name_row = ctk.CTkFrame(left, fg_color="transparent")
            name_row.pack(fill="x")
            ctk.CTkLabel(
                name_row, text="●", text_color=conf_color,
                font=ctk.CTkFont(size=9)
            ).pack(side="left")
            ctk.CTkLabel(
                name_row,
                text=f"  {r.get('country') or '—'}",
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                text_color="#f0f0f0"
            ).pack(side="left")
            if r.get("city"):
                ctk.CTkLabel(
                    name_row, text=f"  ·  {r['city']}",
                    font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT_MUTE
                ).pack(side="left")

            if r.get("exact_location"):
                ctk.CTkLabel(
                    left, text=r["exact_location"],
                    font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT_SEC, anchor="w"
                ).pack(fill="x")

            coords = r.get("coordinates") or {}
            lat, lng = coords.get("lat"), coords.get("lng")
            if lat is not None:
                ctk.CTkLabel(
                    left, text=f"{lat:.4f}, {lng:.4f}",
                    font=ctk.CTkFont("Consolas", 10), text_color=TEXT_MUTE, anchor="w"
                ).pack(fill="x")

            right = ctk.CTkFrame(row, fg_color="transparent", width=64)
            right.pack(side="right", padx=10, pady=8)
            right.pack_propagate(False)
            try:
                t = datetime.fromisoformat(ts).strftime("%H:%M:%S")
            except Exception:
                t = ts[-8:] if len(ts) >= 8 else ts
            ctk.CTkLabel(
                right, text=t,
                font=ctk.CTkFont("Consolas", 10), text_color=TEXT_MUTE
            ).pack()
            ctk.CTkLabel(
                right, text=conf.upper() if conf else "—",
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=conf_color
            ).pack()

    # ── Settings Tab ──────────────────────────────────────────────────────────
    def _build_settings_tab(self):
        tab = self.tab_view.tab("⚙ Settings")

        ctk.CTkLabel(
            tab, text="OPENAI API KEY",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE,
            anchor="w"
        ).pack(fill="x", pady=(4, 4))

        key_frame = ctk.CTkFrame(tab, fg_color="transparent")
        key_frame.pack(fill="x", pady=(0, 4))

        self.key_entry = ctk.CTkEntry(
            key_frame, placeholder_text="sk-...",
            show="●", height=36,
            fg_color=BG_SURF, border_color=BORDER,
            text_color="#f0f0f0"
        )
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        if self.api_key:
            self.key_entry.insert(0, self.api_key)

        self._show_key = False
        self.eye_btn = ctk.CTkButton(
            key_frame, text="👁", width=36, height=36,
            fg_color=BG_SURF, hover_color=BG_ELEV, border_width=1, border_color=BORDER,
            command=self._toggle_key_visibility
        )
        self.eye_btn.pack(side="left")

        ctk.CTkLabel(
            tab,
            text="Stored locally. Only sent to OpenAI's API.",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE, anchor="w"
        ).pack(fill="x", pady=(0, 10))

        self.save_key_btn = ctk.CTkButton(
            tab, text="Save API Key", height=34,
            fg_color=ACCENT, hover_color="#2ea873",
            text_color="#000000", font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=self._save_api_key
        )
        self.save_key_btn.pack(fill="x", pady=(0, 16))

        # Region info
        sep = ctk.CTkFrame(tab, fg_color=BORDER, height=1)
        sep.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            tab, text="CURRENT REGION",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE, anchor="w"
        ).pack(fill="x", pady=(0, 6))

        self.region_info = ctk.CTkFrame(tab, fg_color=BG_SURF, corner_radius=8)
        self.region_info.pack(fill="x", pady=(0, 16))
        self.region_info_label = ctk.CTkLabel(
            self.region_info, text=self._region_info_text(),
            font=ctk.CTkFont("Consolas", 11), text_color=TEXT_SEC, justify="left"
        )
        self.region_info_label.pack(padx=12, pady=10, anchor="w")

        # Specs
        sep2 = ctk.CTkFrame(tab, fg_color=BORDER, height=1)
        sep2.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            tab, text="ANALYSIS SETTINGS",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_MUTE, anchor="w"
        ).pack(fill="x", pady=(0, 6))

        specs = [
            ("Model", "gpt-4o"),
            ("Interval", "5 seconds"),
            ("Detail level", "low (faster)"),
            ("Image quality", "JPEG 85%"),
            ("Max tokens", "400"),
        ]
        spec_frame = ctk.CTkFrame(tab, fg_color=BG_SURF, corner_radius=8)
        spec_frame.pack(fill="x")
        for key, val in specs:
            row = ctk.CTkFrame(spec_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=key, font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT_MUTE).pack(side="left")
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT_SEC).pack(side="right")

    def _toggle_key_visibility(self):
        self._show_key = not self._show_key
        self.key_entry.configure(show="" if self._show_key else "●")

    def _save_api_key(self):
        key = self.key_entry.get().strip()
        if not key:
            self._show_error("Enter your OpenAI API key first.")
            return
        self.api_key = key
        self.settings["api_key"] = key
        save_settings(self.settings)
        self.save_key_btn.configure(text="✓ Saved", fg_color="#1a6b4a")
        self.after(2000, lambda: self.save_key_btn.configure(text="Save API Key", fg_color=ACCENT))

    def _region_info_text(self):
        if not self.region:
            return "No region selected."
        r = self.region
        return f"X: {r['x']}px    Y: {r['y']}px\nWidth: {r['width']}px    Height: {r['height']}px"

    # ── Capture Logic ─────────────────────────────────────────────────────────
    def _toggle_capture(self):
        if self.running:
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        if not self.api_key:
            self._show_error("Enter your OpenAI API key in ⚙ Settings first.")
            self.tab_view.set("⚙ Settings")
            return
        if not self.region:
            self._show_error("Select a screen region first.")
            return

        self.running = True
        self._stop_event.clear()
        self.start_btn.configure(text="⏹  Stop", fg_color="#2a1515", hover_color="#3a1515",
                                 text_color=DANGER, border_width=1, border_color="#5c2020")
        self.region_btn.configure(state="disabled")
        self._set_status("capturing")

        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    def _stop_capture(self):
        self.running = False
        self._stop_event.set()
        self.start_btn.configure(text="▶  Start", fg_color=ACCENT, hover_color="#2ea873",
                                 text_color="#000000", border_width=0)
        self.region_btn.configure(state="normal")
        self._set_status("idle")

    def _capture_loop(self):
        while not self._stop_event.is_set():
            self.after(0, lambda: self._set_status("analyzing"))
            try:
                b64 = capture_region(self.region)
                result = analyze_image(b64, self.api_key)
                ts = datetime.now().strftime("%H:%M:%S")
                full_ts = datetime.now().isoformat()
                entry = {"timestamp": full_ts, "prediction": result, "region": self.region}
                save_log(entry)
                self.predictions.insert(0, entry)
                self.after(0, lambda r=result, t=ts: self._on_prediction(r, t))
            except Exception as ex:
                self.after(0, lambda e=str(ex): self._show_error(f"Error: {e}"))
            if self._stop_event.is_set():
                break
            self.after(0, lambda: self._set_status("capturing"))
            self._stop_event.wait(5)

    def _on_prediction(self, result, ts):
        self._set_status("capturing")
        self.tab_view.set("📍 Predict")
        self.predictions = self.predictions[:20]
        self._add_prediction_card(result, ts)

    # ── Region Selector ───────────────────────────────────────────────────────
    def _open_selector(self):
        self.withdraw()
        self.after(200, self._launch_selector)

    def _launch_selector(self):
        def on_region_selected(r):
            self.region = r
            self.settings["region"] = r
            save_settings(self.settings)
            self.after(0, self._on_region_set)

        RegionSelector(on_region_selected)
        self.after(300, self.deiconify)

    def _on_region_set(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self._update_region_label()
        if hasattr(self, "region_info_label"):
            self.region_info_label.configure(text=self._region_info_text())

    def _update_region_label(self):
        if self.region:
            r = self.region
            self.region_label.configure(
                text=f"{r['width']}×{r['height']} @ ({r['x']},{r['y']})",
                text_color=TEXT_SEC
            )
        else:
            self.region_label.configure(text="No region selected", text_color=TEXT_MUTE)

    # ── Status / Error ────────────────────────────────────────────────────────
    STATUS_COLORS = {"idle": TEXT_MUTE, "capturing": ACCENT, "analyzing": WARN}
    STATUS_LABELS = {"idle": "Idle", "capturing": "Capturing…", "analyzing": "Analyzing…"}

    def _set_status(self, status: str):
        color = self.STATUS_COLORS.get(status, TEXT_MUTE)
        label = self.STATUS_LABELS.get(status, status)
        self.status_dot.configure(text_color=color)
        self.status_label.configure(text=label, text_color=color)

    def _show_error(self, msg: str):
        self.error_var.set(f"⚠  {msg}")
        self.error_frame.pack(fill="x", padx=12, pady=(4, 0))
        self.after(8000, self._hide_error)

    def _hide_error(self):
        self.error_frame.pack_forget()


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = GeoAnalyzerApp()
    app.mainloop()
