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

# ── macOS uyumlu renkli buton (tk.Button bg/fg macOS'ta çalışmaz) ──────────
class ColorButton(tk.Canvas):
    """tk.Button yerine Canvas kullanarak macOS'ta da arka plan rengini gösterir."""

    def __init__(self, parent, text, bg, fg, command=None,
                 font=("Arial", 8, "bold"), padx=8, pady=4,
                 width=None, cursor="hand2", **kw):
        self._bg       = bg
        self._fg       = fg
        self._text     = text
        self._font     = font
        self._padx     = padx
        self._pady     = pady
        self._command  = command
        self._selected = False   # seçili kenar çizgisi için

        # Boyut tahmini
        import tkinter.font as tkfont
        try:
            fobj = tkfont.Font(font=font)
            tw   = fobj.measure(text)
            th   = fobj.metrics("linespace")
        except Exception:
            tw, th = len(text) * 7, 14
        cw = (width * 7 + padx * 2) if width else tw + padx * 2
        ch = th + pady * 2

        super().__init__(parent, width=cw, height=ch,
                         bg=parent.cget("bg"), highlightthickness=0,
                         cursor=cursor, **kw)
        self._cw = cw
        self._ch = ch
        self._draw()
        self.bind("<Button-1>",        self._on_click)
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)

    def _draw(self, hover=False):
        self.delete("all")
        bg = self._lighten(self._bg, 0.15) if hover else self._bg
        # Arka plan dikdörtgeni
        self.create_rectangle(0, 0, self._cw, self._ch,
                               fill=bg, outline="#00000033" if self._selected else "",
                               width=2 if self._selected else 0,
                               tags="bg")
        # Metin
        self.create_text(self._cw // 2, self._ch // 2,
                         text=self._text, fill=self._fg,
                         font=self._font, anchor="center", tags="txt")

    def _lighten(self, hex_color, amount):
        """Rengi biraz açar (hover efekti)."""
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
            r = min(255, int(r + (255-r)*amount))
            g = min(255, int(g + (255-g)*amount))
            b = min(255, int(b + (255-b)*amount))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _on_click(self, e):
        if self._command:
            self._command()

    def _on_enter(self, e):
        self._draw(hover=True)

    def _on_leave(self, e):
        self._draw(hover=False)

    def config(self, **kw):
        changed = False
        if "bg" in kw:
            self._bg = kw.pop("bg"); changed = True
        if "fg" in kw:
            self._fg = kw.pop("fg"); changed = True
        if "text" in kw:
            self._text = kw.pop("text"); changed = True
        if "relief" in kw:
            sel = kw.pop("relief") == "solid"
            if sel != self._selected:
                self._selected = sel; changed = True
        if "highlightthickness" in kw:
            sel = int(kw.pop("highlightthickness")) > 0
            if sel != self._selected:
                self._selected = sel; changed = True
        if "highlightbackground" in kw:
            kw.pop("highlightbackground")
        if kw:
            super().config(**kw)
        if changed:
            self._draw()

    def pack(self, **kw):
        super().pack(**kw)

    def grid(self, **kw):
        super().grid(**kw)




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
                                    bg=BG_MID, fg=ACCENT, font=("Courier New", 10, "bold"))
        self._start_lbl.grid(row=0, column=1, padx=6, sticky="w")
        tk.Label(time_frm, text="Bitiş:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 9)).grid(row=0, column=2, sticky="w")
        self._end_lbl = tk.Label(time_frm, text=self._fmt_h(block.end, _sh),
                                  bg=BG_MID, fg=ACCENT, font=("Courier New", 10, "bold"))
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
                                relief="flat", font=("Courier New", 9),
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
                                  relief="flat", font=("Courier New", 9),
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

        self._btn_align_left = ColorButton(align_frm, text="◀ Sol",
            bg=ACCENT if cur_align == "left" else BG_PANEL,
            fg="#ffffff" if cur_align == "left" else TEXT_PRIMARY,
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=lambda: _set_align("left"))
        self._btn_align_left.pack(side="left", padx=(6, 2))

        self._btn_align_center = ColorButton(align_frm, text="■ Orta",
            bg=ACCENT if cur_align == "center" else BG_PANEL,
            fg="#ffffff" if cur_align == "center" else TEXT_PRIMARY,
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=lambda: _set_align("center"))
        self._btn_align_center.pack(side="left", padx=2)

        self._btn_align_right = ColorButton(align_frm, text="Sağ ▶",
            bg=ACCENT if cur_align == "right" else BG_PANEL,
            fg="#ffffff" if cur_align == "right" else TEXT_PRIMARY,
            font=("Arial", 8, "bold"), padx=6, pady=2,
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

        self._btn_txt_auto  = ColorButton(txt_color_frm, text="Oto",
            bg=ACCENT, fg="#ffffff",
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=_set_txt_auto)
        self._btn_txt_auto.pack(side="left", padx=(6, 2))
        self._btn_txt_black = ColorButton(txt_color_frm, text="■ Siyah",
            bg=BG_PANEL, fg="#000000",
            font=("Arial", 8, "bold"), padx=6, pady=2,
            cursor="hand2", command=_set_txt_black)
        self._btn_txt_black.pack(side="left", padx=2)
        self._btn_txt_white = ColorButton(txt_color_frm, text="□ Beyaz",
            bg="#cccccc", fg="#111111",
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

        def _make_sev_cmd(hex_color, captured_block=block):
            def _cmd():
                target = captured_block
                if not target:
                    return
                target.color = hex_color
                self._block = target
                try:
                    self._color_preview.config(fg=hex_color)
                    self._update_sev_buttons()
                except Exception:
                    pass
                self.app.timeline._sel = target.id
                self.app.timeline.redraw()
            return _cmd

        for row_i, (lbl, dark_hex, dark_fg, light_hex, light_fg) in enumerate(SEVERITY_ROWS):
            tk.Label(sev_grid, text=lbl, bg=BG_MID, fg=TEXT_PRIMARY,
                     font=("Arial", 8, "bold"), width=8, anchor="w"
                     ).grid(row=row_i, column=0, sticky="w", pady=2)
            btn_dark = ColorButton(sev_grid, text="(koyu)", bg=dark_hex, fg=dark_fg,
                                   font=("Arial", 7, "bold"),
                                   padx=6, pady=4, cursor="hand2", width=6,
                                   command=_make_sev_cmd(dark_hex))
            btn_dark.grid(row=row_i, column=1, padx=(4, 2), pady=2)
            self._sev_buttons.append((btn_dark, dark_hex))
            btn_light = ColorButton(sev_grid, text="(açık)", bg=light_hex, fg=light_fg,
                                    font=("Arial", 7, "bold"),
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
        ColorButton(btn_frm, text="✔ Kaydet", bg="#238636", fg="#ffffff",
                    font=("Arial", 9, "bold"), padx=10, pady=4,
                    command=self._save).pack(side="left", padx=(0, 6))
        ColorButton(btn_frm, text="✕ Sil", bg="#ffeef0", fg="#f85149",
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
    """Tıklanınca açılan checkbox menüsü.
    
    macOS uyumlu: Toplevel yerine ana pencerede place() ile yüzen Frame kullanır.
    Toplevel + focus_set() kombinasyonu macOS'ta pencereyi kilitliyordu.
    """

    def __init__(self, parent, var, options, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        self.var      = var
        self.options  = options
        self.chk_vars = {opt: tk.BooleanVar() for opt in options}
        self._popup   = None   # artık Toplevel değil, tk.Frame (place ile konumlandırılır)
        self._parse_current()

        # Dışarıdan var.set() ile değer atanınca checkbox'ları güncelle
        self.var.trace_add("write", self._on_var_changed)

        # Tıklanabilir buton satırı
        btn_row = tk.Frame(self, bg=BG_DARK,
                           highlightthickness=1, highlightbackground=BORDER)
        btn_row.pack(fill="x", expand=True)

        self._lbl = tk.Label(btn_row, text="(seçiniz...)",
                             bg=BG_DARK, fg=TEXT_MUTED, anchor="w",
                             font=("Courier New", 9), cursor="hand2",
                             padx=4, pady=3)
        self._lbl.pack(side="left", fill="x", expand=True)

        self._arrow = tk.Label(btn_row, text="▼", bg=BG_DARK, fg=TEXT_MUTED,
                               font=("Arial", 8), cursor="hand2", padx=4)
        self._arrow.pack(side="right")

        for w in (btn_row, self._lbl, self._arrow):
            w.bind("<Button-1>", lambda e: self._toggle())

        self._update_btn_text()

    def _parse_current(self):
        current = self.var.get()
        if current:
            items = [x.strip() for x in current.split(",")]
            for opt in self.options:
                self.chk_vars[opt].set(opt in items)

    def _on_var_changed(self, *args):
        """Dışarıdan var.set() çağrılınca checkbox'ları ve buton metnini güncelle."""
        self._parse_current()
        self._update_btn_text()

    def _update_btn_text(self):
        selected = [opt for opt in self.options if self.chk_vars[opt].get()]
        if not selected:
            self._lbl.config(fg=TEXT_MUTED, text="(seçiniz...)")
            self._arrow.config(text="▼")
        else:
            txt = ", ".join(selected)
            if len(txt) > 40:
                txt = ", ".join(selected[:2]) + f"  +{len(selected)-2} daha"
            self._lbl.config(fg=TEXT_PRIMARY, text=txt)
            self._arrow.config(text="▲" if self._popup else "▼")

    def _toggle(self):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self):
        # En üst seviye pencereyi bul (winfo_toplevel)
        root = self.winfo_toplevel()

        # Popup frame — root üzerinde place() ile konumlandırılır
        self._popup = tk.Frame(root, bg=BG_DARK,
                               highlightthickness=1, highlightbackground=BORDER,
                               relief="flat")

        # Seçenek satırları
        for opt in self.options:
            row = tk.Frame(self._popup, bg=BG_DARK, cursor="hand2")
            row.pack(fill="x", pady=1, padx=6)

            var = self.chk_vars[opt]
            indicator = tk.Label(row, text="✓" if var.get() else " ", width=2,
                                 bg=ACCENT if var.get() else BG_PANEL,
                                 fg="white", font=("Arial", 9, "bold"),
                                 relief="flat")
            indicator.pack(side="left", padx=(0, 6))

            lbl = tk.Label(row, text=opt, bg=BG_DARK, fg=TEXT_PRIMARY,
                           font=("Arial", 9), anchor="w")
            lbl.pack(side="left", fill="x", expand=True)

            def _make_toggle(o=opt, ind=indicator):
                def _tog(e=None):
                    new_val = not self.chk_vars[o].get()
                    self.chk_vars[o].set(new_val)
                    ind.config(bg=ACCENT if new_val else BG_PANEL,
                               text="✓" if new_val else " ")
                    self._on_change()
                return _tog

            fn = _make_toggle()
            for w in (row, indicator, lbl):
                w.bind("<Button-1>", fn)

        # Kapat butonu
        close_row = tk.Frame(self._popup, bg=BG_MID)
        close_row.pack(fill="x", pady=(4, 2), padx=6)
        tk.Label(close_row, text="── Kapat ──", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 8), cursor="hand2").pack(
                     fill="x", expand=True, pady=2)
        close_row.bind("<Button-1>", lambda e: self._close_popup())
        close_row.winfo_children()[0].bind("<Button-1>", lambda e: self._close_popup())

        # Konumu hesapla: self widget'ın root üzerindeki mutlak konumu
        self.update_idletasks()
        x = self.winfo_rootx() - root.winfo_rootx()
        y = self.winfo_rooty() - root.winfo_rooty() + self.winfo_height() + 2

        popup_w = max(self.winfo_width(), 260)
        self._popup.place(x=x, y=y, width=popup_w)
        self._popup.lift()   # diğer widget'ların üstüne çık

        # ok yönünü güncelle
        self._arrow.config(text="▲")

        # Ana penceredeki herhangi bir tıklamayı yakala → popup'ı kapat
        root.bind("<Button-1>", self._on_root_click, add="+")

    def _on_root_click(self, e):
        """Ana pencerede popup dışına tıklanınca kapat — focus sorunu yok."""
        if not self._popup or not self._popup.winfo_exists():
            self._unbind_root()
            return
        # Tıklanan widget popup içinde mi?
        w = e.widget
        while w is not None:
            if w == self._popup:
                return   # popup içi tıklama — kapatma
            try:
                w = w.master
            except Exception:
                break
        self._close_popup()

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        self._arrow.config(text="▼")
        self._unbind_root()

    def _unbind_root(self):
        try:
            self.winfo_toplevel().unbind("<Button-1>")
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
                         "CB bulutu", "LVO (Düşük Görüş)", "Dolu", "Windshear", "Kar yağışı"]

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
                          relief="flat", font=("Courier New", 9),
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
        dropdown._lbl.config(width=52)  # dropdown etiket genişliği

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
                          relief="flat", font=("Courier New", 9),
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
                                   relief="flat", font=("Courier New", 9, "bold", "italic"),
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
        self._apply_style()   # macOS renk düzeltmesi build_ui'dan önce gelmeli
        self._build_ui()

    def _apply_style(self):
        import platform
        style = ttk.Style(self)
        # macOS'ta "clam" teması tk renklerini düzgün uygular;
        # varsayılan "aqua" teması bg/fg'yi yok sayar.
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass  # tema yoksa aqua'da devam et
        style.configure("TCombobox",
                         fieldbackground=BG_DARK, background=BG_DARK,
                         foreground=TEXT_PRIMARY, arrowcolor=TEXT_MUTED,
                         selectbackground=BG_PANEL)
        style.configure("TSpinbox",
                         fieldbackground=BG_DARK, background=BG_DARK,
                         foreground=ACCENT, arrowcolor=TEXT_MUTED,
                         selectbackground=BG_PANEL)
        # macOS'ta tk.Button renkleri ancak bu seçenek ile çalışır
        if platform.system() == "Darwin":
            self.option_add("*Button.highlightBackground", BG_MID)
            self.option_add("*Button.background", BG_PANEL)
            self.option_add("*Button.foreground", TEXT_PRIMARY)
            self.option_add("*Label.background", BG_MID)
            self.option_add("*Frame.background", BG_MID)
            # Spinbox metin rengi
            self.option_add("*Spinbox.foreground", ACCENT)
            self.option_add("*Spinbox.background", BG_DARK)

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
            ColorButton(top, text=lbl, command=cmd,
                        bg=BG_PANEL, fg=TEXT_PRIMARY,
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
                              width=4, font=("Courier New", 12, "bold"),
                              bg=BG_DARK, fg=ACCENT, relief="flat",
                              highlightthickness=1, highlightbackground=BORDER,
                              format="%02.0f", increment=1)
        sh_spin.pack(side="left")
        tk.Label(sh_frm, text="Z", bg=BG_MID, fg=ACCENT,
                 font=("Courier New", 12, "bold")).pack(side="left", padx=(1, 16))
        self._start_hour_var.trace_add("write", self._on_start_hour_change)

        # Zaman çizelgesi süresi
        tk.Label(sh_frm, text="Zaman Çizelgesi Süresi:", bg=BG_MID, fg=TEXT_MUTED,
                 font=("Arial", 10, "bold")).pack(side="left", padx=(0, 4))
        self._hours_shown_var = tk.IntVar(value=HOURS_SHOWN)
        hs_spin = tk.Spinbox(sh_frm, from_=1, to=HOURS_MAX, textvariable=self._hours_shown_var,
                              width=4, font=("Courier New", 12, "bold"),
                              bg=BG_DARK, fg=ACCENT, relief="flat",
                              highlightthickness=1, highlightbackground=BORDER,
                              format="%02.0f", increment=1)
        hs_spin.pack(side="left")
        tk.Label(sh_frm, text="saat", bg=BG_MID, fg=ACCENT,
                 font=("Courier New", 12, "bold")).pack(side="left", padx=(2, 4))
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
            h = int(self._start_hour_var.get())
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
        self.timeline.delete_selected()

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

        meta = data.get("meta", {})

        # Tarihe bağımlı OLMAYAN alanları dosyadan yükle
        DATE_FIELDS = {"tarih", "bas_tar", "bit_tar"}
        for fid, val in meta.items():
            if fid not in DATE_FIELDS and fid in self.meta._vars:
                self.meta._vars[fid].set(val)

        # Tarihe bağımlı alanları BUGÜNÜN tarihiyle yeniden hesapla
        today_dt  = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = today_dt.strftime("%d.%m.%Y")

        # Hazırlanma tarihi → bugün
        if "tarih" in self.meta._vars:
            self.meta._vars["tarih"].set(today_str)

        # Blokları yükle
        blocks = [Block.from_dict(d) for d in data.get("blocks", [])]
        self.timeline.blocks = blocks

        # Geçerlilik periyodu → blokların pozisyonundan + start_hour'dan hesapla
        start_hour = self.timeline.start_hour
        if blocks:
            min_start = min(b.start for b in blocks)
            max_end   = max(b.end   for b in blocks)
            bas_dt  = today_dt + timedelta(hours=start_hour + min_start)
            bit_dt  = today_dt + timedelta(hours=start_hour + max_end)
            bas_str = bas_dt.strftime("%d.%m.%Y %H:%M")
            bit_str = bit_dt.strftime("%d.%m.%Y %H:%M")
        else:
            bas_str = today_str + " 00:00"
            bit_str = (today_dt + timedelta(days=1)).strftime("%d.%m.%Y") + " 00:00"

        if "bas_tar" in self.meta._vars:
            self.meta._vars["bas_tar"].set(bas_str)
        if "bit_tar" in self.meta._vars:
            self.meta._vars["bit_tar"].set(bit_str)

        # Diğer metin alanları
        self.sinoptik_text.delete("1.0", "end")
        self.sinoptik_text.insert("1.0", data.get("sinoptik", ""))
        self.olay_takip_text.delete("1.0", "end")
        self.olay_takip_text.insert("1.0", data.get("olay_takip", ""))

        self.timeline._sel = None
        self.close_editor()
        self.timeline.redraw()   # redraw → refresh_analiz() tetiklenir → analiz güncel tarihe göre yenilenir
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
        start_hour_offset = self._start_hour_var.get()

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
               self._start_hour_var.get(), self.timeline.hours_shown)
            
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