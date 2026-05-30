"""
権限管理テスト証跡.xlsx に「スクリーンショット証跡」シートを追加し、
テストケースごとにスクリーンショットを貼り付けるスクリプト
"""
import io, pathlib
from PIL import Image as PILImage
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

EXCEL_PATH = pathlib.Path(__file__).parent / "権限管理テスト証跡.xlsx"
SS_DIR     = pathlib.Path(__file__).parent / "screenshots"

# ── テストケース × スクリーンショット マッピング ─────────────
# (試験番号, 確認内容ラベル, 使用するスクリーンショットファイル名)
CASE_SCREENSHOTS = [
    ("UT-AUTH-001", "login.html　ログイン画面表示確認",
     "01_login.png"),
    ("UT-AUTH-002", "staff1 ログイン → ダッシュボード遷移・ロール「一般担当」表示確認",
     "02_dashboard_staff1.png"),
    ("UT-AUTH-003", "保険金支払状況ボタン グレーアウト・他3ボタン活性確認",
     "03_dashboard_staff1_permission.png"),
    ("UT-AUTH-004", "グレーアウトボタン ホバー時「権限がありません」ツールチップ確認",
     "04_tooltip_no_permission.png"),
    ("UT-AUTH-005", "staff1 ログイン時 ヘッダーに「ユーザー管理」リンク非表示確認",
     "03_dashboard_staff1_permission.png"),
    ("UT-AUTH-006", "「ログアウト」クリック → login.html 復帰確認",
     "05_logout_back_to_login.png"),
    ("UT-AUTH-007", "admin ログイン → ダッシュボード遷移・ロール「管理者」表示確認",
     "06_dashboard_admin.png"),
    ("UT-AUTH-008", "全メニューボタン活性状態確認（admin・保険金支払状況も活性）",
     "07_dashboard_admin_permission.png"),
    ("UT-AUTH-009", "ヘッダーに「ユーザー管理」リンク表示確認（admin）",
     "07_dashboard_admin_permission.png"),
    ("UT-AUTH-010", "「ユーザー管理」リンク → admin.html 遷移確認",
     "08_admin_page.png"),
    ("UT-AUTH-011", "ユーザー一覧テーブル（admin・staff1の2件）・ロールチップ・操作ボタン確認",
     "09_admin_user_list.png"),
    ("UT-AUTH-012", "「＋ユーザー追加」ボタン → 追加モーダル表示確認",
     "10_admin_add_modal.png"),
    ("UT-AUTH-013", "ロール別権限マトリクス表示確認（管理者=全権限、一般担当・閲覧専用=制限あり）",
     "11_admin_permission_matrix.png"),
    ("UT-AUTH-014", "GET /api/permissions (staff1) → 一般担当権限制御がダッシュボードに反映されていることで確認",
     "03_dashboard_staff1_permission.png"),
    ("UT-AUTH-015", "GET /api/users (staff1=role_id:2) → 403応答。ユーザー管理リンク非表示・管理画面アクセス不可で確認",
     "03_dashboard_staff1_permission.png"),
    ("UT-AUTH-016", "GET /api/users (admin=role_id:1) → A001ユーザー一覧2件返却確認",
     "09_admin_user_list.png"),
    ("UT-AUTH-017", "staff1 で admin.html 直接アクセス → dashboard.html リダイレクト確認",
     "03_dashboard_staff1_permission.png"),
]

# ── レイアウト定数 ─────────────────────────────────────────────
# Excel 画像表示サイズ（ピクセル）
IMG_W = 800   # 表示幅
IMG_H = 500   # 表示高さ

# Excel行高さ(pt) → ピクセル換算: 1pt ≈ 1.333px (96dpi)
ROW_H_PT      = 14.0
PX_PER_PT     = 96 / 72          # ≈ 1.333
IMG_ROW_COUNT = int(IMG_H / (ROW_H_PT * PX_PER_PT)) + 2   # ≈ 27行
HEADER_ROW_H  = 30.0
GAP_ROWS      = 2

# 1ケース当たりの行数
ROWS_PER_CASE = 1 + IMG_ROW_COUNT + GAP_ROWS   # header + image + gap

# ── カラー定義 ─────────────────────────────────────────────────
NAVY      = "000D2B5E"
NAVY_MID  = "001A3A72"
GOLD      = "00C9A84C"
WHITE     = "00FFFFFF"
LIGHT     = "00F0F2F7"

def thin_border():
    s = Side(style="thin", color="FFCCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def resize_image(img_path: pathlib.Path, width: int, height: int) -> io.BytesIO:
    """PIL でリサイズして BytesIO に PNG 保存して返す"""
    with PILImage.open(img_path) as im:
        im = im.convert("RGB")
        im = im.resize((width, height), PILImage.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        buf.seek(0)
    return buf


def add_screenshot_sheet():
    wb = load_workbook(EXCEL_PATH)

    # 既に存在するなら削除して作り直す
    if "スクリーンショット証跡" in wb.sheetnames:
        del wb["スクリーンショット証跡"]

    ws = wb.create_sheet("スクリーンショット証跡")

    # ── カラム幅設定 ─────────────────────────────────────────
    # A列: ラベル（狭め）/ B列: 画像エリア（広め）
    # Excel列幅 1unit ≈ 7px
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = int(IMG_W / 7) + 2   # ≈ 116

    # ── シートタイトル行（行1）────────────────────────────────
    ws.row_dimensions[1].height = 36
    ws.merge_cells("A1:B1")
    c = ws["A1"]
    c.value = "権限管理テスト　スクリーンショット証跡"
    c.font  = Font(bold=True, size=15, color=WHITE, name="Meiryo")
    c.fill  = PatternFill(fill_type="solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[2].height = 20
    ws.merge_cells("A2:B2")
    ws["A2"].value = "テストID：UT-AUTH-001 〜 UT-AUTH-017　　テスト実施日：2026/05/30"
    ws["A2"].font  = Font(size=10, color=WHITE, name="Meiryo")
    ws["A2"].fill  = PatternFill(fill_type="solid", fgColor=NAVY_MID)
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")

    ws.row_dimensions[3].height = 8   # 区切り空白

    # ── テストケースごとに貼り付け ──────────────────────────
    current_row = 4

    for idx, (case_id, label, img_name) in enumerate(CASE_SCREENSHOTS):
        img_path = SS_DIR / img_name
        print(f"  [{idx+1:02d}/{len(CASE_SCREENSHOTS)}] {case_id} ← {img_name}")

        # ── ヘッダー行（ケースID・説明）────────────────────
        ws.row_dimensions[current_row].height = HEADER_ROW_H

        # A列：試験番号
        c_id = ws.cell(row=current_row, column=1, value=case_id)
        c_id.font  = Font(bold=True, size=10, color=WHITE, name="Meiryo")
        c_id.fill  = PatternFill(fill_type="solid", fgColor=NAVY)
        c_id.alignment = Alignment(horizontal="center", vertical="center")
        c_id.border = thin_border()

        # B列：確認内容ラベル
        c_lb = ws.cell(row=current_row, column=2, value=label)
        c_lb.font  = Font(bold=True, size=10, color=WHITE, name="Meiryo")
        c_lb.fill  = PatternFill(fill_type="solid", fgColor=NAVY)
        c_lb.alignment = Alignment(horizontal="left", vertical="center")
        c_lb.border = thin_border()

        img_start_row = current_row + 1

        # ── 画像エリアの行高さを設定 ────────────────────────
        for r in range(img_start_row, img_start_row + IMG_ROW_COUNT):
            ws.row_dimensions[r].height = ROW_H_PT
            # A列・B列に背景色（薄いグレー）
            for col in [1, 2]:
                cell = ws.cell(row=r, column=col)
                cell.fill = PatternFill(fill_type="solid", fgColor=LIGHT)

        # ── 画像をリサイズして挿入 ──────────────────────────
        buf = resize_image(img_path, IMG_W, IMG_H)
        xl_img = XLImage(buf)
        xl_img.width  = IMG_W
        xl_img.height = IMG_H

        # B列の開始行にアンカー
        anchor_cell = f"B{img_start_row}"
        ws.add_image(xl_img, anchor_cell)

        # ── ギャップ行 ────────────────────────────────────
        current_row = img_start_row + IMG_ROW_COUNT
        for r in range(current_row, current_row + GAP_ROWS):
            ws.row_dimensions[r].height = 10

        current_row += GAP_ROWS

    # ── 保存 ─────────────────────────────────────────────────
    wb.save(EXCEL_PATH)
    print(f"\n保存完了: {EXCEL_PATH}")
    print(f"総テストケース数: {len(CASE_SCREENSHOTS)}")


if __name__ == "__main__":
    add_screenshot_sheet()
