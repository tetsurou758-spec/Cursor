"""
更改おすすめプラン通知書PDF生成モジュール
ReportLab + Font Awesome SVG（svglib経由）を使用

FAアイコンはreports/icons/solid/ のSVGファイルをsvglibで読み込み
ReportLab Drawingとして埋め込む。
"""

import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, Flowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

# ── フォント登録 ──────────────────────────────────────────────────────────────

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons", "solid")

_JP_FONT_PATHS = [
    r"C:\Windows\Fonts\meiryo.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
    r"C:\Windows\Fonts\YuGothR.ttc",
]

def _register_fonts():
    for path in _JP_FONT_PATHS:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("JP",      path))
            pdfmetrics.registerFont(TTFont("JP-Bold", path))
            registerFontFamily("JP",
                               normal="JP", bold="JP-Bold",
                               italic="JP", boldItalic="JP-Bold")
            return
    raise RuntimeError("日本語フォントが見つかりません")

_register_fonts()

# ── SVGアイコン名マップ ───────────────────────────────────────────────────────

SVG = {
    "car":         "car.svg",
    "car_burst":   "car-burst.svg",
    "person_fall": "person-falling.svg",
    "fire":        "fire.svg",
    "bandage":     "bandage.svg",
    "scale":       "scale-balanced.svg",
    "shield":      "shield-halved.svg",
    "globe":       "globe.svg",
    "coins":       "coins.svg",
    "house":       "house.svg",
    "arrow_up":    "arrow-up.svg",
}

POLICY_SVG = {
    "自動車":         SVG["car"],
    "火災":           SVG["house"],
    "傷害":           SVG["bandage"],
    "自賠責":         SVG["car"],
    "賠償責任":       SVG["shield"],
    "サイバーリスク": SVG["globe"],
    "所得補償":       SVG["coins"],
}

# SVG Drawingキャッシュ
_svg_cache: dict = {}

def _load_svg(svg_filename: str):
    if svg_filename in _svg_cache:
        return _svg_cache[svg_filename]
    path = os.path.join(_ICONS_DIR, svg_filename)
    if not os.path.exists(path):
        _svg_cache[svg_filename] = None
        return None
    drawing = svg2rlg(path)
    _svg_cache[svg_filename] = drawing
    return drawing

# ── 色定義 ────────────────────────────────────────────────────────────────────

COLOR_NAVY   = colors.HexColor("#003366")
COLOR_ACCENT = colors.HexColor("#C8960C")
COLOR_UP     = colors.HexColor("#cc0000")
COLOR_GRAY   = colors.HexColor("#f5f5f5")
COLOR_BORDER = colors.HexColor("#cccccc")
COLOR_HEADER = colors.HexColor("#e8eef7")

# ── SVGアイコンFlowable ───────────────────────────────────────────────────────

class SVGIcon(Flowable):
    """Font Awesome SVGをスケーリングして描画するFlowable"""

    def __init__(self, svg_filename: str, size: float = 10):
        Flowable.__init__(self)
        self._svg_file = svg_filename
        self._size     = size
        self.width     = size
        self.height    = size

    def draw(self):
        drawing = _load_svg(self._svg_file)
        if drawing is None:
            return
        sx = self._size / drawing.width  if drawing.width  else 1
        sy = self._size / drawing.height if drawing.height else 1
        scale = min(sx, sy)
        self.canv.saveState()
        self.canv.translate(0, (self.height - drawing.height * scale) / 2)
        self.canv.scale(scale, scale)
        renderPDF.draw(drawing, self.canv, 0, 0)
        self.canv.restoreState()


def _icon_cell(svg_filename: str, text: str, style, icon_size: float = 9):
    """SVGアイコン＋テキストをミニTableにまとめてテーブルセル用に返す"""
    ico = SVGIcon(svg_filename, icon_size)
    txt = Paragraph(text, style)
    t = Table([[ico, txt]], colWidths=[icon_size * 1.8, None])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t

# ── スタイル定義 ──────────────────────────────────────────────────────────────

def _style(name, **kw):
    defaults = dict(fontName="JP", fontSize=9, leading=13, textColor=colors.black)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

ST_TITLE  = _style("title",  fontName="JP-Bold", fontSize=16, textColor=COLOR_NAVY, leading=22, alignment=1)
ST_SUB    = _style("sub",    fontName="JP-Bold", fontSize=10, textColor=COLOR_NAVY)
ST_LABEL  = _style("label",  fontName="JP-Bold", fontSize=8,  textColor=COLOR_NAVY)
ST_BODY   = _style("body",   fontSize=8)
ST_CENTER = _style("center", fontSize=8,  alignment=1)
ST_PLAN_H = _style("plan_h", fontName="JP-Bold", fontSize=9,  alignment=1, textColor=colors.white)
ST_UP     = _style("up",     fontName="JP-Bold", fontSize=8,  textColor=COLOR_UP)
ST_FOOT   = _style("foot",   fontSize=7,  textColor=colors.grey)

def _up_para(text):
    """UPマーク付きパラグラフ（↑はMeiryoのU+2191）"""
    return Paragraph(f'<font color="#cc0000"><b>&#x2191; {text}</b></font>', ST_CENTER)

# ── プランデータ生成（ダミーロジック） ───────────────────────────────────────

def _make_plans(policy_type: str, cd: dict, premium: int) -> tuple:
    """現在契約から3プランを生成する（本番では別システムがDBに投入する想定）"""
    if policy_type == "自動車":
        base = dict(
            premium=premium,
            taininsho=cd.get("auto_taininsho", "無制限"),
            taibutsusho=cd.get("auto_taibutsusho", "500万円"),
            jinshin=cd.get("auto_jinshin", "5,000万円"),
            vehicle=cd.get("auto_vehicle_amount") or "なし",
            legal="なし",
        )
        plan_a = dict(base)
        plan_b = dict(base, premium=int(premium * 1.15),
                      taibutsusho="1,000万円", vehicle="200万円")
        plan_c = dict(base, premium=int(premium * 1.08), legal="あり")

    elif policy_type == "火災":
        bld = cd.get("fire_building_amount") or 0
        hld = cd.get("fire_household_amount") or 0
        base = dict(
            premium=premium,
            building=f"{bld:,}万円" if bld else "1,000万円",
            household=f"{hld:,}万円" if hld else "300万円",
            quake="あり" if cd.get("fire_quake_flg") else "なし",
            flood="あり" if cd.get("fire_flood_flg") else "なし",
        )
        plan_a = dict(base)
        plan_b = dict(base, premium=int(premium * 1.12),
                      building=f"{int(bld * 1.2):,}万円" if bld else "1,200万円",
                      quake="あり")
        plan_c = dict(base, premium=int(premium * 1.06), flood="あり")

    else:
        base = dict(premium=premium, amount=f"{premium:,}円", tokuyaku="なし")
        plan_a = dict(base)
        plan_b = dict(base, premium=int(premium * 1.15),
                      amount=f"{int(premium * 1.15):,}円")
        plan_c = dict(base, premium=int(premium * 1.08), tokuyaku="あり")

    return plan_a, plan_b, plan_c

# ── 補償対比行ビルダー ────────────────────────────────────────────────────────

def _cmp_cell(current_val, plan_val):
    v = str(plan_val) if plan_val else "—"
    if plan_val and str(plan_val) != str(current_val):
        return _up_para(v)
    return Paragraph(v, ST_CENTER)


def _build_auto_rows(cd: dict, plans: dict) -> list:
    cur = dict(
        taininsho=cd.get("auto_taininsho", "無制限"),
        taibutsusho=cd.get("auto_taibutsusho", "500万円"),
        jinshin=cd.get("auto_jinshin", "5,000万円"),
        vehicle=cd.get("auto_vehicle_amount") or "なし",
        legal="なし",
    )
    specs = [
        (SVG["person_fall"], "対人賠償",   "taininsho"),
        (SVG["car_burst"],   "対物賠償",   "taibutsusho"),
        (SVG["bandage"],     "人身傷害",   "jinshin"),
        (SVG["car"],         "車両保険",   "vehicle"),
        (SVG["scale"],       "弁護士特約", "legal"),
    ]
    rows = []
    for svg_file, label, key in specs:
        cv = cur[key]
        rows.append([
            _icon_cell(svg_file, label, ST_LABEL),
            Paragraph(str(cv), ST_CENTER),
            _cmp_cell(cv, plans["A"].get(key, cv)),
            _cmp_cell(cv, plans["B"].get(key, cv)),
            _cmp_cell(cv, plans["C"].get(key, cv)),
        ])
    return rows


def _build_fire_rows(cd: dict, plans: dict) -> list:
    bld = cd.get("fire_building_amount") or 0
    hld = cd.get("fire_household_amount") or 0
    cur = dict(
        building=f"{bld:,}万円" if bld else "1,000万円",
        household=f"{hld:,}万円" if hld else "300万円",
        quake="あり" if cd.get("fire_quake_flg") else "なし",
        flood="あり" if cd.get("fire_flood_flg") else "なし",
    )
    specs = [
        (SVG["house"],  "建物保険金額", "building"),
        (SVG["house"],  "家財保険金額", "household"),
        (SVG["fire"],   "地震保険",    "quake"),
        (SVG["shield"], "水災補償",    "flood"),
    ]
    rows = []
    for svg_file, label, key in specs:
        cv = cur[key]
        rows.append([
            _icon_cell(svg_file, label, ST_LABEL),
            Paragraph(str(cv), ST_CENTER),
            _cmp_cell(cv, plans["A"].get(key, cv)),
            _cmp_cell(cv, plans["B"].get(key, cv)),
            _cmp_cell(cv, plans["C"].get(key, cv)),
        ])
    return rows


def _build_generic_rows(policy_type: str, premium: int, plans: dict) -> list:
    svg_file = POLICY_SVG.get(policy_type, SVG["shield"])
    specs = [
        (svg_file, "保険金額", "amount"),
        (svg_file, "特約",     "tokuyaku"),
    ]
    rows = []
    for sf, label, key in specs:
        cv = f"{premium:,}円" if key == "amount" else "なし"
        rows.append([
            _icon_cell(sf, label, ST_LABEL),
            Paragraph(str(cv), ST_CENTER),
            _cmp_cell(cv, plans["A"].get(key, cv)),
            _cmp_cell(cv, plans["B"].get(key, cv)),
            _cmp_cell(cv, plans["C"].get(key, cv)),
        ])
    return rows

# ── PDF生成メイン関数 ─────────────────────────────────────────────────────────

def generate_renewal_notice_pdf(contract: dict, contract_detail: dict | None) -> bytes:
    """
    更改おすすめプラン通知書PDFを生成してバイト列で返す。

    Args:
        contract:        contractsテーブルの1行（dict）
        contract_detail: contract_detailsテーブルの1行（dict or None）
    Returns:
        PDFバイナリ（bytes）
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )

    cd          = contract_detail or {}
    policy_type = contract.get("policy_type", "")
    premium     = contract.get("annual_premium", 0) or 0
    svg_file    = POLICY_SVG.get(policy_type, SVG["shield"])

    plan_a, plan_b, plan_c = _make_plans(policy_type, cd, premium)
    plans = {"A": plan_a, "B": plan_b, "C": plan_c}

    elems = []

    # ── タイトル ──────────────────────────────────────────────────────────────
    elems.append(Paragraph("AX損害保険株式会社", _style("co",
        fontName="JP-Bold", fontSize=11, textColor=COLOR_NAVY, alignment=1)))
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph("更 改 お す す め プ ラ ン 通 知 書", ST_TITLE))
    elems.append(HRFlowable(width="100%", thickness=2, color=COLOR_ACCENT, spaceAfter=4*mm))

    # ── 基本情報 ──────────────────────────────────────────────────────────────
    info_data = [
        [Paragraph("証券番号",     ST_LABEL), Paragraph(contract.get("contract_no", ""),    ST_BODY),
         Paragraph("満期日",       ST_LABEL), Paragraph(contract.get("expiry_date", ""),    ST_BODY)],
        [Paragraph("ご契約者",     ST_LABEL), Paragraph(contract.get("customer_name", ""),  ST_BODY),
         Paragraph("代理店コード", ST_LABEL), Paragraph(contract.get("agency_code", ""),    ST_BODY)],
        [Paragraph("保険種目",     ST_LABEL), _icon_cell(svg_file, policy_type, ST_BODY, 9),
         Paragraph("現在の保険料", ST_LABEL), Paragraph(f"{premium:,}円 / 年",              ST_BODY)],
    ]
    info_tbl = Table(info_data, colWidths=[28*mm, 62*mm, 28*mm, 62*mm])
    info_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), COLOR_GRAY),
        ("GRID",          (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    elems.append(info_tbl)
    elems.append(Spacer(1, 5*mm))

    # ── プラン対比表 ──────────────────────────────────────────────────────────
    elems.append(Paragraph("■ 更改おすすめプラン 対比表", ST_SUB))
    elems.append(Spacer(1, 2*mm))

    col_w = [42*mm, 28*mm, 28*mm, 28*mm, 28*mm]

    header_row = [
        Paragraph("補償内容", ST_PLAN_H),
        _icon_cell(svg_file, "現在のご契約",
                   _style("ph_cur", fontName="JP-Bold", fontSize=8,
                          alignment=1, textColor=colors.white), 8),
        Paragraph("プランA\n保険料据え置き", ST_PLAN_H),
        Paragraph("プランB\n補償UP",        ST_PLAN_H),
        Paragraph("プランC\n特約追加",      ST_PLAN_H),
    ]

    def premium_row_cell(p, base):
        if p == base:
            return Paragraph(f"{p:,}円", ST_CENTER)
        return _up_para(f"{p:,}円　(+{p - base:,}円)")

    premium_row = [
        _icon_cell(SVG["coins"], "年換算保険料", ST_LABEL),
        Paragraph(f"{premium:,}円", ST_CENTER),
        premium_row_cell(plan_a["premium"], premium),
        premium_row_cell(plan_b["premium"], premium),
        premium_row_cell(plan_c["premium"], premium),
    ]

    if policy_type == "自動車":
        detail_rows = _build_auto_rows(cd, plans)
    elif policy_type == "火災":
        detail_rows = _build_fire_rows(cd, plans)
    else:
        detail_rows = _build_generic_rows(policy_type, premium, plans)

    all_rows = [header_row, premium_row] + detail_rows

    plan_tbl = Table(all_rows, colWidths=col_w, repeatRows=1)
    plan_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  COLOR_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("BACKGROUND",    (1, 1), (1, -1),  COLOR_HEADER),
        ("BACKGROUND",    (3, 1), (3, -1),  colors.HexColor("#e8f5ed")),
        ("BACKGROUND",    (4, 1), (4, -1),  colors.HexColor("#e8eef5")),
        ("BACKGROUND",    (0, 1), (-1, 1),  colors.HexColor("#fff8e8")),
        ("FONTNAME",      (0, 1), (-1, 1),  "JP-Bold"),
        ("GRID",          (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
    ]))
    elems.append(plan_tbl)
    elems.append(Spacer(1, 5*mm))

    # ── 注意書き ──────────────────────────────────────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER))
    elems.append(Spacer(1, 2*mm))
    notes = [
        "※ 本通知書はデモ用サンプルです。実際の保険料・補償内容は正式な見積書をご確認ください。",
        "※ プランB・Cの保険料はシミュレーション値であり、引受審査により変動する場合があります。",
        "※ &#x2191; UP マークは現在のご契約より補償・保険金額が向上した項目を示します。",
    ]
    for n in notes:
        elems.append(Paragraph(n, ST_FOOT))
        elems.append(Spacer(1, 1*mm))

    doc.build(elems)
    return buf.getvalue()
