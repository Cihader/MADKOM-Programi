# ─────────────────────────── Timeline-canvas ───────────────────────────

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from datetime import datetime, timedelta

# ─────────────────────────── Renkler & Sabitler ───────────────────────────

BG_DARK       = "#ffffff"
BG_MID        = "#f6f8fa"
BG_PANEL      = "#f0f2f5"
BORDER        = "#d0d7de"
TEXT_PRIMARY  = "#24292f"
TEXT_MUTED    = "#6a737d"
ACCENT        = "#0969da"

LAYER_CFG = {
    "ruzgar":  {"label": "🧭  RÜZGAR",   "color": "#0969da", "text": "#000000"},
    "gorus":   {"label": "👁  GÖRÜŞ",    "color": "#0969da", "text": "#000000"},
    "hadise":  {"label": "⛈  HADİSE",   "color": "#0969da", "text": "#ffffff"},
    "oraj":    {"label": "⚡  ORAJ/TS",  "color": "#0969da", "text": "#ffffff"},
    "bulut":   {"label": "☁  BULUT",    "color": "#0969da", "text": "#ffffff"},
}

LAYER_KEYS = ["ruzgar", "gorus", "hadise", "oraj", "bulut"]

# Saat ekseni: ayarlanabilir (maks 48 saat), ayarlanabilir başlangıç saati
HOURS_SHOWN  = 40       # varsayılan gösterilen saat sayısı (kullanıcı değiştirebilir)
HOURS_MAX    = 48       # maksimum izin verilen saat
START_HOUR   = 0        # varsayılan başlangıç saati (0-23 arası tam saat)
TRACK_H     = 44        # piksel yükseklik / katman
LABEL_W     = 110       # sol etiket genişliği
MIN_BLOCK_H = 0.25      # minimum blok süresi (saat)


# ─────────────────────────── Blok Veri Sınıfı ────────────────────────────

class Block:
    _id = 0

    def __init__(self, layer, start, end):
        Block._id += 1
        self.id     = Block._id
        self.layer  = layer
        self.start  = round(start)   # tam saat hassasiyet
        self.end    = round(end)
        self.striped       = False
        self.dashed_border = False   # kesik kenarlı / aralıklı blok
        self.fields  = {}
        self.color      = None   # None → katman varsayılan rengi kullan
        self.text_color = "#ffffff"   # None → katman varsayılan metin rengi kullan
        self.label_align = "center"  # "left" | "center" | "right"

    def label(self):
        return self.fields.get("etiket", "")

    def to_dict(self):
        return {
            "id": self.id, "layer": self.layer,
            "start": self.start, "end": self.end,
            "striped": self.striped, "dashed_border": self.dashed_border,
            "fields": self.fields,
            "color": self.color, "text_color": self.text_color,
            "label_align": self.label_align
        }

    @staticmethod
    def from_dict(d):
        b = Block(d["layer"], d["start"], d["end"])
        b.id           = d["id"]
        b.striped      = d.get("striped", False)
        b.dashed_border = d.get("dashed_border", False)
        b.fields       = d.get("fields", {})
        b.color        = d.get("color", None)
        b.text_color   = d.get("text_color", "#ffffff")
        b.label_align  = d.get("label_align", "center")
        return b


# ──────────────────────────── Zaman Çizelgesi ────────────────────────────

class TimelineCanvas(tk.Canvas):
    """Sürükle-bırak blok çizelgesi."""

    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=BG_DARK, highlightthickness=0, **kw)
        self.app      = app
        self.blocks   = []
        self.start_hour  = START_HOUR   # çizelge başlangıç saati (tam saat, 0-23)
        self.hours_shown = HOURS_SHOWN  # gösterilen saat sayısı (ayarlanabilir)
        self._sel     = None        # seçili blok id
        self._drag    = None        # {"id", "ox", "os", "oe"}
        self._resize  = None        # {"id", "ox", "oe"}
        self._draw    = None        # {"layer", "sx", "cx"}
        self._hover   = None

        self.bind("<Configure>",     self._on_resize)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>",     self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>",        self._on_hover)
        self.bind("<Leave>",         lambda e: self._set_cursor("arrow"))

    # ── boyut & koordinat ──────────────────────────────────────────────

    def _track_w(self):
        return max(100, self.winfo_width() - LABEL_W - 12)

    def _layer_y(self, idx):
        return idx * (TRACK_H + 6)
    
    def _time_axis_y(self):
        return len(LAYER_KEYS) * (TRACK_H + 6)

    def _layer_at(self, y):
        for i, k in enumerate(LAYER_KEYS):
            ty = self._layer_y(i)
            if ty <= y <= ty + TRACK_H:
                return k, i
        return None, None

    def _x_to_h(self, x):
        x = max(0, min(self._track_w(), x - LABEL_W))
        return round((x / self._track_w()) * self.hours_shown)  # tam saat snap

    def _h_to_x(self, h):
        return LABEL_W + (h / self.hours_shown) * self._track_w()

    def _block_rect(self, b):
        x1 = self._h_to_x(b.start)
        x2 = self._h_to_x(b.end)
        return x1, x2

    # ── render ────────────────────────────────────────────────────────

    def redraw(self):
        self.delete("all")
        for i, k in enumerate(LAYER_KEYS):
            self._draw_track(i, k)
        for b in self.blocks:
            self._draw_block(b)
        if self._draw:
            self._draw_preview()
        self._draw_time_axis()
        # Analiz metnini otomatik güncelle
        if hasattr(self.app, 'refresh_analiz'):
            self.app.refresh_analiz()

    def _draw_time_axis(self):
        w = self._track_w()
        y = self._time_axis_y()
        self.create_rectangle(0, y, LABEL_W - 4, y + 18,
                              fill=BG_MID, outline=BORDER, width=1)
        self.create_text(LABEL_W // 2, y + 9,
                         text="Periyot", fill=TEXT_MUTED,
                         font=("Arial", 8, "bold"), anchor="center")
        cell_w = w / self.hours_shown
        # Başlangıç tarihi (bugün UTC)
        base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt  = base_date + timedelta(hours=self.start_hour)
        for h in range(self.hours_shown + 1):
            abs_hour = (self.start_hour + h) % 24
            x = LABEL_W + h * cell_w
            is_midnight = (abs_hour == 0 and h > 0)
            line_color = "#cc0000" if is_midnight else BORDER
            line_width = 2 if is_midnight else 1
            self.create_line(x, y, x, y + 18, fill=line_color, width=line_width)
            if h < self.hours_shown:
                lbl = f"{abs_hour:02d}Z"
                if is_midnight:
                    cur_dt = start_dt + timedelta(hours=h)
                    day_lbl = f"{cur_dt.day:02d}"
                    self.create_rectangle(x, y, x + cell_w, y + 18,
                                          fill="#fff0f0", outline="")
                    self.create_text(x + cell_w / 2, y + 5,
                                     text=day_lbl, fill="#cc0000",
                                     font=("Arial", 6, "bold"), anchor="center")
                    self.create_text(x + cell_w / 2, y + 13,
                                     text=lbl, fill="#cc0000",
                                     font=("Courier", 7, "bold"), anchor="center")
                else:
                    self.create_text(x + cell_w / 2, y + 9,
                                     text=lbl, fill=TEXT_MUTED,
                                     font=("Courier", 8), anchor="center")

    def _draw_track(self, idx, key):
        y = self._layer_y(idx)
        cfg = LAYER_CFG[key]
        cell_w = self._track_w() / self.hours_shown
        # etiket
        self.create_rectangle(0, y, LABEL_W - 4, y + TRACK_H,
                               fill=BG_MID, outline=BORDER, width=1)
        self.create_text(LABEL_W // 2, y + TRACK_H // 2,
                         text=cfg["label"], fill=TEXT_PRIMARY,
                         font=("Arial", 9, "bold"), anchor="center")
        # iz arka plan (çizgisiz, düz)
        self.create_rectangle(LABEL_W, y, LABEL_W + self._track_w(), y + TRACK_H,
                               fill=BG_MID, outline=BORDER, width=1,
                               tags=(f"track_{key}",))
        # sadece gün değişimi kırmızı çizgisi (saat kılavuz çizgileri kaldırıldı)
        for h in range(self.hours_shown + 1):
            abs_hour = (self.start_hour + h) % 24
            x = LABEL_W + h * cell_w
            is_midnight = (abs_hour == 0 and h > 0)
            if is_midnight:
                self.create_line(x, y, x, y + TRACK_H, fill="#cc0000", width=2)

    def _draw_block(self, b):
        cfg  = LAYER_CFG[b.layer]
        idx  = LAYER_KEYS.index(b.layer)
        y    = self._layer_y(idx)
        x1, x2 = self._block_rect(b)
        pad  = 3
        is_sel = (b.id == self._sel)

        fill = b.color if b.color else cfg["color"]
        outline = "#000000" if is_sel else cfg["color"]
        width   = 2 if is_sel else 1

        if b.striped:
            # Taralı blok: önce zemin sonra çizgiler
            self.create_rectangle(x1, y+pad, x2, y+TRACK_H-pad,
                                   fill=fill, outline=outline, width=width,
                                   tags=(f"block_{b.id}",))
            stripe_w = 8
            for sx in range(int(x1), int(x2) + stripe_w * 2, stripe_w):
                self.create_line(sx, y+pad, sx - TRACK_H, y+TRACK_H-pad,
                                 fill="#d0d7de", width=1,
                                 tags=(f"block_{b.id}",))
                self.create_rectangle(0, y+pad, x1, y+TRACK_H-pad,
                                       fill=BG_MID, outline="", width=0,
                                       tags=(f"block_{b.id}_clip",))
                self.create_rectangle(x2, y+pad, LABEL_W+self._track_w(), y+TRACK_H-pad,
                                       fill=BG_MID, outline="", width=0,
                                       tags=(f"block_{b.id}_clip",))
        else:
            self.create_rectangle(x1, y+pad, x2, y+TRACK_H-pad,
                                   fill=fill, outline=outline, width=width,
                                   tags=(f"block_{b.id}",))

        # Kesik kenarlı (dashed_border): üzerine kesik çizgi dikdörtgeni çiz
        if b.dashed_border:
            dash_outline = "#ffffff" if is_sel else "#000000"
            dash_width   = 2
            # Tkinter'da canvas rectangle dash desteği yok; çizgilerle simüle et
            for side, coords in [
                ("top",    (x1, y+pad, x2, y+pad)),
                ("bottom", (x1, y+TRACK_H-pad, x2, y+TRACK_H-pad)),
                ("left",   (x1, y+pad, x1, y+TRACK_H-pad)),
                ("right",  (x2, y+pad, x2, y+TRACK_H-pad)),
            ]:
                self.create_line(*coords, fill=dash_outline, width=dash_width,
                                 dash=(6, 4), tags=(f"block_{b.id}",))

        # Etiket
        lbl = b.label()
        txt_color = b.text_color if b.text_color else cfg["text"]
        visible_w = x2 - x1
        if visible_w > 30:
            align = getattr(b, "label_align", "center")
            if align == "left":
                tx     = x1 + 6
                anchor = "w"
                tw     = max(1, int(visible_w - 12))
            elif align == "right":
                tx     = x2 - 6
                anchor = "e"
                tw     = max(1, int(visible_w - 12))
            else:  # center
                tx     = (x1 + x2) / 2
                anchor = "center"
                tw     = max(1, int(visible_w - 8))
            self.create_text(tx, y + TRACK_H // 2,
                             text=lbl, fill=txt_color,
                             font=("Courier", 9, "bold"), anchor=anchor,
                             width=tw,
                             tags=(f"block_{b.id}",))

        # yeniden boyutlandırma tutacağı
        handle_x = x2 - 6
        self.create_rectangle(handle_x, y+pad+2, x2-1, y+TRACK_H-pad-2,
                               fill="#6a737d", outline="", width=0,
                               tags=(f"resize_{b.id}",))

    def _draw_preview(self):
        d = self._draw
        idx = LAYER_KEYS.index(d["layer"])
        y = self._layer_y(idx)
        x1 = min(d["sx"], d["cx"])
        x2 = max(d["sx"], d["cx"])
        if x2 - x1 < 4:
            return
        pad = 3
        self.create_rectangle(x1, y+pad, x2, y+TRACK_H-pad,
                               fill="#e1f0ff", outline="#0969da",
                               width=1, stipple="gray50")

    # ── etkinlikler ───────────────────────────────────────────────────

    def _block_at(self, x, y):
        """(x,y) noktasındaki bloğu ve bölgeyi döndür: (block, 'resize'|'move'|None)"""
        for b in reversed(self.blocks):
            idx = LAYER_KEYS.index(b.layer)
            ty  = self._layer_y(idx)
            if not (ty <= y <= ty + TRACK_H):
                continue
            x1, x2 = self._block_rect(b)
            if x1 <= x <= x2:
                zone = "resize" if x >= x2 - 8 else "move"
                return b, zone
        return None, None

    def _on_press(self, e):
        b, zone = self._block_at(e.x, e.y)
        if b:
            self._sel = b.id
            if zone == "resize":
                self._resize = {"id": b.id, "ox": e.x, "oe": b.end}
            else:
                self._drag = {"id": b.id, "ox": e.x,
                              "os": b.start, "oe": b.end}
            self.app.open_editor(b)
            self.redraw()
            return

        layer, _ = self._layer_at(e.y)
        if layer:
            self._sel   = None
            self._draw  = {"layer": layer, "sx": e.x, "cx": e.x}
            self.app.close_editor()
            self.redraw()

    def _on_motion(self, e):
        if self._resize:
            b  = self._block_by_id(self._resize["id"])
            dx = e.x - self._resize["ox"]
            dh = (dx / self._track_w()) * self.hours_shown
            new_end = round(self._resize["oe"] + dh)   # tam saat snap
            b.end = max(b.start + 1, min(self.hours_shown, new_end))
            self.redraw()
            return
        if self._drag:
            b   = self._block_by_id(self._drag["id"])
            dx  = e.x - self._drag["ox"]
            dh  = (dx / self._track_w()) * self.hours_shown
            dur = self._drag["oe"] - self._drag["os"]
            ns  = round(self._drag["os"] + dh)   # tam saat snap
            ns  = max(0, min(self.hours_shown - dur, ns))
            b.start = ns
            b.end   = ns + dur
            self.app.update_editor_times(b)
            self.redraw()
            return
        if self._draw:
            self._draw["cx"] = max(LABEL_W, min(LABEL_W + self._track_w(), e.x))
            self.redraw()
            return
        # imleç değiştir
        b, zone = self._block_at(e.x, e.y)
        if zone == "resize":  self._set_cursor("sb_h_double_arrow")
        elif zone == "move":  self._set_cursor("fleur")
        else:                 self._set_cursor("crosshair")

    def _on_release(self, e):
        if self._resize:
            self._resize = None
            self.redraw()
            return
        if self._drag:
            self._drag = None
            self.redraw()
            return
        if self._draw:
            d  = self._draw
            x1 = min(d["sx"], d["cx"])
            x2 = max(d["sx"], d["cx"])
            if x2 - x1 > 6:
                h1 = int(self._x_to_h(x1))
                h2 = int(self._x_to_h(x2))
                if h1 >= h2:
                    h2 = h1 + 1
                nb = Block(d["layer"], h1, h2)
                nb.start = max(0, nb.start)
                nb.end   = min(self.hours_shown, nb.end)
                self.blocks.append(nb)
                self._sel = nb.id
                self.app.open_editor(nb)
            self._draw = None
            self.redraw()

    def _on_hover(self, e):
        b, zone = self._block_at(e.x, e.y)
        if zone == "resize":  self._set_cursor("sb_h_double_arrow")
        elif zone == "move":  self._set_cursor("fleur")
        else:                 self._set_cursor("crosshair")

    def _on_resize(self, e):
        self.redraw()

    def _set_cursor(self, c):
        self.config(cursor=c)

    def _block_by_id(self, bid):
        return next((b for b in self.blocks if b.id == bid), None)

    def delete_selected(self):
        if self._sel:
            self.blocks = [b for b in self.blocks if b.id != self._sel]
            self._sel = None
            self.app.close_editor()
            self.redraw()

    def canvas_height(self):
        return len(LAYER_KEYS) * (TRACK_H + 6) + 18 + 10
