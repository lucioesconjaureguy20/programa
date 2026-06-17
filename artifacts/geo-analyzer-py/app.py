"""
GeoAnalyzer v2 - Street View AI Analyzer
Build: pyinstaller --onefile --windowed --name GeoAnalyzer --collect-all customtkinter app.py
"""

import sys
import os
import ctypes
import tkinter as tk
import customtkinter as ctk
import threading
import json
import base64
import io
from datetime import datetime
from pathlib import Path
import mss
from PIL import Image
import openai

# ── DPI: must run before any window ──────────────────────────────────────────
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # SYSTEM_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

C_BG      = "#0d0d0d"
C_CARD    = "#161616"
C_BORDER  = "#252525"
C_ACCENT  = "#3ecf8e"
C_WARN    = "#f59e0b"
C_DANGER  = "#ef4444"
C_TEXT    = "#f0f0f0"
C_MUTED   = "#666666"
C_DIM     = "#333333"

CONF_COLOR = {"high": C_ACCENT, "medium": C_WARN, "low": C_DANGER}

# ── Storage ───────────────────────────────────────────────────────────────────
APPDATA      = Path(os.environ.get("APPDATA", Path.home())) / "GeoAnalyzer"
LOGS_DIR     = APPDATA / "logs"
SETTINGS_FILE = APPDATA / "settings.json"
APPDATA.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def settings_load() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def settings_save(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def log_write(entry: dict):
    day = datetime.now().strftime("%Y-%m-%d")
    path = LOGS_DIR / f"{day}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_read(limit: int = 60) -> list:
    day = datetime.now().strftime("%Y-%m-%d")
    path = LOGS_DIR / f"{day}.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
        if len(out) >= limit:
            break
    return out


# ── DPI scale helper ──────────────────────────────────────────────────────────
def dpi_scale() -> float:
    """Physical pixels / logical pixels for primary monitor."""
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


# ── Screen capture ────────────────────────────────────────────────────────────
def capture_region(region: dict) -> str:
    """Capture region → base64 JPEG string."""
    with mss.mss() as sct:
        raw = sct.grab({
            "left": region["x"], "top": region["y"],
            "width": region["width"], "height": region["height"]
        })
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    if img.width > 1280:
        h = int(img.height * 1280 / img.width)
        img = img.resize((1280, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


# ── OpenAI Vision ─────────────────────────────────────────────────────────────
SYSTEM = (
    "You are a GeoGuessr expert. Analyze the Street View screenshot and reply "
    "ONLY with a raw JSON object (no markdown, no backticks) in this exact shape:\n"
    '{"country":string|null,"city":string|null,"exact_location":string|null,'
    '"coordinates":{"lat":number|null,"lng":number|null},'
    '"confidence":"high"|"medium"|"low","clues":[string,...]}'
    "\nFocus on: language on signs, road markings, vegetation, architecture, "
    "sun angle, license plates, driving side."
)


def ask_openai(b64: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=400,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}},
                {"type": "text", "text": "Where is this? JSON only."}
            ]}
        ]
    )
    text = (resp.choices[0].message.content or "{}").strip()
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
        return {"error": True, "raw": text[:300]}


# ── Region Selector overlay ───────────────────────────────────────────────────
class RegionSelector:
    def __init__(self, callback, scale: float):
        self._cb    = callback
        self._scale = scale
        self._sx = self._sy = 0
        self._rect  = None

        self.root = tk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.4)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="crosshair", bg="black")

        self.canvas = tk.Canvas(self.root, bg="black",
                                cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self._hint = self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            self.root.winfo_screenheight() // 2,
            text="Arrastrá para marcar el área del Street View\n"
                 "                   ESC para cancelar",
            fill=C_ACCENT, font=("Segoe UI", 16), justify="center"
        )

        self.canvas.bind("<ButtonPress-1>",   self._press)
        self.canvas.bind("<B1-Motion>",        self._drag)
        self.canvas.bind("<ButtonRelease-1>",  self._release)
        self.root.bind("<Escape>",             lambda _: self.root.destroy())

    def _press(self, e):
        self._sx, self._sy = e.x, e.y
        self.canvas.delete(self._hint)
        if self._rect:
            self.canvas.delete(self._rect)

    def _drag(self, e):
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(
            self._sx, self._sy, e.x, e.y,
            outline=C_ACCENT, width=2, fill=""
        )
        self.canvas.delete("lbl")
        self.canvas.create_text(
            e.x + 8, e.y + 8,
            text=f"{abs(e.x - self._sx)}×{abs(e.y - self._sy)} px",
            fill=C_ACCENT, font=("Consolas", 11),
            anchor="nw", tags="lbl"
        )

    def _release(self, e):
        x1 = min(self._sx, e.x);  y1 = min(self._sy, e.y)
        x2 = max(self._sx, e.x);  y2 = max(self._sy, e.y)
        w, h = x2 - x1, y2 - y1
        self.root.destroy()
        if w >= 30 and h >= 30:
            d = self._scale
            self._cb({"x": int(x1*d), "y": int(y1*d),
                       "width": int(w*d), "height": int(h*d)})


# ── Shared UI helpers ─────────────────────────────────────────────────────────
def card(parent, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10,
                        border_width=1, border_color=C_BORDER, **kw)


def label(parent, text, size=13, weight="normal", color=C_TEXT, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text,
                        font=ctk.CTkFont("Segoe UI", size, weight),
                        text_color=color, **kw)


def btn(parent, text, cmd, fg=C_CARD, tc=C_TEXT,
        h=36, size=13, weight="normal", border=C_BORDER, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=cmd,
                         height=h, fg_color=fg, hover_color="#1e1e1e",
                         text_color=tc, border_width=1, border_color=border,
                         font=ctk.CTkFont("Segoe UI", size, weight), **kw)


# ═════════════════════════════════════════════════════════════════════════════
#  Main App
# ═════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._cfg     = settings_load()
        self._region  = self._cfg.get("region")
        self._apikey  = (self._cfg.get("api_key")
                         or os.environ.get("OPENAI_API_KEY", ""))
        self._running = False
        self._stop    = threading.Event()
        self._scale   = dpi_scale()

        # ── Window ──────────────────────────────────────────────────────────
        self.title("GeoAnalyzer")
        self.geometry("400x660")
        self.minsize(380, 560)
        self.resizable(True, True)
        self.configure(fg_color=C_BG)
        self.attributes("-topmost", True)
        self.bind("<FocusIn>", lambda _: self.attributes("-topmost", True))

        self._build()

    # ── Build UI ─────────────────────────────────────────────────────────────
    def _build(self):
        # Title bar
        bar = ctk.CTkFrame(self, fg_color="#111111", corner_radius=0, height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        bar.configure(cursor="fleur")
        bar.bind("<ButtonPress-1>",   self._drag_start)
        bar.bind("<B1-Motion>",        self._drag_move)

        label(bar, "🌍  GeoAnalyzer", 14, "bold", C_ACCENT).pack(side="left", padx=14)

        for sym, cmd in [("─", self.iconify), ("✕", self.destroy)]:
            b = ctk.CTkButton(bar, text=sym, width=34, height=34,
                              fg_color="transparent",
                              hover_color="#2a1515" if sym == "✕" else "#222",
                              text_color=C_MUTED,
                              font=ctk.CTkFont("Segoe UI", 16),
                              command=cmd, cursor="arrow")
            b.pack(side="right", padx=3)

        # Setup banner (only when missing key or region)
        self._setup_banner = ctk.CTkFrame(self, fg_color="#0e1f17",
                                          corner_radius=0, border_width=0)
        self._setup_inner = ctk.CTkFrame(self._setup_banner,
                                         fg_color="transparent")
        self._setup_inner.pack(fill="x", padx=14, pady=8)
        self._setup_label = label(self._setup_inner, "", 12, color="#aaa",
                                  anchor="w", wraplength=340, justify="left")
        self._setup_label.pack(fill="x")

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=12, pady=(10, 0))

        row1 = ctk.CTkFrame(ctrl, fg_color="transparent")
        row1.pack(fill="x")

        self._start_btn = ctk.CTkButton(
            row1, text="▶   Start", height=42,
            fg_color=C_ACCENT, hover_color="#2ea873",
            text_color="#000", font=ctk.CTkFont("Segoe UI", 14, "bold"),
            command=self._toggle, border_width=0
        )
        self._start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._region_btn = ctk.CTkButton(
            row1, text="🔲  Zona", height=42,
            fg_color=C_CARD, hover_color="#1e1e1e",
            text_color=C_TEXT, font=ctk.CTkFont("Segoe UI", 13),
            border_width=1, border_color=C_BORDER,
            command=self._pick_region
        )
        self._region_btn.pack(side="left", expand=True, fill="x")

        # Status strip
        status_row = ctk.CTkFrame(ctrl, fg_color="#111", corner_radius=8,
                                  border_width=1, border_color=C_BORDER)
        status_row.pack(fill="x", pady=(8, 0))

        self._dot   = label(status_row, "●", 10, color=C_MUTED, width=22)
        self._dot.pack(side="left", padx=(8, 0))
        self._status = label(status_row, "Listo", 12, color=C_MUTED)
        self._status.pack(side="left", padx=4)
        self._region_lbl = label(status_row, "Sin zona", 10, color=C_MUTED)
        self._region_lbl.pack(side="right", padx=10)
        self._refresh_region_lbl()

        # Error banner
        self._err_frame = ctk.CTkFrame(self, fg_color="#1a0a0a",
                                       corner_radius=0, border_width=0)
        self._err_lbl   = label(self._err_frame, "", 12, color="#ff7070",
                                wraplength=350, justify="left")
        self._err_lbl.pack(side="left", padx=12, pady=6)
        ctk.CTkButton(self._err_frame, text="✕", width=28, height=28,
                      fg_color="transparent", text_color=C_MUTED,
                      command=self._hide_err).pack(side="right", padx=6)

        # Tabs
        self._tabs = ctk.CTkTabview(
            self, fg_color=C_BG,
            segmented_button_fg_color="#111",
            segmented_button_selected_color=C_ACCENT,
            segmented_button_selected_hover_color="#2ea873",
            segmented_button_unselected_color="#111",
            segmented_button_unselected_hover_color="#1a1a1a",
            text_color=C_MUTED,
        )
        self._tabs.pack(fill="both", expand=True, padx=10, pady=(8, 10))
        self._tabs.add("Resultado")
        self._tabs.add("Historial")
        self._tabs.add("Config")

        self._build_result_tab()
        self._build_history_tab()
        self._build_config_tab()
        self._refresh_setup_banner()

    # ── Drag ─────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx, self._dy = e.x, e.y

    def _drag_move(self, e):
        x = self.winfo_x() + e.x - self._dx
        y = self.winfo_y() + e.y - self._dy
        self.geometry(f"+{x}+{y}")

    # ── Setup banner ──────────────────────────────────────────────────────────
    def _refresh_setup_banner(self):
        missing = []
        if not self._apikey:
            missing.append("API Key de OpenAI")
        if not self._region:
            missing.append("zona de pantalla")

        if missing:
            msg = "⚡ Para empezar configurá: " + " y ".join(missing)
            if not self._apikey:
                msg += "\n→ Pestaña Config → pegá tu API key (empieza con sk-...)"
            if not self._region:
                msg += "\n→ Botón 🔲 Zona → arrastrá sobre el Street View"
            self._setup_label.configure(text=msg)
            self._setup_banner.pack(fill="x", after=self._start_btn.master.master)
        else:
            self._setup_banner.pack_forget()

    # ── Result tab ────────────────────────────────────────────────────────────
    def _build_result_tab(self):
        tab = self._tabs.tab("Resultado")
        self._result_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent", corner_radius=0)
        self._result_scroll.pack(fill="both", expand=True)

        self._empty = label(
            self._result_scroll,
            "🌍\n\nSeleccioná una zona y\npresioná Start para empezar",
            14, color=C_MUTED, justify="center"
        )
        self._empty.pack(pady=50)

    def show_result(self, r: dict, ts: str):
        if self._empty.winfo_ismapped():
            self._empty.pack_forget()

        c = card(self._result_scroll)
        c.pack(fill="x", pady=(0, 8))

        if r.get("error"):
            label(c, f"⚠ Error al parsear\n{r.get('raw', '')[:200]}",
                  11, color=C_DANGER, wraplength=340, justify="left").pack(
                padx=12, pady=10)
            return

        # ── Country + confidence ────────────────────────────────────────────
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 4))

        country = r.get("country") or "Desconocido"
        conf    = (r.get("confidence") or "").lower()
        label(top, country, 20, "bold").pack(side="left")
        cc = CONF_COLOR.get(conf, C_MUTED)
        label(top, f"● {conf.upper() or '—'}", 11, "bold", cc).pack(
            side="right", padx=4)

        if r.get("city"):
            label(c, f"📍  {r['city']}", 12, color="#aaa",
                  anchor="w").pack(fill="x", padx=14, pady=(0, 6))

        # ── Exact location ──────────────────────────────────────────────────
        if r.get("exact_location"):
            el = ctk.CTkFrame(c, fg_color="#0e1f17", corner_radius=6)
            el.pack(fill="x", padx=14, pady=(0, 6))
            label(el, f"🏛  {r['exact_location']}", 12,
                  wraplength=330, justify="left", anchor="w").pack(
                padx=10, pady=7, fill="x")

        # ── Coords ──────────────────────────────────────────────────────────
        coords = r.get("coordinates") or {}
        lat, lng = coords.get("lat"), coords.get("lng")
        coord_txt = (f"{lat:.5f},  {lng:.5f}" if lat is not None
                     else "Coordenadas no disponibles")
        cf = ctk.CTkFrame(c, fg_color=C_DIM, corner_radius=6)
        cf.pack(fill="x", padx=14, pady=(0, 6))
        label(cf, "Coordenadas", 10, color=C_MUTED, anchor="w").pack(
            padx=10, pady=(6, 0), fill="x")
        label(cf, coord_txt, 12, color=C_ACCENT,
              font=ctk.CTkFont("Consolas", 12), anchor="w").pack(
            padx=10, pady=(0, 6), fill="x")

        # ── Clues ───────────────────────────────────────────────────────────
        clues = r.get("clues") or []
        if clues:
            label(c, "Pistas detectadas", 10, color=C_MUTED,
                  anchor="w").pack(fill="x", padx=14)
            cbox = ctk.CTkFrame(c, fg_color="transparent")
            cbox.pack(fill="x", padx=10, pady=(2, 8))
            for i, cl in enumerate(clues[:8]):
                lbl = ctk.CTkLabel(
                    cbox, text=cl,
                    font=ctk.CTkFont("Segoe UI", 11),
                    text_color="#aaa", fg_color=C_DIM,
                    corner_radius=999, padx=8, pady=2
                )
                lbl.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="w")

        label(c, ts, 10, color=C_MUTED).pack(
            anchor="e", padx=14, pady=(0, 8))

    # ── History tab ───────────────────────────────────────────────────────────
    def _build_history_tab(self):
        tab = self._tabs.tab("Historial")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))

        for txt, cmd in [("↻  Actualizar", self._load_history),
                         ("📁  Abrir carpeta", lambda: os.startfile(str(LOGS_DIR)))]:
            ctk.CTkButton(
                top, text=txt, height=32,
                fg_color=C_CARD, hover_color="#1e1e1e",
                text_color="#aaa", border_width=1, border_color=C_BORDER,
                font=ctk.CTkFont("Segoe UI", 12), command=cmd
            ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        self._hist_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent", corner_radius=0)
        self._hist_scroll.pack(fill="both", expand=True)
        self._hist_empty = label(self._hist_scroll,
                                 "Sin historial hoy todavía",
                                 12, color=C_MUTED, justify="center")
        self._hist_empty.pack(pady=40)

    def _load_history(self):
        for w in self._hist_scroll.winfo_children():
            w.destroy()
        entries = log_read()
        if not entries:
            label(self._hist_scroll, "Sin historial hoy todavía",
                  12, color=C_MUTED, justify="center").pack(pady=40)
            return

        label(self._hist_scroll,
              f"Últimas {len(entries)} predicciones de hoy",
              10, color=C_MUTED, anchor="w").pack(fill="x", pady=(0, 6))

        for e in entries:
            r  = e.get("prediction", {})
            ts = e.get("timestamp", "")
            conf = (r.get("confidence") or "").lower()
            cc   = CONF_COLOR.get(conf, C_MUTED)

            row = card(self._hist_scroll)
            row.pack(fill="x", pady=(0, 4))

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            top_row = ctk.CTkFrame(left, fg_color="transparent")
            top_row.pack(fill="x")
            label(top_row, "●", 9, color=cc).pack(side="left")
            label(top_row, f"  {r.get('country') or '—'}",
                  13, "bold").pack(side="left")
            if r.get("city"):
                label(top_row, f"  ·  {r['city']}",
                      11, color=C_MUTED).pack(side="left")

            if r.get("exact_location"):
                label(left, r["exact_location"], 11, color="#aaa",
                      anchor="w").pack(fill="x")

            coords = r.get("coordinates") or {}
            lat, lng = coords.get("lat"), coords.get("lng")
            if lat is not None:
                label(left, f"{lat:.4f}, {lng:.4f}",
                      10, color=C_MUTED,
                      font=ctk.CTkFont("Consolas", 10),
                      anchor="w").pack(fill="x")

            right = ctk.CTkFrame(row, fg_color="transparent", width=70)
            right.pack(side="right", padx=10, pady=8)
            right.pack_propagate(False)
            try:
                t = datetime.fromisoformat(ts).strftime("%H:%M:%S")
            except Exception:
                t = ts[-8:] if len(ts) >= 8 else ts
            label(right, t, 10, color=C_MUTED).pack()
            label(right, conf.upper() or "—", 10, "bold", cc).pack()

    # ── Config tab ────────────────────────────────────────────────────────────
    def _build_config_tab(self):
        tab = self._tabs.tab("Config")
        tab.configure()

        # ── API Key ──────────────────────────────────────────────────────────
        c1 = card(tab)
        c1.pack(fill="x", pady=(0, 10))

        label(c1, "API Key de OpenAI", 12, "bold", anchor="w").pack(
            fill="x", padx=14, pady=(12, 4))
        label(c1,
              "Pegá tu clave que empieza con sk-...\n"
              "(la encontrás en platform.openai.com → API Keys)",
              11, color=C_MUTED, anchor="w", justify="left",
              wraplength=340).pack(fill="x", padx=14, pady=(0, 8))

        key_row = ctk.CTkFrame(c1, fg_color="transparent")
        key_row.pack(fill="x", padx=14, pady=(0, 6))

        self._key_entry = ctk.CTkEntry(
            key_row, show="●", placeholder_text="sk-...",
            height=36, fg_color="#111", border_color=C_BORDER,
            text_color=C_TEXT, font=ctk.CTkFont("Consolas", 12)
        )
        self._key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        if self._apikey:
            self._key_entry.insert(0, self._apikey)

        self._eye = ctk.CTkButton(
            key_row, text="👁", width=36, height=36,
            fg_color="#111", hover_color=C_DIM,
            border_width=1, border_color=C_BORDER,
            command=self._toggle_eye
        )
        self._eye.pack(side="left")
        self._show_key = False

        self._save_btn = ctk.CTkButton(
            c1, text="Guardar API Key", height=36,
            fg_color=C_ACCENT, hover_color="#2ea873",
            text_color="#000", font=ctk.CTkFont("Segoe UI", 13, "bold"),
            border_width=0, command=self._save_key
        )
        self._save_btn.pack(fill="x", padx=14, pady=(0, 12))

        # ── Region ───────────────────────────────────────────────────────────
        c2 = card(tab)
        c2.pack(fill="x", pady=(0, 10))

        label(c2, "Zona de captura", 12, "bold", anchor="w").pack(
            fill="x", padx=14, pady=(12, 4))
        label(c2,
              "Seleccioná el área donde está el Street View.",
              11, color=C_MUTED, anchor="w").pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkButton(
            c2, text="🔲  Seleccionar zona", height=36,
            fg_color=C_CARD, hover_color="#1e1e1e",
            text_color=C_TEXT, border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 13), command=self._pick_region
        ).pack(fill="x", padx=14, pady=(0, 8))

        self._region_info = label(c2, self._region_text(),
                                  11, color=C_MUTED, anchor="w")
        self._region_info.pack(fill="x", padx=14, pady=(0, 12))

        # ── Info ─────────────────────────────────────────────────────────────
        c3 = card(tab)
        c3.pack(fill="x")

        label(c3, "Configuración del análisis", 12, "bold",
              anchor="w").pack(fill="x", padx=14, pady=(12, 6))
        for k, v in [("Modelo", "gpt-4o"),
                     ("Intervalo", "5 segundos"),
                     ("Detalle imagen", "low (más rápido)"),
                     ("Calidad JPEG", "82%"),
                     ("Logs", str(LOGS_DIR))]:
            row = ctk.CTkFrame(c3, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=1)
            label(row, k, 11, color=C_MUTED).pack(side="left")
            label(row, v, 11, color="#aaa").pack(side="right")
        ctk.CTkFrame(c3, fg_color="transparent", height=8).pack()

    def _toggle_eye(self):
        self._show_key = not self._show_key
        self._key_entry.configure(show="" if self._show_key else "●")

    def _save_key(self):
        k = self._key_entry.get().strip()
        if not k.startswith("sk-"):
            self._show_err("La API key debe empezar con sk-")
            return
        self._apikey = k
        self._cfg["api_key"] = k
        settings_save(self._cfg)
        self._save_btn.configure(text="✓ Guardado", fg_color="#1a5c3a")
        self.after(2500, lambda: self._save_btn.configure(
            text="Guardar API Key", fg_color=C_ACCENT))
        self._refresh_setup_banner()

    def _region_text(self):
        if not self._region:
            return "Ninguna zona seleccionada"
        r = self._region
        return f"{r['width']}×{r['height']} px  —  posición ({r['x']}, {r['y']})"

    # ── Region picker ─────────────────────────────────────────────────────────
    def _pick_region(self):
        self.withdraw()
        self.after(200, self._open_selector)

    def _open_selector(self):
        def on_done(region):
            self._region = region
            self._cfg["region"] = region
            settings_save(self._cfg)
            self.after(0, self._on_region_set)

        RegionSelector(on_done, self._scale)
        self.after(300, self.deiconify)

    def _on_region_set(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self._refresh_region_lbl()
        self._refresh_setup_banner()
        if hasattr(self, "_region_info"):
            self._region_info.configure(text=self._region_text())

    def _refresh_region_lbl(self):
        if self._region:
            r = self._region
            self._region_lbl.configure(
                text=f"{r['width']}×{r['height']} @ ({r['x']},{r['y']})",
                text_color="#aaa")
        else:
            self._region_lbl.configure(
                text="Sin zona", text_color=C_MUTED)

    # ── Capture loop ──────────────────────────────────────────────────────────
    def _toggle(self):
        if self._running:
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        if not self._apikey:
            self._show_err("Configurá tu API Key primero (pestaña Config)")
            self._tabs.set("Config")
            return
        if not self._region:
            self._show_err("Seleccioná una zona primero (botón 🔲 Zona)")
            return
        self._running = True
        self._stop.clear()
        self._start_btn.configure(
            text="⏹   Stop", fg_color="#2a1515",
            hover_color="#3a1515", text_color=C_DANGER,
            border_width=1, border_color="#5c2020"
        )
        self._region_btn.configure(state="disabled")
        self._set_status("capturing")
        threading.Thread(target=self._loop, daemon=True).start()

    def _stop_capture(self):
        self._running = False
        self._stop.set()
        self._start_btn.configure(
            text="▶   Start", fg_color=C_ACCENT,
            hover_color="#2ea873", text_color="#000", border_width=0
        )
        self._region_btn.configure(state="normal")
        self._set_status("idle")

    def _loop(self):
        while not self._stop.is_set():
            self.after(0, lambda: self._set_status("analyzing"))
            try:
                b64 = capture_region(self._region)
                result = ask_openai(b64, self._apikey)
                ts = datetime.now().strftime("%H:%M:%S")
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "prediction": result,
                    "region": self._region
                }
                log_write(entry)
                self.after(0, lambda r=result, t=ts: self._on_result(r, t))
            except openai.AuthenticationError:
                self.after(0, lambda: self._show_err(
                    "API Key inválida. Verificá que sea correcta en Config."))
                self.after(0, self._stop_capture)
                return
            except Exception as ex:
                self.after(0, lambda e=str(ex): self._show_err(f"Error: {e}"))
            if self._stop.is_set():
                break
            self.after(0, lambda: self._set_status("capturing"))
            self._stop.wait(5)

    def _on_result(self, result, ts):
        self._set_status("capturing")
        self._tabs.set("Resultado")
        self.show_result(result, ts)

    # ── Status ────────────────────────────────────────────────────────────────
    _STATUS = {
        "idle":      (C_MUTED,  "Listo"),
        "capturing": (C_ACCENT, "Capturando…"),
        "analyzing": (C_WARN,   "Analizando…"),
    }

    def _set_status(self, key: str):
        color, text = self._STATUS.get(key, (C_MUTED, key))
        self._dot.configure(text_color=color)
        self._status.configure(text=text, text_color=color)

    # ── Error banner ──────────────────────────────────────────────────────────
    def _show_err(self, msg: str):
        self._err_lbl.configure(text=f"⚠  {msg}")
        self._err_frame.pack(fill="x")
        self.after(8000, self._hide_err)

    def _hide_err(self):
        self._err_frame.pack_forget()


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()
