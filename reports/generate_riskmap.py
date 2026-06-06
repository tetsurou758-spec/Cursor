"""
リスクマップPDF生成モジュール
ReportLab でピザチャート（7等分円グラフ）を描画し、
各スライスにSVGアイコン＋種目名を表示する。

関数:
    generate_customer_riskmap  -- 顧客単位（7種目加入状況）
    generate_contract_riskmap  -- 契約単位（種目別補償項目）
"""

import io
import math
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Wedge, String, Group, Path
from reportlab.platypus import (
    SimpleDocTemplate, Spacer, HRFlowable, Paragraph
)
from reportlab.lib.styles import ParagraphStyle
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
            pdfmetrics.registerFont(TTFont("RM_JP",      path))
            pdfmetrics.registerFont(TTFont("RM_JP-Bold", path))
            registerFontFamily("RM_JP",
                               normal="RM_JP", bold="RM_JP-Bold",
                               italic="RM_JP", boldItalic="RM_JP-Bold")
            return
    raise RuntimeError("日本語フォントが見つかりません")


_register_fonts()

# ── SVGアイコンキャッシュ ─────────────────────────────────────────────────────

_svg_cache: dict = {}


def _load_svg(svg_filename: str):
    """SVGファイルをReportLabのDrawingとして読み込む（キャッシュ付き）"""
    if svg_filename in _svg_cache:
        return _svg_cache[svg_filename]
    path = os.path.join(_ICONS_DIR, svg_filename)
    if not os.path.exists(path):
        _svg_cache[svg_filename] = None
        return None
    with open(path, "rb") as f:
        drawing = svg2rlg(io.BytesIO(f.read()))
    _svg_cache[svg_filename] = drawing
    return drawing

# ── 種目定義 ──────────────────────────────────────────────────────────────────

# 時計回り順：自動車→火災→傷害→自賠責→賠償責任→サイバーリスク→所得補償
POLICY_TYPES_ORDER = [
    "自動車",
    "火災",
    "傷害",
    "自賠責",
    "賠償責任",
    "サイバーリスク",
    "所得補償",
]

# 種目ごとの設定（カラー・SVGファイル名・DB種目コード）
POLICY_CONFIG = {
    "自動車":         {"color": "#4A90D9", "svg": "car.svg",           "code": "AUTO"},
    "火災":           {"color": "#E8763A", "svg": "house.svg",         "code": "FIRE"},
    "傷害":           {"color": "#5BAD6F", "svg": "bandage.svg",       "code": "INJURY"},
    "自賠責":         {"color": "#5BB8D4", "svg": "car.svg",           "code": "JIBAI"},
    "賠償責任":       {"color": "#D4A838", "svg": "shield-halved.svg", "code": "LIABILITY"},
    "サイバーリスク": {"color": "#8B5BD4", "svg": "globe.svg",         "code": "CYBER"},
    "所得補償":       {"color": "#D45B5B", "svg": "coins.svg",         "code": "INCOME"},
}

# 未加入スライスのグレー色
COLOR_UNCOVERED = "#C8C8C8"

# 契約単位の補償項目定義
CONTRACT_ITEMS = {
    "自動車": [
        ("対人賠償",     "auto_taininsho"),
        ("対物賠償",     "auto_taibutsusho"),
        ("人身傷害",     "auto_jinshin"),
        ("搭乗者傷害",   "auto_passenger"),
        ("車両保険",     "auto_vehicle_amount"),
    ],
    "火災": [
        ("建物",       "fire_building_amount"),
        ("家財",       "fire_household_amount"),
        ("地震保険",   "fire_quake_flg"),
        ("水災補償",   "fire_flood_flg"),
    ],
    "傷害": [
        ("死亡",       "inj_death_amount"),
        ("後遺障害",   "inj_disability_amount"),
        ("入院",       "inj_hospitalization"),
        ("通院",       "inj_outpatient"),
        ("手術",       "inj_surgery"),
    ],
    "自賠責": [
        ("傷害限度額", "jibai_injury_limit"),
        ("死亡限度額", "jibai_death_limit"),
    ],
    "賠償責任": [
        ("対人(1名)",   "liab_per_person"),
        ("対人(1事故)", "liab_per_accident"),
        ("対物",        "liab_property"),
    ],
    "サイバーリスク": [
        ("第三者賠償",   "cyber_third_party"),
        ("情報漏えい",   "cyber_info_leak"),
        ("復旧費用",     "cyber_recovery"),
        ("事業中断",     "cyber_business_int"),
    ],
    "所得補償": [
        ("月額保険金",   "income_monthly_benefit"),
        ("月間平均所得", "income_avg_monthly"),
    ],
}

# ── スタイル定義 ──────────────────────────────────────────────────────────────

COLOR_NAVY   = colors.HexColor("#003366")
COLOR_ACCENT = colors.HexColor("#C8960C")
COLOR_BORDER = colors.HexColor("#cccccc")


def _style(name, **kw):
    defaults = dict(fontName="RM_JP", fontSize=9, leading=13, textColor=colors.black)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


ST_TITLE = _style("rm_title", fontName="RM_JP-Bold", fontSize=16,
                  textColor=COLOR_NAVY, leading=22, alignment=1)
ST_CO    = _style("rm_co",    fontName="RM_JP-Bold", fontSize=11,
                  textColor=COLOR_NAVY, alignment=1)
ST_FOOT  = _style("rm_foot",  fontSize=7, textColor=colors.grey)
ST_LEGEND_LABEL = _style("rm_legend", fontSize=8, leading=11)

# ── ピザチャート描画 ──────────────────────────────────────────────────────────


def _pizza_chart(
    cx: float, cy: float, radius: float,
    items: list[tuple[str, bool, str]],
) -> Drawing:
    """
    ピザチャートを描くDrawingを返す。

    Args:
        cx, cy   : 中心座標（Drawing内の座標）
        radius   : 外半径
        items    : [(ラベル, 加入フラグ, カラーHex), ...]
    Returns:
        ReportLab Drawing オブジェクト
    """
    n = len(items)
    if n == 0:
        return Drawing(cx * 2, cy * 2)

    d = Drawing(cx * 2, cy * 2)
    angle_step = 360.0 / n
    # 12時方向（90度）から時計回りに描画
    start_angle = 90.0

    for i, (label, covered, hex_color) in enumerate(items):
        fill_hex = hex_color if covered else COLOR_UNCOVERED
        fill_color = colors.HexColor(fill_hex)

        # 時計回りなので角度を減算
        wedge_start = start_angle - (i + 1) * angle_step
        wedge = Wedge(
            cx, cy,
            radius,
            wedge_start,
            wedge_start + angle_step,
            strokeColor=colors.white,
            strokeWidth=2,
            fillColor=fill_color,
        )
        d.add(wedge)

        # スライス中央にアイコン＋ラベルテキストを配置
        mid_angle_deg = wedge_start + angle_step / 2.0
        mid_angle_rad = math.radians(mid_angle_deg)
        label_r = radius * 0.65
        lx = cx + label_r * math.cos(mid_angle_rad)
        ly = cy + label_r * math.sin(mid_angle_rad)

        # SVGアイコン（小さく縮小して描画）
        icon_size = radius * 0.18
        svg_drawing = _load_svg(
            POLICY_CONFIG.get(label, {}).get("svg", "shield-halved.svg")
        )
        if svg_drawing and svg_drawing.width and svg_drawing.height:
            scale = icon_size / max(svg_drawing.width, svg_drawing.height)
            icon_x = lx - icon_size / 2.0
            icon_y = ly + icon_size * 0.1  # テキストの上
            g = Group()
            g.transform = (
                scale, 0, 0, scale,
                icon_x,
                icon_y,
            )
            g.add(svg_drawing)
            d.add(g)

        # ラベルテキスト
        font_size = max(5.5, radius * 0.07)
        text_y = ly - icon_size * 1.0
        txt = String(
            lx, text_y, label,
            fontName="RM_JP",
            fontSize=font_size,
            textAnchor="middle",
            fillColor=colors.white if covered else colors.HexColor("#666666"),
        )
        d.add(txt)

    # 中央の白い円（ドーナツ効果）
    from reportlab.graphics.shapes import Circle
    hole = Circle(cx, cy, radius * 0.3,
                  fillColor=colors.white, strokeColor=colors.white)
    d.add(hole)

    return d

# ── 凡例テーブル描画 ──────────────────────────────────────────────────────────


def _build_legend(items: list[tuple[str, bool, str]], chart_width: float) -> list:
    """
    ピザチャートの凡例をFlowableリストとして返す。

    Args:
        items      : [(ラベル, 加入フラグ, カラーHex), ...]
        chart_width: チャートの幅（mm）
    """
    from reportlab.platypus import Table, TableStyle

    legend_rows = []
    row = []
    for i, (label, covered, hex_color) in enumerate(items):
        fill_hex = hex_color if covered else COLOR_UNCOVERED
        # カラーボックス＋ラベル
        color_box = f'<font color="{fill_hex}">■</font> {label}'
        status = "加入済" if covered else "未加入"
        status_color = hex_color if covered else "#888888"
        cell_text = (
            f'<font color="{fill_hex}">■</font> {label}　'
            f'<font color="{status_color}"><b>{status}</b></font>'
        )
        row.append(Paragraph(cell_text, ST_LEGEND_LABEL))
        if len(row) == 3 or i == len(items) - 1:
            # 3列揃えるためにパディング
            while len(row) < 3:
                row.append(Paragraph("", ST_LEGEND_LABEL))
            legend_rows.append(row)
            row = []

    if not legend_rows:
        return []

    col_w = [chart_width / 3.0] * 3
    tbl = Table(legend_rows, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    return [tbl]

# ── PDFドキュメント共通ビルダー ───────────────────────────────────────────────


def _build_pdf(title_text: str, chart_drawing: Drawing, legend_items, chart_size_mm: float) -> bytes:
    """
    タイトル＋ピザチャート＋凡例を組み合わせてPDFバイナリを返す。

    Args:
        title_text   : ページタイトル文字列
        chart_drawing: _pizza_chart() が返す Drawing
        legend_items : [(ラベル, 加入フラグ, カラーHex), ...]
        chart_size_mm: チャートの描画サイズ（mm）
    Returns:
        PDFバイナリ（bytes）
    """
    from reportlab.platypus import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.graphics import renderPDF as rl_renderPDF

    buf = io.BytesIO()
    page_w, page_h = A4
    left_m = right_m = 20 * mm
    top_m = bottom_m = 15 * mm
    usable_w = page_w - left_m - right_m

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=left_m, rightMargin=right_m,
        topMargin=top_m, bottomMargin=bottom_m,
    )

    elems = []

    # ── 会社名・タイトル ──────────────────────────────────────────────────────
    elems.append(Paragraph("AX損害保険株式会社", ST_CO))
    elems.append(Spacer(1, 3 * mm))
    elems.append(Paragraph(title_text, ST_TITLE))
    elems.append(HRFlowable(width="100%", thickness=2,
                             color=COLOR_ACCENT, spaceAfter=6 * mm))

    # ── ピザチャートをDrawingとして埋め込む ───────────────────────────────────
    chart_size_pt = chart_size_mm * mm
    # Drawingをページ中央配置するためにラッパーDrawingで包む
    wrapper = Drawing(usable_w, chart_size_pt)
    chart_x = (usable_w - chart_drawing.width) / 2.0
    chart_y = (chart_size_pt - chart_drawing.height) / 2.0
    from reportlab.graphics.shapes import Group as RLGroup
    g = RLGroup()
    g.transform = (1, 0, 0, 1, chart_x, chart_y)
    g.add(chart_drawing)
    wrapper.add(g)

    from reportlab.platypus import Flowable as BaseFlowable

    class DrawingFlowable(BaseFlowable):
        """DrawingをFlowableとして埋め込むラッパー"""
        def __init__(self, drawing, width, height):
            BaseFlowable.__init__(self)
            self._d = drawing
            self.width = width
            self.height = height

        def draw(self):
            rl_renderPDF.draw(self._d, self.canv, 0, 0)

    elems.append(DrawingFlowable(wrapper, usable_w, chart_size_pt))
    elems.append(Spacer(1, 6 * mm))

    # ── 凡例 ─────────────────────────────────────────────────────────────────
    legend_flowables = _build_legend(legend_items, usable_w)
    elems.extend(legend_flowables)
    elems.append(Spacer(1, 8 * mm))

    # ── 注意書き ──────────────────────────────────────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER))
    elems.append(Spacer(1, 2 * mm))
    notes = [
        "※ 本帳票はデモ用サンプルです。実際の補償内容は保険証券または約款をご確認ください。",
        "※ ■加入済は現在ご契約中の種目・補償項目を示します。■未加入は対象外または未加入を示します。",
    ]
    for n in notes:
        elems.append(Paragraph(n, ST_FOOT))
        elems.append(Spacer(1, 1 * mm))

    doc.build(elems)
    return buf.getvalue()

# ── 公開関数 ──────────────────────────────────────────────────────────────────


def generate_customer_riskmap(customer_name: str, covered_types: list[str]) -> bytes:
    """
    顧客単位リスクマップPDFを生成してバイト列で返す。

    Args:
        customer_name: 顧客氏名（タイトルに使用）
        covered_types: 加入済み種目名のリスト（例: ['自動車', '火災']）
    Returns:
        PDFバイナリ（bytes）
    """
    covered_set = set(covered_types)

    # ピザチャート用アイテムリスト
    items = []
    for pt in POLICY_TYPES_ORDER:
        cfg = POLICY_CONFIG[pt]
        covered = pt in covered_set
        items.append((pt, covered, cfg["color"]))

    # 円の半径を決める（usable幅 = A4 - 40mm マージン = 170mm相当）
    chart_size_mm = 140.0
    chart_size_pt = chart_size_mm * mm
    radius = chart_size_pt * 0.42
    cx = cy = chart_size_pt / 2.0

    chart = _pizza_chart(cx, cy, radius, items)
    title = f"{customer_name}様　リスクカバー状況"
    return _build_pdf(title, chart, items, chart_size_mm)


def generate_contract_riskmap(
    customer_name: str, contract_no: str, policy_type: str, detail: dict
) -> bytes:
    """
    契約単位リスクマップPDFを生成してバイト列で返す。

    Args:
        customer_name: 顧客氏名
        contract_no  : 証券番号
        policy_type  : 保険種目名（例: '自動車'）
        detail       : contract_detailsテーブルの1行をdictにしたもの
    Returns:
        PDFバイナリ（bytes）
    """
    cfg   = POLICY_CONFIG.get(policy_type, POLICY_CONFIG["賠償責任"])
    specs = CONTRACT_ITEMS.get(policy_type, [])

    items = []
    for label, col in specs:
        val = detail.get(col)
        # None / 0 / False / 空文字 → 未カバー扱い
        covered = val is not None and val not in (0, False, "", "0", "なし")
        items.append((label, covered, cfg["color"]))

    if not items:
        # 補償項目定義がない種目はダミー2スライスで代替
        items = [("補償", True, cfg["color"]), ("その他", False, COLOR_UNCOVERED)]

    chart_size_mm = 140.0
    chart_size_pt = chart_size_mm * mm
    radius = chart_size_pt * 0.42
    cx = cy = chart_size_pt / 2.0

    chart = _pizza_chart(cx, cy, radius, items)
    title = f"{customer_name}様　契約リスクカバー状況（{contract_no}）"
    return _build_pdf(title, chart, items, chart_size_mm)
