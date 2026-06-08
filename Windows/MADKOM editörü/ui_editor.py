# ──────────────────────────── UI Editor Panel ───────────────────────────

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from datetime import datetime, timedelta, timezone
from timeline_canvas import TimelineCanvas, Block, LAYER_CFG, LAYER_KEYS, TRACK_H, LABEL_W
from pdf_generator import _build_pdf

# ─────────────────────────── Renkler & Sabitler ───────────────────────────
# Alt taraftaki arayüz kodlarının hata vermemesi için renk tanımlamalarını buraya ekledik
BG_DARK       = "#ffffff"
BG_MID        = "#f6f8fa"
BG_PANEL      = "#f0f2f5"
BORDER        = "#d0d7de"
TEXT_PRIMARY  = "#24292f"
TEXT_MUTED    = "#6a737d"
ACCENT        = "#0969da"

START_HOUR    = 0   # Program açıldığında varsayılan başlangıç sati (00Z)
HOURS_SHOWN   = 24  # Zaman çizelgesinde gösterilecek toplam saat süresi
HOURS_MAX     = 48    # Zaman çizelgesinin çıkabileceği maksimum saat sınırı

# ──────────────────────────── Düzenleyici Panel ───────────────────────────

FIELD_DEFS = {}  # Artık kullanılmıyor; tüm katmanlar yalnızca "etiket" kullanır


class EditorPanel(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        self.app     = app
        self._block  = None
        self._vars   = {}
        self._widgets = {}
        self._build_empty()

    def _build_empty(self):
        for w in self.winfo_children():
            w.destroy()
        tk.Label(self, text="Bir blok seçin veya çizin.",
                 bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 10)).pack(pady=20)

    def load(self, block):
        self._block = block
        self._vars  = {}
        self._widgets = {}
        for w in self.winfo_children():
            w.destroy()

        cfg = LAYER_CFG[block.layer]

        # Başlık
        hdr = tk.Frame(self, bg=cfg["color"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=cfg["label"].upper(),
                 bg=cfg["color"], fg=cfg["text"],
                 font=("Arial", 10, "bold"), pady=6).pack(side="left", padx=10)

        # Zaman
        time_frm = tk.Frame(self, bg=BG_MID)
        time_frm.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(time_frm, text="Başlangıç:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9)).grid(row=0, column=0, sticky="w")
        _sh = self.app.timeline.start_hour
        self._start_lbl = tk.Label(time_frm, text=self._fmt_h(block.start, _sh),
                                    bg=BG_MID, fg=ACCENT, font=("Courier", 10, "bold"))
        self._start_lbl.grid(row=0, column=1, padx=6, sticky="w")
        tk.Label(time_frm, text="Bitiş:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9)).grid(row=0, column=2, sticky="w")
        self._end_lbl = tk.Label(time_frm, text=self._fmt_h(block.end, _sh),
                                  bg=BG_MID, fg=ACCENT, font=("Courier", 10, "bold"))
        self._end_lbl.grid(row=0, column=3, padx=6, sticky="w")

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", padx=4, pady=4)

        # Etiket alanı
        grid_frm = tk.Frame(self, bg=BG_MID)
        grid_frm.pack(fill="x", padx=8, pady=4)
        tk.Label(grid_frm, text="Etiket:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9), anchor="w").grid(row=0, column=0, sticky="w", pady=4)
        etiket_var = tk.StringVar(value=block.fields.get("etiket", ""))
        self._vars["etiket"] = etiket_var
        etiket_entry = tk.Entry(grid_frm, textvariable=etiket_var, width=20,
                                bg=BG_DARK, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                relief="flat", font=("Courier", 9),
                                highlightthickness=1, highlightbackground=BORDER,
                                highlightcolor=ACCENT)
        etiket_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)

        def _on_etiket_key(e=None):
            cur = etiket_var.get()
            tr_map = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
            upper = "".join(tr_map.get(c, c.upper()) for c in cur)
            if cur != upper:
                pos = etiket_entry.index(tk.INSERT)
                etiket_var.set(upper)
                etiket_entry.icursor(pos)
            self._live_save()

        etiket_entry.bind("<KeyRelease>", _on_etiket_key)

        # Olasılık alanı
        tk.Label(grid_frm, text="Olasılık:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9), anchor="w").grid(row=1, column=0, sticky="w", pady=4)
        olasilik_var = tk.StringVar(value=block.fields.get("olasilik", ""))
        self._vars["olasilik"] = olasilik_var
        olasilik_entry = tk.Entry(grid_frm, textvariable=olasilik_var, width=20,
                                  bg=BG_DARK, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                  relief="flat", font=("Courier", 9),
                                  highlightthickness=1, highlightbackground=BORDER,
                                  highlightcolor=ACCENT)
        olasilik_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)
        olasilik_entry.bind("<KeyRelease>", lambda e: self._live_save())
        grid_frm.columnconfigure(1, weight=1)

# ── Etiket Hizalama ───────────────────────────────────────────────
        align_sep = tk.Frame(self, bg=BORDER, height=1)
        align_sep.pack(fill="x", padx=4, pady=(2, 2))
        align_frm = tk.Frame(self, bg=BG_MID)
        align_frm.pack(fill="x", padx=8, pady=(2, 6))
        tk.Label(align_frm, text="Etiket Konumu:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9), anchor="w").pack(side="left")

        cur_align = getattr(block, "label_align", "center")

        def _set_align(val):
            self._block.label_align = val
            _update_align_buttons()
            self.app.timeline.redraw()

        self._btn_align_left = tk.Button(align_frm, text="◀ Sol",
            bg=ACCENT if cur_align == "left" else BG_PANEL,
            fg="#ffffff" if cur_align == "left" else TEXT_PRIMARY,
            relief="flat", font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=lambda: _set_align("left"))
        self._btn_align_left.pack(side="left", padx=(6, 2))

        self._btn_align_center = tk.Button(align_frm, text="■ Orta",
            bg=ACCENT if cur_align == "center" else BG_PANEL,
            fg="#ffffff" if cur_align == "center" else TEXT_PRIMARY,
            relief="flat", font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=lambda: _set_align("center"))
        self._btn_align_center.pack(side="left", padx=2)

        self._btn_align_right = tk.Button(align_frm, text="Sağ ▶",
            bg=ACCENT if cur_align == "right" else BG_PANEL,
            fg="#ffffff" if cur_align == "right" else TEXT_PRIMARY,
            relief="flat", font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=lambda: _set_align("right"))
        self._btn_align_right.pack(side="left", padx=2)

        def _update_align_buttons():
            a = getattr(self._block, "label_align", "center") if self._block else "center"
            self._btn_align_left  .config(bg=ACCENT if a=="left"   else BG_PANEL,
                                          fg="#ffffff" if a=="left"   else TEXT_PRIMARY)
            self._btn_align_center.config(bg=ACCENT if a=="center" else BG_PANEL,
                                          fg="#ffffff" if a=="center" else TEXT_PRIMARY)
            self._btn_align_right .config(bg=ACCENT if a=="right"  else BG_PANEL,
                                          fg="#ffffff" if a=="right"  else TEXT_PRIMARY)

        # Metin rengi seçimi
        txt_sep = tk.Frame(self, bg=BORDER, height=1)
        txt_sep.pack(fill="x", padx=4, pady=(2, 4))
        txt_color_frm = tk.Frame(self, bg=BG_MID)
        txt_color_frm.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(txt_color_frm, text="Metin Rengi:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9), anchor="w").pack(side="left")
        self._text_color_var = tk.StringVar(value=block.text_color or "")
        # Siyah butonu
        def _set_txt_black():
            self._block.text_color = "#000000"
            self._text_color_var.set("#000000")
            _update_txt_buttons()
            self.app.timeline.redraw()
        # Beyaz butonu
        def _set_txt_white():
            self._block.text_color = "#ffffff"
            self._text_color_var.set("#ffffff")
            _update_txt_buttons()
            self.app.timeline.redraw()
        # Otomatik butonu
        def _set_txt_auto():
            self._block.text_color = None
            self._text_color_var.set("")
            _update_txt_buttons()
            self.app.timeline.redraw()

        self._btn_txt_auto  = tk.Button(txt_color_frm, text="Oto",
            bg=ACCENT, fg="#ffffff", relief="flat",
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=_set_txt_auto)
        self._btn_txt_auto.pack(side="left", padx=(6, 2))
        self._btn_txt_black = tk.Button(txt_color_frm, text="■ Siyah",
            bg=BG_PANEL, fg="#000000", relief="flat",
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=_set_txt_black)
        self._btn_txt_black.pack(side="left", padx=2)
        self._btn_txt_white = tk.Button(txt_color_frm, text="□ Beyaz",
            bg=BG_PANEL, fg=TEXT_PRIMARY, relief="flat",
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=_set_txt_white)
        self._btn_txt_white.pack(side="left", padx=2)

        def _update_txt_buttons():
            tc = self._block.text_color if self._block else None
            self._btn_txt_auto.config( bg=ACCENT    if tc is None     else BG_PANEL,
                                       fg="#ffffff"  if tc is None     else TEXT_PRIMARY)
            self._btn_txt_black.config(bg="#333333"  if tc=="#000000"  else BG_PANEL,
                                       fg="#ffffff"  if tc=="#000000"  else "#000000")
            self._btn_txt_white.config(bg="#888888"  if tc=="#ffffff"  else BG_PANEL,
                                       fg="#ffffff"  if tc=="#ffffff"  else TEXT_PRIMARY)
        _update_txt_buttons()

        def _update_type_buttons():
            s = self._block.striped if self._block else False
            d = self._block.dashed_border if self._block else False
            self._btn_striped.config(bg=ACCENT if s else BG_PANEL,
                                     fg="#ffffff" if s else TEXT_PRIMARY)
            self._btn_dashed.config( bg=ACCENT if d else BG_PANEL,
                                     fg="#ffffff" if d else TEXT_PRIMARY)

        # Renk seçici — sabit sınıflandırma butonları
        color_sep = tk.Frame(self, bg=BORDER, height=1)
        color_sep.pack(fill="x", padx=4, pady=(6, 2))
        color_lbl_frm = tk.Frame(self, bg=BG_MID)
        color_lbl_frm.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(color_lbl_frm, text="Blok Rengi:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9), anchor="w").pack(side="left")
        self._color_preview = tk.Label(color_lbl_frm, text="  ■  ", bg=BG_MID,
                                        fg=block.color or "#0969da",
                                        font=("Arial", 12))
        self._color_preview.pack(side="left", padx=4)

        # 8 sabit renk: satır başı etiket | koyu kare | açık kare
        # Format: (etiket, koyu_hex, koyu_fg, açık_hex, açık_fg)
        SEVERITY_ROWS = [
            ("Hafif",    "#049104", "#ffffff", "#07fb03", "#1a1a1a"),
            ("Orta",     "#fe9601", "#ffffff", "#fff507", "#1a1a1a"),
            ("Kuvvetli", "#cd0102", "#ffffff", "#f60003", "#1a1a1a"),
            ("Şiddetli", "#993399", "#ffffff", "#cc66cc", "#1a1a1a"),
        ]
        sev_grid = tk.Frame(self, bg=BG_MID)
        sev_grid.pack(fill="x", padx=8, pady=(0, 6))
        self._sev_buttons = []

        def _make_sev_cmd(hex_color):
            def _cmd():
                if self._block:
                    self._block.color = hex_color
                    self._color_preview.config(fg=hex_color)
                    self._update_sev_buttons()
                    self.app.timeline.redraw()
            return _cmd

        for row_i, (lbl, dark_hex, dark_fg, light_hex, light_fg) in enumerate(SEVERITY_ROWS):
            tk.Label(sev_grid, text=lbl, bg=BG_MID, fg=TEXT_PRIMARY,
                     font=("Arial", 8, "bold"), width=8, anchor="w"
                     ).grid(row=row_i, column=0, sticky="w", pady=2)
            btn_dark = tk.Button(sev_grid, text="(koyu)", bg=dark_hex, fg=dark_fg,
                                 relief="flat", font=("Arial", 7, "bold"),
                                 padx=6, pady=4, cursor="hand2", width=6,
                                 command=_make_sev_cmd(dark_hex))
            btn_dark.grid(row=row_i, column=1, padx=(4, 2), pady=2)
            self._sev_buttons.append((btn_dark, dark_hex))
            btn_light = tk.Button(sev_grid, text="(açık)", bg=light_hex, fg=light_fg,
                                  relief="flat", font=("Arial", 7, "bold"),
                                  padx=6, pady=4, cursor="hand2", width=6,
                                  command=_make_sev_cmd(light_hex))
            btn_light.grid(row=row_i, column=2, padx=(2, 4), pady=2)
            self._sev_buttons.append((btn_light, light_hex))

        def _update_sev_buttons_local():
            cur = self._block.color if self._block else None
            for btn, hc in self._sev_buttons:
                if cur == hc:
                    btn.config(relief="solid", highlightthickness=2,
                               highlightbackground="#000000")
                else:
                    btn.config(relief="flat", highlightthickness=0)

        self._update_sev_buttons = _update_sev_buttons_local
        self._update_sev_buttons()

        def _update_txt_buttons():
            tc = self._block.text_color if self._block else None
            self._btn_txt_auto.config( bg=ACCENT    if tc is None     else BG_PANEL,
                                       fg="#ffffff"  if tc is None     else TEXT_PRIMARY)
            self._btn_txt_black.config(bg="#333333"  if tc=="#000000"  else BG_PANEL,
                                       fg="#ffffff"  if tc=="#000000"  else "#000000")
            self._btn_txt_white.config(bg="#888888"  if tc=="#ffffff"  else BG_PANEL,
                                       fg="#ffffff"  if tc=="#ffffff"  else TEXT_PRIMARY)
        _update_txt_buttons()

        def _update_type_buttons():
            s = self._block.striped if self._block else False
            d = self._block.dashed_border if self._block else False
            self._btn_striped.config(bg=ACCENT if s else BG_PANEL,
                                     fg="#ffffff" if s else TEXT_PRIMARY)
            self._btn_dashed.config( bg=ACCENT if d else BG_PANEL,
                                     fg="#ffffff" if d else TEXT_PRIMARY)

        # Butonlar
        btn_frm = tk.Frame(self, bg=BG_MID)
        btn_frm.pack(fill="x", padx=8, pady=10)
        tk.Button(btn_frm, text="✔ Kaydet", bg="#238636", fg="#ffffff",
                  activebackground="#2ea043", relief="flat",
                  font=("Arial", 9, "bold"), padx=10, pady=4,
                  command=self._save).pack(side="left", padx=(0, 6))
        tk.Button(btn_frm, text="✕ Sil", bg=BG_PANEL, fg="#f85149",
                  activebackground="#2d1117", relief="flat",
                  font=("Arial", 9, "bold"), padx=10, pady=4,
                  command=self.app.delete_selected).pack(side="left")


    def _live_save(self):
        if not self._block:
            return
        for fid, var in self._vars.items():
            self._block.fields[fid] = var.get()
        self.app.timeline.redraw()

    def _save(self):
        if not self._block:
            return
        for fid, var in self._vars.items():
            self._block.fields[fid] = var.get()
        self.app.timeline.redraw()

    def update_times(self, block):
        if self._block and self._block.id == block.id:
            sh = self.app.timeline.start_hour
            self._start_lbl.config(text=self._fmt_h(block.start, sh))
            self._end_lbl.config(text=self._fmt_h(block.end, sh))

    def clear(self):
        self._block = None
        self._build_empty()

    @staticmethod
    def _fmt_h(h, start_hour=0):
        abs_h = int(start_hour + h) % 24
        mm = round((h % 1) * 60)
        return f"{abs_h:02d}:{mm:02d}Z"


# ──────────────────────────── Meta Panel (üst) ───────────────────────────

class CheckboxDropdown(tk.Frame):
    """Tıklanınca açılan checkbox menüsü."""

    def __init__(self, parent, var, options, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        self.var      = var
        self.options  = options
        self.chk_vars = {opt: tk.BooleanVar() for opt in options}
        self._popup   = None
        self._parse_current()

        # Tek tıklanabilir kutu
        self._btn = tk.Button(
            self, textvariable=self.var,
            bg=BG_DARK, fg=TEXT_PRIMARY, anchor="w",
            relief="flat", font=("Courier", 9),
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, cursor="hand2",
            command=self._toggle)
        self._btn.pack(fill="x", expand=True)
        # Placeholder mantığı
        self._update_btn_text()

    def _parse_current(self):
        current = self.var.get()
        if current:
            items = [x.strip() for x in current.split(",")]
            for opt in self.options:
                self.chk_vars[opt].set(opt in items)

    def _update_btn_text(self):
        selected = [opt for opt in self.options if self.chk_vars[opt].get()]
        if not selected:
            self._btn.config(fg=TEXT_MUTED, text="(seçiniz...)")
        else:
            txt = ", ".join(selected)
            if len(txt) > 38:
                txt = ", ".join(selected[:2]) + f" +{len(selected)-2}"
            self._btn.config(fg=TEXT_PRIMARY, text=txt)

    def _toggle(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
            self._popup = None
            return
        self._open_popup()

    def _open_popup(self):
        self._popup = tk.Toplevel(self)
        self._popup.wm_overrideredirect(True)
        self._popup.configure(bg=BORDER)

        # Konum: butonun altı
        self.update_idletasks()
        x = self._btn.winfo_rootx()
        y = self._btn.winfo_rooty() + self._btn.winfo_height() + 2
        self._popup.geometry(f"+{x}+{y}")

        inner = tk.Frame(self._popup, bg=BG_DARK, padx=2, pady=4)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        for opt in self.options:
            row = tk.Frame(inner, bg=BG_DARK, cursor="hand2")
            row.pack(fill="x", pady=1, padx=4)

            var = self.chk_vars[opt]
            # Tik kutusu yerine renkli gösterge
            indicator = tk.Label(row, text="", width=2,
                                  bg=ACCENT if var.get() else BG_PANEL,
                                  fg="white", font=("Arial", 9, "bold"),
                                  relief="flat")
            indicator.pack(side="left", padx=(0, 6))

            lbl = tk.Label(row, text=opt, bg=BG_DARK, fg=TEXT_PRIMARY,
                           font=("Arial", 9), anchor="w")
            lbl.pack(side="left", fill="x", expand=True)

            def _make_toggle(o=opt, ind=indicator):
                def _tog(e=None):
                    self.chk_vars[o].set(not self.chk_vars[o].get())
                    ind.config(bg=ACCENT if self.chk_vars[o].get() else BG_PANEL,
                               text="✓" if self.chk_vars[o].get() else "")
                    self._on_change()
                return _tog

            fn = _make_toggle()
            row.bind("<Button-1>", fn)
            lbl.bind("<Button-1>", fn)
            indicator.bind("<Button-1>", fn)
            if var.get():
                indicator.config(text="✓")

        # Dışarı tıklayınca kapat
        self._popup.bind("<FocusOut>", lambda e: self._close_if_outside(e))
        self._popup.focus_set()

    def _close_if_outside(self, e):
        try:
            w = self._popup.winfo_containing(e.x_root, e.y_root)
            if w is None or not str(w).startswith(str(self._popup)):
                self._popup.destroy()
                self._popup = None
        except Exception:
            pass

    def _on_change(self):
        selected = [opt for opt in self.options if self.chk_vars[opt].get()]
        self.var.set(", ".join(selected))
        self._update_btn_text()


class MetaPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        self._build()

    def _build(self):
        today    = datetime.utcnow().strftime("%d.%m.%Y")
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%d.%m.%Y")

        # Meteorolojik olaylar seçenekleri
        weather_events = ["Kuvvetli rüzgar", "Sağanak yağmur", "Oraj/TS",
                         "CB bulutu", "LVO (düşük görüş)", "Dolu", "Windshear", "Kar yağışı"]

        self._vars = {}

        # ── Satır 0: Kurum Adı | Hazırlayan Unvanı | Hazırlayanın Adı | Meteorolojik Olaylar
        # Placeholder destekli field tanımları: (fid, etiket, genişlik, default, placeholder)
        row0_fields = [
            ("kurum",     "Kurum Adı",            44, "İstanbul Havalimanı Meteoroloji Müdürlüğü", None),
            ("unvan",     "Hazırlayan Unvanı",     44, "",                                         "Unvanınızı giriniz..."),
            ("imzalayan", "Hazırlayanın Adı",      44, "",                                         "Adınızı giriniz..."),
        ]
        col = 0
        for fid, lbl, w, default, placeholder in row0_fields:
            frm = tk.Frame(self, bg=BG_MID)
            frm.grid(row=0, column=col, padx=8, pady=(6, 2), sticky="w")
            tk.Label(frm, text=lbl, bg=BG_MID, fg=TEXT_MUTED,
                     font=("Arial", 8)).pack(anchor="w")
            var = tk.StringVar(value=default)
            self._vars[fid] = var
            e = tk.Entry(frm, textvariable=var, width=w,
                          bg=BG_DARK, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                          relief="flat", font=("Courier", 9),
                          highlightthickness=1,
                          highlightbackground=BORDER, highlightcolor=ACCENT)
            e.pack()
            if placeholder:
                # Placeholder mekanizması
                if not var.get():
                    e.insert(0, placeholder)
                    e.config(fg=TEXT_MUTED)
                def _on_focus_in(event, entry=e, ph=placeholder, v=var):
                    if entry.get() == ph:
                        entry.delete(0, "end")
                        entry.config(fg=TEXT_PRIMARY)
                def _on_focus_out(event, entry=e, ph=placeholder, v=var):
                    if not entry.get():
                        entry.insert(0, ph)
                        entry.config(fg=TEXT_MUTED)
                        v.set("")
                def _on_key(event, entry=e, ph=placeholder, v=var):
                    if entry.get() != ph:
                        entry.config(fg=TEXT_PRIMARY)
                        v.set(entry.get())
                e.bind("<FocusIn>",  _on_focus_in)
                e.bind("<FocusOut>", _on_focus_out)
                e.bind("<KeyRelease>", _on_key)
            col += 1

        # Meteorolojik Olaylar — satır 0, son sütun
        olay_frm = tk.Frame(self, bg=BG_MID)
        olay_frm.grid(row=0, column=col, padx=8, pady=(6, 2), sticky="w")
        tk.Label(olay_frm, text="Meteorolojik Olaylar", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 8)).pack(anchor="w")
        olay_var = tk.StringVar(value="")
        self._vars["olay"] = olay_var
        dd_border = tk.Frame(olay_frm, bg=BORDER, padx=1, pady=1)
        dd_border.pack(anchor="w")
        dropdown = CheckboxDropdown(dd_border, olay_var, weather_events)
        dropdown.pack()
        dropdown._btn.config(width=60)

        # ── Satır 1: Hazırlanma Tarihi | Geçerlilik Başlangıç | Geçerlilik Bitiş
        row1_fields = [
            ("tarih",   "Hazırlanma Tarihi",      22, today),
            ("bas_tar", "Geçerlilik Başlangıç",   22, today + " 00:00"),
            ("bit_tar", "Geçerlilik Bitiş",        22, tomorrow + " 00:00"),
        ]
        for i, (fid, lbl, w, default) in enumerate(row1_fields):
            frm = tk.Frame(self, bg=BG_MID)
            frm.grid(row=1, column=i, padx=8, pady=(2, 6), sticky="w")
            tk.Label(frm, text=lbl, bg=BG_MID, fg=TEXT_MUTED,
                     font=("Arial", 8)).pack(anchor="w")
            var = tk.StringVar(value=default)
            self._vars[fid] = var
            e = tk.Entry(frm, textvariable=var, width=w,
                          bg=BG_DARK, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                          relief="flat", font=("Courier", 9),
                          highlightthickness=1,
                          highlightbackground=BORDER, highlightcolor=ACCENT)
            e.pack()

        # İletişim — satır 1, Meteorolojik Olaylar ile aynı sütun (col)
        iletisim_frm = tk.Frame(self, bg=BG_MID)
        iletisim_frm.grid(row=1, column=col, padx=8, pady=(2, 6), sticky="w")
        tk.Label(iletisim_frm, text="İletişim", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 8)).pack(anchor="w")
        iletisim_var = tk.StringVar(value="(0212) 812 8316 / (16496)")
        self._vars["iletisim"] = iletisim_var
        iletisim_entry = tk.Entry(iletisim_frm, textvariable=iletisim_var, width=62,
                                   bg=BG_DARK, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                   relief="flat", font=("Courier", 9, "bold", "italic"),
                                   highlightthickness=1,
                                   highlightbackground=BORDER, highlightcolor=ACCENT)
        iletisim_entry.pack()

    def get(self):
        return {k: v.get() for k, v in self._vars.items()}


# ──────────────────────────── Ana Pencere ────────────────────────────────

class MatkomApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MATKOM Rapor Editörü — İstanbul Havalimanı Meteoroloji Müdürlüğü")
        self.configure(bg=BG_DARK)
        self.geometry("1280x720")
        self.minsize(900, 600)
        self._build_ui()
        self._apply_style()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                         fieldbackground=BG_DARK, background=BG_DARK,
                         foreground=TEXT_PRIMARY, arrowcolor=TEXT_MUTED,
                         selectbackground=BG_PANEL)

    def _build_ui(self):
        # ─ Meta panel ilk olarak oluştur (kurum adı için)
        self.meta = MetaPanel(self)
        
        # ─ Başlık çubuğu
        top = tk.Frame(self, bg=BG_MID, bd=0)
        top.pack(fill="x")
        tk.Label(top, text="✈  MATKOM RAPOR EDİTÖRÜ",
                  bg=BG_MID, fg=ACCENT,
                  font=("Arial", 11, "bold"), pady=8, padx=12).pack(side="left")
        # Kurum adını meta'dan al ve dinamik olarak güncelle
        self._header_label = tk.Label(top, text=self.meta._vars["kurum"].get(),
                  bg=BG_MID, fg=TEXT_MUTED,
                  font=("Arial", 9), pady=8)
        self._header_label.pack(side="left")
        # Kurum adı değiştiğinde header'ı güncelle
        self.meta._vars["kurum"].trace_add("write", lambda *args: self._header_label.config(
            text=self.meta._vars["kurum"].get()))

        # Araç çubuğu butonları
        btn_data = [
            ("💾 Kaydet",         self._save_project),
            ("📂 Aç",             self._load_project),
            ("📄 PDF Rapor",      self._export_pdf),
            ("📋 Metin Rapor",    self._export_text),
            ("🗑 Temizle",        self._clear_all),
        ]
        for lbl, cmd in btn_data:
            tk.Button(top, text=lbl, command=cmd,
                       bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=BORDER, relief="flat",
                       font=("Arial", 9), padx=10, pady=6,
                       cursor="hand2").pack(side="right", padx=2, pady=4)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

        # ─ Meta panel (zaten oluşturulmuş)
        self.meta.pack(fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ─ Ana alan: çizelge + editör
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        # Çizelge (sol/orta)
        tl_frm = tk.Frame(main, bg=BG_DARK)
        tl_frm.pack(side="left", fill="both", expand=True)

        # Başlangıç saati ayarı
        sh_frm = tk.Frame(tl_frm, bg=BG_MID)
        sh_frm.pack(fill="x", padx=4, pady=(2, 0))
        tk.Label(sh_frm, text="Periyot Başlangıcı:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 10, "bold")).pack(side="left", padx=(6, 4))
        self._start_hour_var = tk.IntVar(value=START_HOUR)
        sh_spin = tk.Spinbox(sh_frm, from_=0, to=23, textvariable=self._start_hour_var,
                              width=4, font=("Courier", 12, "bold"),
                              bg=BG_DARK, fg=ACCENT, relief="flat",
                              highlightthickness=1, highlightbackground=BORDER,
                              format="%02.0f", increment=1)
        sh_spin.pack(side="left")
        tk.Label(sh_frm, text="Z", bg=BG_MID, fg=ACCENT,
                 font=("Courier", 12, "bold")).pack(side="left", padx=(1, 16))
        self._start_hour_var.trace_add("write", self._on_start_hour_change)

        # Zaman çizelgesi süresi
        tk.Label(sh_frm, text="Zaman Çizelgesi Süresi:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 10, "bold")).pack(side="left", padx=(0, 4))
        self._hours_shown_var = tk.IntVar(value=HOURS_SHOWN)
        hs_spin = tk.Spinbox(sh_frm, from_=1, to=HOURS_MAX, textvariable=self._hours_shown_var,
                              width=4, font=("Courier", 12, "bold"),
                              bg=BG_DARK, fg=ACCENT, relief="flat",
                              highlightthickness=1, highlightbackground=BORDER,
                              format="%02.0f", increment=1)
        hs_spin.pack(side="left")
        tk.Label(sh_frm, text="saat", bg=BG_MID, fg=ACCENT,
                 font=("Courier", 12, "bold")).pack(side="left", padx=(2, 4))
        self._hours_shown_var.trace_add("write", self._on_hours_shown_change)

        hint = tk.Label(tl_frm,
                         text="  Katman üzerine tıklayıp sürükle → blok oluştur   |   "
                              "Bloğu tut → taşı   |   Sağ kenara tut → genişlet/daralt   |   "
                              "Bloğa tıkla → düzenle",
                         bg=BG_DARK, fg=TEXT_MUTED, font=("Arial", 8), anchor="w", pady=4)
        hint.pack(fill="x")

        tl_canvas_frm = tk.Frame(tl_frm, bg=BG_DARK)
        tl_canvas_frm.pack(fill="both", expand=True, padx=4)

        ch = len(LAYER_KEYS) * (TRACK_H + 6) + 38
        self.timeline = TimelineCanvas(tl_canvas_frm, self,
                                        width=800, height=ch)
        self.timeline.pack(fill="both", expand=True)

        # ─ Sinoptik Durum Değerlendirmesi (opsiyonel)
        sinoptik_frm = tk.Frame(tl_frm, bg=BG_MID)
        sinoptik_frm.pack(fill="x", padx=4, pady=(6, 2))
        tk.Label(sinoptik_frm, text="Sinoptik Durum Değerlendirmesi (opsiyonel)",
                 bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold"), anchor="w", padx=4, pady=4).pack(fill="x")
        sinoptik_inner = tk.Frame(sinoptik_frm, bg=BG_MID)
        sinoptik_inner.pack(fill="x", padx=4, pady=(0, 4))
        sinoptik_sb = tk.Scrollbar(sinoptik_inner, orient="vertical")
        sinoptik_sb.pack(side="right", fill="y")
        self.sinoptik_text = tk.Text(sinoptik_inner, height=6,
                                     bg=BG_DARK, fg=TEXT_PRIMARY,
                                     insertbackground=TEXT_PRIMARY,
                                     relief="flat", font=("Arial", 9),
                                     wrap="word",
                                     highlightthickness=1,
                                     highlightbackground=BORDER,
                                     highlightcolor=ACCENT,
                                     padx=6, pady=6,
                                     yscrollcommand=sinoptik_sb.set)
        self.sinoptik_text.pack(fill="x", expand=True, side="left")
        sinoptik_sb.config(command=self.sinoptik_text.yview)

        # ─ Hava Analizi ve Yorumu
        analiz_frm = tk.Frame(tl_frm, bg=BG_MID)
        analiz_frm.pack(fill="x", padx=4, pady=(2, 2))
        tk.Label(analiz_frm, text="Hava Analizi ve Yorumu",
                 bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold"), anchor="w", padx=4, pady=4).pack(fill="x")
        analiz_inner = tk.Frame(analiz_frm, bg=BG_MID)
        analiz_inner.pack(fill="x", padx=4, pady=(0, 4))
        analiz_sb = tk.Scrollbar(analiz_inner, orient="vertical")
        analiz_sb.pack(side="right", fill="y")
        self.analiz_text = tk.Text(analiz_inner, height=6,
                                   bg=BG_DARK, fg=TEXT_PRIMARY,
                                   insertbackground=TEXT_PRIMARY,
                                   relief="flat", font=("Arial", 9),
                                   wrap="word",
                                   highlightthickness=1,
                                   highlightbackground=BORDER,
                                   highlightcolor=ACCENT,
                                   padx=6, pady=6,
                                   yscrollcommand=analiz_sb.set)
        self.analiz_text.pack(fill="x", expand=True, side="left")
        analiz_sb.config(command=self.analiz_text.yview)

        # ─ Olay Takibi ve Bilgi
        olay_takip_frm = tk.Frame(tl_frm, bg=BG_MID)
        olay_takip_frm.pack(fill="x", padx=4, pady=(2, 2))
        tk.Label(olay_takip_frm, text="Olay Takibi ve Bilgi",
                 bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold"), anchor="w", padx=4, pady=4).pack(fill="x")
        olay_takip_inner = tk.Frame(olay_takip_frm, bg=BG_MID)
        olay_takip_inner.pack(fill="x", padx=4, pady=(0, 4))
        olay_takip_sb = tk.Scrollbar(olay_takip_inner, orient="vertical")
        olay_takip_sb.pack(side="right", fill="y")
        self.olay_takip_text = tk.Text(olay_takip_inner, height=6,
                                       bg=BG_DARK, fg=TEXT_PRIMARY,
                                       insertbackground=TEXT_PRIMARY,
                                       relief="flat", font=("Arial", 9),
                                       wrap="word",
                                       highlightthickness=1,
                                       highlightbackground=BORDER,
                                       highlightcolor=ACCENT,
                                       padx=6, pady=6,
                                       yscrollcommand=olay_takip_sb.set)
        self.olay_takip_text.pack(fill="x", expand=True, side="left")
        olay_takip_sb.config(command=self.olay_takip_text.yview)

        _default_olay_takip = (
            "Tahmin güncel durum TAF raporlarına yansıtılacağından "
            "takip edilmesi önem arz etmektedir. Uydu-Radar gözlemleri ile yapılacak "
            "Nowcasting tahmin sonucu gerekli görüldüğü takdirde MEYDAN UYARI'ları "
            "ilgili birimler ile paylaşılacaktır."
        )
        self.olay_takip_text.insert("1.0", _default_olay_takip)

        # ─ Editör (sağ)
        tk.Frame(main, bg=BORDER, width=1).pack(side="left", fill="y")
        editor_frm = tk.Frame(main, bg=BG_MID, width=260)
        editor_frm.pack(side="right", fill="y")
        editor_frm.pack_propagate(False)

        tk.Label(editor_frm, text="BLOK DÜZENLE",
                  bg=BG_MID, fg=TEXT_MUTED,
                  font=("Arial", 8, "bold"), pady=6).pack(fill="x", padx=8)
        tk.Frame(editor_frm, bg=BORDER, height=1).pack(fill="x")

        self.editor = EditorPanel(editor_frm, self)
        self.editor.pack(fill="both", expand=True)

        # ─ Durum çubuğu
        self.status = tk.Label(self, text="Hazır",
                                 bg=BG_MID, fg=TEXT_MUTED,
                                 font=("Arial", 8), anchor="w", pady=3, padx=10)
        self.status.pack(fill="x", side="bottom")

        # Delete tuşu ile seçili bloğu sil
        self.bind("<Delete>", lambda e: self._on_delete_key(e))

    def _on_delete_key(self, event):
        """Delete tuşuna basılınca — metin kutusuna odaklanılmamışsa seçili bloğu sil."""
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            return  # metin alanındaysa Delete tuşu normal çalışsın
        self.delete_selected()

    def _on_start_hour_change(self, *args):
        try:
            h = int(str(self._start_hour_var.get()).lstrip("0") or "0")
            h = max(0, min(23, h))
            self.timeline.start_hour = h
            self.timeline.redraw()
            self.refresh_analiz()
        except (ValueError, tk.TclError):
            pass

    def _on_hours_shown_change(self, *args):
        try:
            h = int(self._hours_shown_var.get())
            h = max(1, min(HOURS_MAX, h))
            self.timeline.hours_shown = h
            self.timeline.redraw()
        except (ValueError, tk.TclError):
            pass

    def open_editor(self, block):
        self.editor.load(block)

    def close_editor(self):
        self.editor.clear()

    def update_editor_times(self, block):
        self.editor.update_times(block)

    def delete_selected(self):
        if not getattr(self.timeline, "_sel", None):
            return
        self.timeline.delete_selected()
        self.refresh_analiz()
        self._set_status("Blok silindi.")

    def _set_status(self, msg):
        self.status.config(text=msg)
        self.after(4000, lambda: self.status.config(text="Hazır"))

    def _save_project(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".matkom",
            filetypes=[("MATKOM Proje", "*.matkom"), ("Tüm Dosyalar", "*.*")],
            title="Projeyi Kaydet")
        if not path:
            return
        data = {
            "meta":       self.meta.get(),
            "blocks":     [b.to_dict() for b in self.timeline.blocks],
            "analiz":     self.analiz_text.get("1.0", "end-1c"),
            "sinoptik":   self.sinoptik_text.get("1.0", "end-1c"),
            "olay_takip": self.olay_takip_text.get("1.0", "end-1c")
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._set_status(f"Kaydedildi: {os.path.basename(path)}")

    def _load_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("MATKOM Proje", "*.matkom"), ("Tüm Dosyalar", "*.*")],
            title="Proje Aç")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # ── Meta alanlarını yükle (tarih/periyot hariç — bunları aşağıda güncelleyeceğiz) ──
        DATE_FIELDS = {"tarih", "bas_tar", "bit_tar"}
        for fid, val in data.get("meta", {}).items():
            if fid in self.meta._vars and fid not in DATE_FIELDS:
                self.meta._vars[fid].set(val)

        # ── Blokları yükle ──
        self.timeline.blocks = [Block.from_dict(d) for d in data.get("blocks", [])]

        # ── Açılış gününe göre tarihleri güncelle ──────────────────────────────
        # Hazırlanma tarihi = bugün
        today_utc  = datetime.utcnow()
        today_str  = today_utc.strftime("%d.%m.%Y")
        self.meta._vars["tarih"].set(today_str)

        # Blokların start/end değerlerinden geçerlilik periyodunu hesapla
        sh      = int(str(self._start_hour_var.get()).lstrip("0") or "0")   # mevcut çizelge başlangıç saati
        base_dt = today_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        if self.timeline.blocks:
            min_start = min(b.start for b in self.timeline.blocks)
            max_end   = max(b.end   for b in self.timeline.blocks)
            bas_dt = base_dt + timedelta(hours=sh + min_start)
            bit_dt = base_dt + timedelta(hours=sh + max_end)
            self.meta._vars["bas_tar"].set(bas_dt.strftime("%d.%m.%Y %H:%M"))
            self.meta._vars["bit_tar"].set(bit_dt.strftime("%d.%m.%Y %H:%M"))
        else:
            tomorrow_str = (today_utc + timedelta(days=1)).strftime("%d.%m.%Y")
            self.meta._vars["bas_tar"].set(today_str   + " 00:00")
            self.meta._vars["bit_tar"].set(tomorrow_str + " 00:00")

        # ── Diğer metin alanlarını yükle ──
        self.sinoptik_text.delete("1.0", "end")
        self.sinoptik_text.insert("1.0", data.get("sinoptik", ""))
        self.olay_takip_text.delete("1.0", "end")
        self.olay_takip_text.insert("1.0", data.get("olay_takip", ""))

        # ── Hava Analizi: güncel tarihlere göre yeniden üret ──────────────────
        self.timeline._sel = None
        self.close_editor()
        self.timeline.redraw()
        self.refresh_analiz()   # blok tarih/saatlerini açılış gününe göre yeniden hesapla

        self._set_status(f"Açıldı: {os.path.basename(path)}")

    def _clear_all(self):
        if messagebox.askyesno("Temizle", "Tüm bloklar silinsin mi?"):
            self.timeline.blocks = []
            self.timeline._sel   = None
            self.close_editor()
            self.timeline.redraw()

    # ── Rapor metni ───────────────────────────────────────────────────

    # Katman görünen adları (Hava Analizi metni için)
    LAYER_DISPLAY = {
        "ruzgar": "Rüzgar",
        "gorus":  "Görüş",
        "hadise": "Hadise",
        "oraj":   "Oraj/TS",
        "bulut":  "Bulut",
    }

    def _block_dt_str(self, offset_hours):
        """Çizelge start_hour + offset_hours ekleyerek 'gg.aa.yyyy SS:DDZ' döndür."""
        bas = self.meta._vars.get("bas_tar", tk.StringVar()).get()
        sh  = self.timeline.start_hour   # çizelge 0. slotunun gerçek UTC saati
        try:
            bas_clean = bas.strip().split(" ")[0]   # sadece tarih kısmı al, saati yoksay
            base_dt = datetime.strptime(bas_clean, "%d.%m.%Y")
        except Exception:
            base_dt = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        # Çizelge 0. slotu → base_dt + start_hour
        # Blok offset_hours → 0. slottan itibaren göreli saat
        origin = base_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        result = origin + timedelta(hours=sh + int(offset_hours))
        return result.strftime("%d.%m.%Y %H:%M") + "Z"

    def _build_analiz_text(self):
        """Bloklardan otomatik Hava Analizi ve Yorumu metni üretir."""
        parts = []
        for key in LAYER_KEYS:
            blocks_in_layer = sorted(
                [b for b in self.timeline.blocks if b.layer == key],
                key=lambda b: b.start)
            if not blocks_in_layer:
                continue
            display = self.LAYER_DISPLAY.get(key, key.title())
            segments = []
            for b in blocks_in_layer:
                s_str = self._block_dt_str(b.start)
                e_str = self._block_dt_str(b.end)
                etiket   = b.fields.get("etiket", "").strip()
                olasilik = b.fields.get("olasilik", "").strip()
                # Aynı tarih-gün ise yalnızca saatleri yaz
                s_date, s_time = s_str[:10], s_str[11:]
                e_date, e_time = e_str[:10], e_str[11:]
                if s_date == e_date:
                    aralik = f"{s_str} ile {e_time} saatleri aralığında"
                else:
                    aralik = f"{s_str} ile {e_str} saatleri aralığında"
                seg = aralik
                if etiket:
                    seg += f" {etiket}"
                if olasilik:
                    olasilik_clean = olasilik.lstrip("%")
                    seg += f" (%{olasilik_clean})"
                segments.append(seg)
            line = f"{display}: " + ", ".join(segments) + "."
            parts.append(line)
        return "\n".join(parts)

    def refresh_analiz(self):
        """Bloklara göre analiz metnini yenile (mevcut içeriği günceller)."""
        txt = self._build_analiz_text()
        self.analiz_text.config(state="normal")
        self.analiz_text.delete("1.0", "end")
        if txt:
            self.analiz_text.insert("1.0", txt)
        self.analiz_text.config(state="normal")

    def _layer_text(self, layer):
        lb = sorted([b for b in self.timeline.blocks if b.layer == layer],
                    key=lambda b: b.start)
        lines = []
        for b in lb:
            sh = self.timeline.start_hour
            ts = EditorPanel._fmt_h(b.start, sh) + "–" + EditorPanel._fmt_h(b.end, sh)
            etiket = b.fields.get("etiket", "")
            lines.append((ts + "  " + etiket).strip())
        return "\n".join(lines) if lines else "—"

    def _export_text(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Metin", "*.txt"), ("Tüm Dosyalar", "*.*")],
            title="Metin Rapor Kaydet")
        if not path:
            return
        m   = self.meta.get()
        txt = self._build_text_report(m)
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        self._set_status(f"Metin rapor kaydedildi: {os.path.basename(path)}")
        # Önizleme
        self._show_text_preview(txt)

    def _build_text_report(self, m):
        sep = "=" * 70
        lines = [
            sep,
            "METEOROLOJİ GENEL MÜDÜRLÜĞÜ",
            m.get('kurum', 'İSTANBUL HAVALİMANI METEOROLOJİ MÜDÜRLÜĞÜ').upper(),
            "MADKOM ANALİZ VE TAHMİN RAPORU",
            sep,
            f"Meteorolojik Olay (Wx) : {m.get('olay','')}",
            f"Hazırlayan Birim       : {m.get('kurum', 'İstanbul Havalimanı Meteoroloji Müdürlüğü')}",
            f"Hazırlama Tarihi       : {m.get('tarih','')}",
            f"Hazırlayan Unvanı      : {m.get('unvan','')}",
            f"Hazırlayanın Adı       : {m.get('imzalayan','')}",
            f"Geçerlilik Periyodu    : {m.get('bas_tar','')} – {m.get('bit_tar','')}",
            sep,
            "HALİHAZIR DURUM VE TAHMİN",
            "",
            "Rüzgar:",
            self._layer_text("ruzgar"),
            "",
            "Görüş:",
            self._layer_text("gorus"),
            "",
            "Hava Durumu / Hadise:",
            self._layer_text("hadise"),
            "",
            "ORAJ/TS:",
            self._layer_text("oraj"),
            "",
            "Bulutluluk:",
            self._layer_text("bulut"),
            sep,
            "Olay Takibi ve Bilgi:",
            self.olay_takip_text.get("1.0", "end-1c"),
            sep,
            "",
            f"                                    {m.get('imzalayan','')}",
            f"                                    {m.get('unvan','')}",
        ]
        return "\n".join(lines)

    def _show_text_preview(self, txt):
        win = tk.Toplevel(self)
        win.title("Metin Rapor Önizlemesi")
        win.configure(bg=BG_DARK)
        win.geometry("760x560")
        frm = tk.Frame(win, bg=BG_DARK)
        frm.pack(fill="both", expand=True, padx=8, pady=8)
        sb = tk.Scrollbar(frm)
        sb.pack(side="right", fill="y")
        t = tk.Text(frm, bg="#ffffff", fg=TEXT_PRIMARY,
                    font=("Courier New", 10), relief="flat",
                    yscrollcommand=sb.set, wrap="none")
        t.pack(fill="both", expand=True)
        sb.config(command=t.yview)
        t.insert("1.0", txt)
        t.config(state="disabled")

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Dosyası", "*.pdf"), ("Tüm Dosyalar", "*.*")],
            title="PDF Rapor Kaydet")
        if not path:
            return

        m = self.meta.get()

        # ── GEÇERLİLİK PERİYODU: blokların start/end değerlerinden otomatik hesapla ──
        all_blocks = self.timeline.blocks
        start_hour_offset = int(str(self._start_hour_var.get()).lstrip("0") or "0")

        if all_blocks:
            min_start = min(b.start for b in all_blocks)  # en erken başlangıç (göreli saat)
            max_end   = max(b.end   for b in all_blocks)  # en geç bitiş (göreli saat)

            # Bugünün UTC tarihini baz al, saat bilgisini sıfırla
            base_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

            # Gerçek UTC saatlerini hesapla
            validity_start_dt = base_dt + timedelta(hours=start_hour_offset + min_start)
            validity_end_dt   = base_dt + timedelta(hours=start_hour_offset + max_end)

            # PDF'teki "Geçerlilik Periyodu" satırına yaz — tam saat (02Z, 14Z gibi)
            m["periyot_baslangic"] = validity_start_dt.strftime("%d.%m.%Y %H:%M")
            m["periyot_bitis"]     = validity_end_dt.strftime("%d.%m.%Y %H:%M")
        else:
            m["periyot_baslangic"] = "Belirtilmedi"
            m["periyot_bitis"]     = "Belirtilmedi"

        m["sinoptik"]   = self.sinoptik_text.get("1.0", "end-1c")
        m["olay_takip"] = self.olay_takip_text.get("1.0", "end-1c")

        try:
            # pdf_generator.py dosyasındaki fonksiyonu tetikliyoruz
            # Güncellediğimiz m (meta) sözlüğünü aynen gönderiyoruz
            _build_pdf(path, m, {
                "ruzgar": self._layer_text("ruzgar"),
                "gorus":  self._layer_text("gorus"),
                "hadise": self._layer_text("hadise"),
                "oraj":   self._layer_text("oraj"),
                "bulut":  self._layer_text("bulut"),
            }, m.get("imzalayan", ""), m.get("unvan", ""),
               self.analiz_text.get("1.0", "end-1c"), self.timeline.blocks,
               int(str(self._start_hour_var.get()).lstrip("0") or "0"), self.timeline.hours_shown)
            
            self._set_status(f"PDF rapor kaydedildi: {os.path.basename(path)}")
            messagebox.showinfo("PDF", f"PDF oluşturuldu:\n{path}")
        except Exception as ex:
            messagebox.showerror("Hata", f"PDF oluşturulamadı:\n{ex}")

# ─────────────────────────────── Giriş ──────────────────────────────────

if __name__ == "__main__":
    # MatkomApp zaten kendi penceresini oluşturduğu için 
    # root = tk.Tk() dememize ve içine root vermemize gerek yok.
    
    app = MatkomApp() 
    app.title("MATKOM Rapor Editörü - İstanbul Havalimanı")
    app.geometry("1200x700") # Ekran boyutunu buradan ayarlayabilirsin
    
    app.mainloop()