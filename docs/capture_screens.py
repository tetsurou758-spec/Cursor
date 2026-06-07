"""
capture_screens.py
全画面のスクリーンショットを docs/screenshots/ に保存する。
APIサーバー（localhost:8000）が起動していること。

使い方:
    python docs/capture_screens.py
"""

import asyncio
import os
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8000"
OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

# =========================================================
# 画面定義（ファイル名, 出力PNG名, ログイン種別, 追加操作）
# =========================================================
AGENCY_LOGIN = {"id": "agency_code", "id_val": "A001",
                "login": "login_id", "login_val": "admin",
                "pass": "password",  "pass_val": "password123"}

STAFF_LOGIN  = {"staff_code": "S001", "password": "staff123"}

SCREENS = [
    # (PNG名, HTMLファイル or URL, ログイン種別, 備考)
    ("01_login",          "login.html",           None,     "代理店ログイン"),
    ("02_staff_login",    "staff_login.html",      None,     "社員ログイン"),
    ("03_dashboard_agency", "dashboard.html",     "agency", "ダッシュボード（代理店）"),
    ("04_dashboard_staff",  "dashboard.html",     "staff",  "ダッシュボード（社員）"),
    ("05_maturity",       "maturity.html",        "agency", "満期管理"),
    ("06_customer",       "customer.html",        "agency", "顧客管理"),
    ("07_contract",       "contract.html",        "agency", "契約照会"),
    ("08_contract_detail","contract_detail.html", "agency", "契約詳細"),
    ("09_claim",          "claim.html",           "agency", "保険金支払状況"),
    ("10_claim_detail",   "claim_detail.html",    "agency", "保険金詳細"),
    ("11_contact",        "contact.html",         "agency", "コンタクト履歴"),
    ("12_intention",      "intention.html",       "agency", "意向確認一覧"),
    ("13_intention_detail","intention_detail.html","agency", "意向確認詳細"),
    ("14_admin",          "admin.html",           "agency", "権限管理"),
    ("15_agency_master",  "agency_master.html",   "staff",  "代理店マスタ編集"),
    ("16_sales",          "sales.html",           "agency", "成績管理"),
    ("17_sales_target",   "sales_target.html",    "agency", "目標設定"),
    ("18_commission",     "commission.html",      "agency", "手数料管理"),
    ("19_ai_recommend",   "ai_recommend.html",    "agency", "AIレコメンド"),
    ("20_report_list",    "report_list.html",     "agency", "帳票管理"),
    ("21_todo_list",      "todo_list.html",       "agency", "TODOリスト"),
]

async def agency_login(page):
    """代理店でログイン"""
    fpath = os.path.abspath("frontend/login.html").replace("\\", "/")
    await page.goto(f"file:///{fpath}")
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)
    await page.fill("#agency-code", "A001")
    await page.fill("#login-id",    "admin")
    await page.fill("#password",    "password123")
    await page.click("#btn-login")
    await asyncio.sleep(2)

async def staff_login(page):
    """社員でログイン"""
    fpath = os.path.abspath("frontend/staff_login.html").replace("\\", "/")
    await page.goto(f"file:///{fpath}")
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)
    await page.fill("#staff-code", "S001")
    await page.fill("#password",   "staff123")
    await page.click("#btn-login")
    await asyncio.sleep(2)

async def capture_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # --- 代理店セッション ---
        ctx_agency = await browser.new_context(viewport={"width": 1440, "height": 900})
        page_agency = await ctx_agency.new_page()
        await agency_login(page_agency)

        # --- 社員セッション ---
        ctx_staff  = await browser.new_context(viewport={"width": 1440, "height": 900})
        page_staff  = await ctx_staff.new_page()
        await staff_login(page_staff)

        for (png, html, login_type, label) in SCREENS:
            try:
                if login_type is None:
                    # ログイン不要（ログイン画面自体）
                    ctx_tmp = await browser.new_context(viewport={"width": 1440, "height": 900})
                    page = await ctx_tmp.new_page()
                    fpath = os.path.abspath(f"frontend/{html}").replace(os.sep, "/")
                    await page.goto(f"file:///{fpath}")
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(0.5)
                elif login_type == "agency":
                    page = page_agency
                    fpath = os.path.abspath(f"frontend/{html}").replace(os.sep, "/")
                    await page.goto(f"file:///{fpath}")
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1.5)
                else:  # staff
                    page = page_staff
                    fpath = os.path.abspath(f"frontend/{html}").replace(os.sep, "/")
                    await page.goto(f"file:///{fpath}")
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1.5)

                out_path = os.path.join(OUT_DIR, f"{png}.png")
                await page.screenshot(path=out_path, full_page=False)
                print(f"  [OK] {png}.png  ({label})")

                if login_type is None:
                    await ctx_tmp.close()

            except Exception as e:
                print(f"  [NG] {png}  ({label}): {e}")

        await browser.close()
    print(f"\n完了 → {OUT_DIR}")

if __name__ == "__main__":
    asyncio.run(capture_all())
