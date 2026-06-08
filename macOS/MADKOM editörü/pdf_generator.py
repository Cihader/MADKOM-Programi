# ──────────────────────────── PDF üretici ────────────────────────────────
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics  # Eksik import eklendi
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect

# Eğer ana kodda farklı bir saat sayısı varsa burayı değiştirebilirsin (Örn: 24)
HOURS_SHOWN = 24

def _build_pdf(path, meta, layers, signature="", unvan="",
               analiz="", blocks=None, start_hour=0, hours_shown=HOURS_SHOWN):
    from reportlab.platypus import Flowable

    blocks = blocks or []

    # ── Font kaydı ──────────────────────────────────────────────────────
    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    # Türkçe karakter desteği için font arama sırası
    font_candidates = [
        # ── Windows ──────────────────────────────────────────────────────
        (("C:/Windows/Fonts/DejaVuSans.ttf",
          "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
         ("DejaVu", "DejaVu-Bold")),
        (("C:/Windows/Fonts/arial.ttf",
          "C:/Windows/Fonts/arialbd.ttf"),
         ("Arial_TR", "Arial_TR-Bold")),
        # ── macOS — yaygın Arial konumları ───────────────────────────────
        (("/Library/Fonts/Arial.ttf",
          "/Library/Fonts/Arial Bold.ttf"),
         ("Arial_TR", "Arial_TR-Bold")),
        (("/System/Library/Fonts/Supplemental/Arial.ttf",
          "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
         ("Arial_TR", "Arial_TR-Bold")),
        # macOS — Homebrew veya manuel kurulan DejaVu (Apple Silicon)
        (("/opt/homebrew/share/fonts/dejavu-fonts/DejaVuSans.ttf",
          "/opt/homebrew/share/fonts/dejavu-fonts/DejaVuSans-Bold.ttf"),
         ("DejaVu", "DejaVu-Bold")),
        # macOS — Intel Mac / eski Homebrew konumu
        (("/usr/local/share/fonts/DejaVuSans.ttf",
          "/usr/local/share/fonts/DejaVuSans-Bold.ttf"),
         ("DejaVu", "DejaVu-Bold")),
        # macOS — Kullanıcı font klasörü
        ((os.path.expanduser("~/Library/Fonts/Arial.ttf"),
          os.path.expanduser("~/Library/Fonts/Arial Bold.ttf")),
         ("Arial_TR", "Arial_TR-Bold")),
        ((os.path.expanduser("~/Library/Fonts/DejaVuSans.ttf"),
          os.path.expanduser("~/Library/Fonts/DejaVuSans-Bold.ttf")),
         ("DejaVu", "DejaVu-Bold")),
        # ── Linux ─────────────────────────────────────────────────────────
        (("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
         ("DejaVu", "DejaVu-Bold")),
        (("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
          "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
         ("Liberation", "Liberation-Bold")),
    ]
    for paths, names in font_candidates:
        try:
            pdfmetrics.registerFont(TTFont(names[0], paths[0]))
            pdfmetrics.registerFont(TTFont(names[1], paths[1]))
            font_name, font_bold = names
            break
        except Exception:
            pass

    # ── Sayfa ve stiller ────────────────────────────────────────────────
    LEFT_M  = 1.1*cm
    RIGHT_M = 1.1*cm
    doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                            topMargin=1.1*cm, bottomMargin=0.6*cm,
                            leftMargin=LEFT_M, rightMargin=RIGHT_M)
    page_w = landscape(A4)[0] - LEFT_M - RIGHT_M

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=styles["Normal"],
                            fontName=font_name, fontSize=10, leading=13)
    bold   = ParagraphStyle("b", parent=normal, fontName=font_bold)
    title  = ParagraphStyle("t", parent=normal, fontName=font_bold,
                            fontSize=13, alignment=1)

    # ── Zaman Çizelgesi Flowable ─────────────────────────────────────────
    class TimelineDrawing(Flowable):
        LK = ["ruzgar", "gorus", "hadise", "oraj", "bulut"]
        LL = {"ruzgar": "RÜZGAR", "gorus": "GÖRÜŞ", "hadise": "HADİSE", "oraj": "ORAJ/TS", "bulut": "BULUT"}
        LC = {
            "ruzgar": colors.HexColor("#0969da"),
            "gorus":  colors.HexColor("#0969da"),
            "hadise": colors.HexColor("#0969da"),
            "oraj":   colors.HexColor("#0969da"),
            "bulut":  colors.HexColor("#0969da"),
        }
        LABEL_W = 58
        ROW_H   = 28
        AXIS_H  = 22
        PAD     = 2

        def __init__(self, blks, sh, pw):
            Flowable.__init__(self)
            self.hAlign = 'CENTER'
            self.blks  = blks
            self.sh    = sh
            self.hs    = hours_shown   # gösterilen saat sayısı
            self.width = pw
            self.height = len(self.LK) * self.ROW_H + self.AXIS_H + 4
            # Başlangıç tarihi (bugün UTC + başlangıç saati)
            _base = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            self.start_dt = _base + timedelta(hours=sh)

        def _tw(self):
            return self.width - self.LABEL_W

        def _h2x(self, h):
            return self.LABEL_W + (h / self.hs) * self._tw()

        def _hex(self, hx):
            try:
                return colors.HexColor(hx) if hx else None
            except Exception:
                return None

        def draw(self):
            c = self.canv
            tw = self._tw()
            n  = len(self.LK)

            c.setFillColor(colors.white)
            c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

            for i, key in enumerate(self.LK):
                y_bot = self.AXIS_H + (n - 1 - i) * self.ROW_H

                # Etiket hücresi
                c.setFillColor(colors.HexColor("#f0f2f5"))
                c.setStrokeColor(colors.HexColor("#d0d7de"))
                c.setLineWidth(0.5)
                c.rect(0, y_bot, self.LABEL_W - 2, self.ROW_H, fill=1, stroke=1)
                c.setFillColor(colors.HexColor("#24292f"))
                c.setFont(font_bold, 7.5)
                c.drawCentredString((self.LABEL_W - 2) / 2, y_bot + self.ROW_H/2 - 3,
                                    self.LL[key])

                # İz arka plan
                c.setFillColor(colors.HexColor("#f6f8fa"))
                c.setStrokeColor(colors.HexColor("#d0d7de"))
                c.rect(self.LABEL_W, y_bot, tw, self.ROW_H, fill=1, stroke=1)

                # Sadece gün değişimi (gece yarısı) kırmızı çizgisi — saat kılavuzları kaldırıldı
                for h in range(self.hs + 1):
                    abs_h = (self.sh + h) % 24
                    x = self._h2x(h)
                    is_mid = (abs_h == 0 and h > 0)
                    if is_mid:
                        c.setStrokeColor(colors.HexColor("#cc0000"))
                        c.setLineWidth(1.2)
                        c.line(x, y_bot, x, y_bot + self.ROW_H)

                # Bloklar
                for b in [b for b in self.blks if b.layer == key]:
                    x1 = self._h2x(b.start)
                    x2 = self._h2x(b.end)
                    bw = max(x2 - x1, 1)
                    blk_col = self._hex(b.color) if b.color else self.LC[key]
                    c.setFillColor(blk_col)
                    c.setStrokeColor(blk_col)
                    c.setLineWidth(0)
                    c.rect(x1, y_bot + self.PAD, bw, self.ROW_H - self.PAD*2, fill=1, stroke=0)
                    lbl = b.fields.get("etiket", "")
                    if lbl and bw > 12:
                        if b.text_color:
                            c.setFillColor(colors.HexColor(b.text_color))
                        else:
                            r2, g2, b2 = blk_col.red, blk_col.green, blk_col.blue
                            lum = 0.299*r2 + 0.587*g2 + 0.114*b2
                            c.setFillColor(colors.white if lum < 0.55 else colors.HexColor("#24292f"))
                        align = getattr(b, "label_align", "center")
                        y_txt = y_bot + self.ROW_H/2 - 3.5
                        # Font boyutunu küçülterek metni bloğa sığdır
                        for fs in (7.5, 6.5, 5.5):
                            c.setFont(font_bold, fs)
                            avg_char_w = fs * 0.55
                            max_c = max(1, int((bw - 6) / avg_char_w))
                            if len(lbl) <= max_c:
                                disp = lbl
                                break
                        else:
                            disp = lbl[:max_c-1] + "~"
                        if align == "left":
                            c.drawString(x1 + 3, y_txt, disp)
                        elif align == "right":
                            c.drawRightString(x1 + bw - 3, y_txt, disp)
                        else:
                            c.drawCentredString(x1 + bw/2, y_txt, disp)

            # Saat ekseni
            c.setFillColor(colors.HexColor("#f0f2f5"))
            c.setStrokeColor(colors.HexColor("#d0d7de"))
            c.setLineWidth(0.5)
            c.rect(0, 0, self.LABEL_W - 2, self.AXIS_H, fill=1, stroke=1)
            c.setFillColor(colors.HexColor("#6a737d"))
            c.setFont(font_bold, 8.5)
            c.drawCentredString((self.LABEL_W - 2)/2, self.AXIS_H/2 - 3, "Periyot")

            c.setFillColor(colors.HexColor("#f6f8fa"))
            c.rect(self.LABEL_W, 0, tw, self.AXIS_H, fill=1, stroke=1)

            cell_w = tw / self.hs
            for h in range(self.hs + 1):
                abs_h = (self.sh + h) % 24
                x = self._h2x(h)
                is_mid = (abs_h == 0 and h > 0)
                if is_mid:
                    cur_dt = self.start_dt + timedelta(hours=h)
                    day_lbl = f"{cur_dt.day:02d}"
                    c.setFillColor(colors.HexColor("#fff0f0"))
                    c.rect(x, 0, cell_w, self.AXIS_H, fill=1, stroke=0)
                    c.setStrokeColor(colors.HexColor("#cc0000"))
                    c.setLineWidth(1.2)
                    c.line(x, 0, x, self.AXIS_H)
                    c.setFillColor(colors.HexColor("#cc0000"))
                    c.setFont(font_bold, 7)
                    c.drawCentredString(x + cell_w/2, self.AXIS_H - 7.5, day_lbl)
                    c.setFont(font_bold, 7.5)
                    c.drawCentredString(x + cell_w/2, 2.5, f"{abs_h:02d}Z")
                else:
                    c.setStrokeColor(colors.HexColor("#d0d7de"))
                    c.setLineWidth(0.3)
                    c.line(x, 0, x, self.AXIS_H)
                    if h < self.hs:
                        c.setFillColor(colors.HexColor("#6a737d"))
                        c.setFont("Helvetica", 7)
                        c.drawCentredString(x + cell_w/2, self.AXIS_H/2 - 3.5, f"{abs_h:02d}Z")

            # Dış kenarlık
            c.setStrokeColor(colors.black)
            c.setLineWidth(1.5)
            c.rect(0, 0, self.width, self.height, fill=0, stroke=1)

    # ── TÜRKÇE KARAKTER DOSTU BÜYÜTME FONKSİYONU ────────────────────────
    def turkce_upper(metin):
        if not metin:
            return ""
        harfler = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
        for kucuk, buyuk in harfler.items():
            metin = metin.replace(kucuk, buyuk)
        return metin.upper()
    # ── TÜRKÇE KARAKTER VE KELİME DÜZELTMELİ BAŞ HARF BÜYÜTME FONKSİYONU ──
    def turkce_title(metin):
        if not metin:
            return ""
            
        # 1. Kullanıcının yazabileceği olası harf hatalarını otomatik düzeltiyoruz
        metin = metin.replace("Havalmanı", "Havalimanı")
        metin = metin.replace("havalmanı", "havalimanı")
        metin = metin.replace("Meteorolojı", "Meteoroloji")
        metin = metin.replace("meteorolojı", "meteoroloji")
        
        # 2. Tüm metni Türkçe kurallarına göre geçici olarak küçük harfe çeviriyoruz
        kucuk_harfler = {"İ": "i", "I": "ı", "Ğ": "ğ", "Ü": "ü", "Ş": "ş", "Ö": "ö", "Ç": "ç"}
        metin = turkce_upper(metin)
        for buyuk, kucuk in kucuk_harfler.items():
            metin = metin.replace(buyuk, kucuk)
        metin = metin.lower()
        
        # 3. Kelimelerin sadece ilk harflerini Türkçe uyumlu olarak büyütüyoruz
        kelimeler = metin.split()
        donusen_kelimeler = []
        
        for kelime in kelimeler:
            if not kelime:
                continue
            bas_harf = kelime[0]
            bas_harf_eslesme = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
            bas_harf = bas_harf_eslesme.get(bas_harf, bas_harf.upper())
            
            donusen_kelimeler.append(bas_harf + kelime[1:])
            
        return " ".join(donusen_kelimeler)
    # ── Başlık tablosu ──────────────────────────────────────────────────
    from reportlab.platypus import Image as RLImage

    # Platformdan bağımsız logo yolu: Windows ve macOS masaüstü desteklenir
    _desktop = os.path.join(os.path.expanduser("~"), "Desktop", "MADKOM editörü")
    LOGO_PATH = os.path.join(_desktop, "MGM-logosu.png")
    # Windows sabit yolu (fallback)
    if not os.path.exists(LOGO_PATH):
        LOGO_PATH = r"C:\Users\cihader\Desktop\MADKOM editörü\MGM-logosu.png"
    LOGO_COL_W = 2.4 * cm

    # Logo hücresi: dosya varsa Image, yoksa boş string
    if os.path.exists(LOGO_PATH):
        logo_cell = RLImage(LOGO_PATH, width=1.8*cm, height=1.8*cm)
    else:
        logo_cell = ""

    header_bold = ParagraphStyle("hb", parent=bold, fontSize=11, alignment=1, leading=15)

    header_data = [[
        logo_cell,
        Paragraph("<b>METEOROLOJİ GENEL MÜDÜRLÜĞÜ<br/>"
                  f"{turkce_upper(meta.get('kurum', 'İstanbul Havalimanı Meteoroloji Müdürlüğü'))}</b>", header_bold),
        Paragraph("<b>MADKOM ANALİZ VE TAHMİN RAPORU</b>", title),
    ]]
    header_tbl = Table(header_data,
                       colWidths=[LOGO_COL_W, page_w*0.45, page_w - LOGO_COL_W - page_w*0.45])
    header_tbl.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 0.75, colors.black),
        ("INNERGRID",    (0,0),(-1,-1), 0.5,  colors.black),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("ALIGN",        (0,0),(0, 0),  "CENTER"),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("TOPPADDING",   (0,0),(2,0), 5),
        ("BOTTOMPADDING",(0,0),(2,0), 5),
        ("LEFTPADDING",  (0,0),(-1,-1), 6),
    ]))

    # ── Türkçe gün adı yardımcısı ────────────────────────────────────────
    TR_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

    def _gun_adli_tarih(tarih_str):
        """'DD.MM.YYYY HH:MM' veya 'DD.MM.YYYY' stringine gün adı ekler.
        Örnek: '23.05.2026' → '23.05.2026 Cumartesi'
               '16.05.2026 15:00' → '16.05.2026 Cumartesi 15:00Z'
        """
        if not tarih_str or tarih_str in ("Belirtilmedi",):
            return tarih_str
        try:
            parcalar = tarih_str.strip().split()
            gun_kismi = parcalar[0]          # DD.MM.YYYY
            saat_kismi = parcalar[1] if len(parcalar) > 1 else None
            dt = datetime.strptime(gun_kismi, "%d.%m.%Y")
            gun_adi = TR_GUNLER[dt.weekday()]
            if saat_kismi:
                # Saat varsa 'Z' ekle (eğer henüz yoksa)
                saat_z = saat_kismi if saat_kismi.endswith("Z") else saat_kismi + "Z"
                return f"{gun_kismi} {gun_adi} {saat_z}"
            else:
                return f"{gun_kismi} {gun_adi}"
        except Exception:
            return tarih_str

    # ── Üst bilgi tablosu ───────────────────────────────────────────────
    info_data = [
        ["Meteorolojik Olaylar",
         Paragraph(f"<b><font color='#cc6600'>{meta.get('olay','')}</font></b>", bold)],
        
        ["Hazırlayan Birim",
         Paragraph(f"{turkce_title(meta.get('kurum', 'İstanbul Havalimanı Meteoroloji Müdürlüğü'))}", normal)],
        ["Hazırlama Tarihi", 
         Paragraph(f"{_gun_adli_tarih(meta.get('tarih',''))}", normal)],
        ["Geçerlilik Periyodu",
         Paragraph(f"<u><b>{_gun_adli_tarih(meta.get('periyot_baslangic','Belirtilmedi'))} - {_gun_adli_tarih(meta.get('periyot_bitis','Belirtilmedi'))}</b></u>", bold)],
    ]
    
    info_tbl = Table(info_data, colWidths=[page_w*0.22, page_w*0.78])
    info_tbl.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 0.75, colors.black),
        ("INNERGRID",    (0,0),(-1,-1), 0.5,  colors.black),
        ("BACKGROUND",   (0,0),(0,-1),  colors.Color(0.94,0.94,0.94)),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0),(-1,-1), 2),
        ("BOTTOMPADDING",(0,0),(-1,-1), 2),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("FONTNAME",     (0,0),(0,-1),  font_bold),
        ("FONTSIZE",     (0,0),(-1,-1), 10),
    ]))

    # ── Alt bilgi tablosu ────────────────────────────────────────────────
    # Hava analizi: her satır "Katman: ..." biçiminde —
    # katman adı kalın+altı çizili olarak render edilir
    analiz_lines = (analiz or "-").strip().split("\n")
    analiz_html_parts = []
    layer_names = ["Rüzgar", "Görüş", "Hadise", "Oraj/TS", "Bulut"]
    for line in analiz_lines:
        rendered = False
        for ln in layer_names:
            prefix = ln + ":"
            if line.startswith(prefix):
                rest = line[len(prefix):]
                analiz_html_parts.append(
                    f"<b><u>{ln}</u></b>:{rest}")
                rendered = True
                break
        if not rendered:
            analiz_html_parts.append(line if line else "-")
    analiz_html = "<br/>".join(analiz_html_parts) if analiz_html_parts else "-"
    analiz_style = ParagraphStyle("analiz_fit", parent=normal,
                                   fontSize=10, leading=14, wordWrap='LTR')
    bottom_data = []

    sinoptik_val = (meta.get("sinoptik") or "").strip()
    if sinoptik_val:
        sinoptik_html = sinoptik_val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        bottom_data.append(["Sinoptik Durum De\u011flendirmesi",
                             Paragraph(sinoptik_html, analiz_style)])

    bottom_data += [
        ["Hava Analizi ve Yorumu",
         Paragraph(analiz_html, analiz_style)],
        ["Olay Takibi ve Bilgi",
         Paragraph("<i>" + (meta.get("olay_takip") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>") + "</i>", normal)],
    ]
    bottom_tbl = Table(bottom_data, colWidths=[page_w*0.22, page_w*0.78])
    bottom_tbl.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 0.75, colors.black),
        ("INNERGRID",    (0,0),(-1,-1), 0.5,  colors.black),
        ("BACKGROUND",   (0,0),(0,-1),  colors.Color(0.94,0.94,0.94)),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",   (0,0),(-1,-1), 2),
        ("BOTTOMPADDING",(0,0),(-1,-1), 2),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("FONTNAME",     (0,0),(0,-1),  font_bold),
        ("FONTSIZE",     (0,0),(-1,-1), 10),
    ]))

    # ── Legend (sol alt köşe, canvas callback ile) ───────────────────────
    legend_items = [
        # (fill_hex, stroke_hex, label)
        ("#0969da", "#0969da", "Hafif"),    # mavi (default)
        ("#07fb03", "#049104", "Hafif"),    # yeşil açık
        ("#049104", "#026602", "Hafif"),    # yeşil koyu
        ("#fff507", "#fe9601", "Orta"),     # sarı açık
        ("#fe9601", "#b86b00", "Orta"),     # turuncu koyu
        ("#f60003", "#cd0102", "Kuvvetli"), # kırmızı açık
        ("#cd0102", "#8b0000", "Kuvvetli"), # kırmızı koyu
        ("#cc66cc", "#993399", "Şiddetli"), # mor açık
        ("#993399", "#662266", "Şiddetli"), # mor koyu
    ]

    # Boyutlar
    BOX_W  = 13   # kutucuk genişliği
    BOX_H  = 13   # kutucuk yüksekliği
    GAP    = 3    # kutucuk ile etiket arası
    SEP    = 12   # grup arası ekstra boşluk
    ITEM_GAP = 3  # aynı gruptaki öğeler arası

    def _draw_legend_bottom_left(canvas_obj, doc_obj):
        """Her sayfanın sol alt köşesine legend + iletişim kutusu çizer."""
        margin_x = LEFT_M
        margin_y = 0.75 * cm
        FONT_SZ   = 9.5
        PAD_X     = 6
        PAD_Y     = 5

        canvas_obj.saveState()

        # Grupları belirle
        groups = []
        prev_label = None
        cur_group = []
        for item in legend_items:
            fill, stroke, label = item
            if label != prev_label:
                if cur_group:
                    groups.append((prev_label, cur_group))
                cur_group = [(fill, stroke)]
                prev_label = label
            else:
                cur_group.append((fill, stroke))
        if cur_group:
            groups.append((prev_label, cur_group))

        # İçerik genişliğini hesapla
        total_content_w = 0
        for g_idx, (glabel, g_items) in enumerate(groups):
            for _ in g_items:
                total_content_w += BOX_W + ITEM_GAP
            total_content_w -= ITEM_GAP
            total_content_w += GAP
            total_content_w += canvas_obj.stringWidth(glabel, font_name, FONT_SZ)
            total_content_w += SEP
        total_content_w -= SEP

        box_h = BOX_H + PAD_Y * 2
        legend_box_w = total_content_w + PAD_X * 2

        # ── Legend çerçeve kutusu ──
        canvas_obj.setFillColor(HexColor("#f6f8fa"))
        canvas_obj.setStrokeColor(HexColor("#d0d7de"))
        canvas_obj.setLineWidth(0.75)
        canvas_obj.rect(margin_x, margin_y, legend_box_w, box_h, fill=1, stroke=1)

        # İçeriği çiz
        x = margin_x + PAD_X
        y = margin_y + PAD_Y
        for g_idx, (glabel, g_items) in enumerate(groups):
            for b_idx, (fill, stroke) in enumerate(g_items):
                canvas_obj.setFillColor(HexColor(fill))
                canvas_obj.setStrokeColor(HexColor(stroke))
                canvas_obj.setLineWidth(0.6)
                canvas_obj.rect(x, y, BOX_W, BOX_H, fill=1, stroke=1)
                x += BOX_W + ITEM_GAP
            x -= ITEM_GAP
            x += GAP
            canvas_obj.setFillColor(HexColor("#24292f"))
            canvas_obj.setFont(font_name, FONT_SZ)
            text_y = y + BOX_H / 2 - FONT_SZ * 0.35
            canvas_obj.drawString(x, text_y, glabel)
            label_w = canvas_obj.stringWidth(glabel, font_name, FONT_SZ)
            x += label_w + SEP

        # ── İletişim kutusu (legend'in hemen sağında, aynı hizada) ──
        iletisim_num = meta.get("iletisim", "(0212) 812 8316 / (16496)")
        ILET_PAD_X    = 6
        ILET_FONT_LBL = FONT_SZ        # legend etiketleriyle aynı boyut, bold
        ILET_FONT_NUM = FONT_SZ        # aynı boyut, normal italic
        ILET_GAP      = 4

        # İtalik font: DejaVu varsa DejaVu-Oblique yoksa Helvetica-Oblique
        try:
            italic_font = font_name + "-Oblique"
            canvas_obj.setFont(italic_font, ILET_FONT_NUM)
        except Exception:
            italic_font = "Helvetica-Oblique"

        lbl_text = "İletişim:"
        lbl_w    = canvas_obj.stringWidth(lbl_text, font_bold, ILET_FONT_LBL)
        num_w    = canvas_obj.stringWidth(iletisim_num, italic_font, ILET_FONT_NUM)
        ilet_content_w = lbl_w + ILET_GAP + num_w
        ilet_box_w = ilet_content_w + ILET_PAD_X * 2
        ilet_x = margin_x + legend_box_w + 16

        canvas_obj.setFillColor(HexColor("#f6f8fa"))
        canvas_obj.setStrokeColor(HexColor("#d0d7de"))
        canvas_obj.setLineWidth(0.75)
        canvas_obj.rect(ilet_x, margin_y, ilet_box_w, box_h, fill=1, stroke=1)

        cx     = ilet_x + ILET_PAD_X
        cy_mid = margin_y + box_h / 2

        canvas_obj.setFillColor(HexColor("#24292f"))
        canvas_obj.setFont(font_bold, ILET_FONT_LBL)
        canvas_obj.drawString(cx, cy_mid - ILET_FONT_LBL * 0.35, lbl_text)

        canvas_obj.setFont(italic_font, ILET_FONT_NUM)
        canvas_obj.drawString(cx + lbl_w + ILET_GAP, cy_mid - ILET_FONT_NUM * 0.35, iletisim_num)

        canvas_obj.restoreState()

    doc.build(
        [
            header_tbl,
            Spacer(1, 0.1*cm),
            info_tbl,
            Spacer(1, 0.1*cm),
            TimelineDrawing(blocks, start_hour, page_w),
            Spacer(1, 0.1*cm),
            bottom_tbl,
        ],
        onFirstPage=_draw_legend_bottom_left,
        onLaterPages=_draw_legend_bottom_left,
    )

# ─────────────────────────────── Giriş ──────────────────────────────────

if __name__ == "__main__":
    app = MatkomApp()
    app.mainloop()