"""スクリーンショットをExcelに貼り付けるだけのスクリプト"""
import os
from pathlib import Path
import openpyxl
from openpyxl.drawing.image import Image as XlImage

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
EXCEL_PATH     = Path(__file__).parent / "ログインテスト仕様書.xlsx"

TEST_IDS = [f"UT-LOGIN-{i:03d}" for i in range(1, 14)]

wb = openpyxl.load_workbook(str(EXCEL_PATH))

for test_id in TEST_IDS:
    img_path = str(SCREENSHOT_DIR / f"{test_id}.png")
    if test_id not in wb.sheetnames:
        print(f"  スキップ（シートなし）: {test_id}")
        continue
    if not os.path.exists(img_path):
        print(f"  スキップ（画像なし）: {img_path}")
        continue

    ws  = wb[test_id]
    img = XlImage(img_path)
    img.width  = 900
    img.height = 563
    ws.add_image(img, "A3")
    ws.row_dimensions[3].height = 430
    ws.column_dimensions["A"].width = 18
    print(f"  貼付完了: {test_id}")

wb.save(str(EXCEL_PATH))
print(f"\nExcel保存完了: {EXCEL_PATH}")
