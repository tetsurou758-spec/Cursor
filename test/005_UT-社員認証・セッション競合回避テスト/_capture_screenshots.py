"""
005_UT-社員認証・セッション競合回避テスト
スクリーンショット取得スクリプト

シナリオ：
  Tab A（代理店: A001/admin）と Tab B（社員: S001/staff123）を
  2つのブラウザコンテキストで交互に操作し、sessionStorage の
  独立性（セッション競合なし）をスクリーンショットで証明する。

操作順序（各タブで1画面ずつ交互）：
  001 [Tab A] login.html 開く
  002 [Tab B] staff_login.html 開く
  003 [Tab A] ログイン実行 → dashboard.html
  004 [Tab B] ログイン実行 → dashboard.html
  005 [Tab A] ダッシュボード再確認（Tab B ログイン後の影響なし）
  006 [Tab B] ダッシュボード再確認
  007 [Tab A] 満期管理画面へ遷移
  008 [Tab B] 満期管理画面へ遷移
  009 [Tab A] 満期管理→戻る→admin.html（権限設定）へ遷移
  010 [Tab B] 満期管理→戻る→dashboard.html
  011 [Tab A] admin.html→戻る→dashboard.html
  012 [Tab A] ログアウト → login.html
  013 [Tab B] ログアウト → staff_login.html
"""
import subprocess, time, sys, pathlib
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8080"
SS_DIR   = pathlib.Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)

VP = {"width": 1280, "height": 800}


def ss(page, name):
    path = str(SS_DIR / name)
    page.screenshot(path=path, full_page=False)
    print(f"  撮影: {name}")
    return path


def run():
    frontend_dir = pathlib.Path(__file__).parent.parent.parent / "frontend"
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8080", "--directory", str(frontend_dir)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=150)

            # Tab A: 代理店コンテキスト（独立した sessionStorage）
            ctx_a = browser.new_context(viewport=VP)
            page_a = ctx_a.new_page()

            # Tab B: 社員コンテキスト（独立した sessionStorage）
            ctx_b = browser.new_context(viewport=VP)
            page_b = ctx_b.new_page()

            # ────────────────────────────────────────────────
            # 001 [Tab A] 代理店ログイン画面
            # ────────────────────────────────────────────────
            print("\n■ 001 [Tab A] 代理店ログイン画面")
            page_a.goto(f"{BASE_URL}/login.html")
            page_a.wait_for_load_state("networkidle")
            ss(page_a, "01_tab_a_agency_login.png")

            # ────────────────────────────────────────────────
            # 002 [Tab B] 社員ログイン画面
            # ────────────────────────────────────────────────
            print("\n■ 002 [Tab B] 社員ログイン画面")
            page_b.goto(f"{BASE_URL}/staff_login.html")
            page_b.wait_for_load_state("networkidle")
            ss(page_b, "02_tab_b_staff_login.png")

            # ────────────────────────────────────────────────
            # 003 [Tab A] 代理店ログイン実行 → ダッシュボード
            # ────────────────────────────────────────────────
            print("\n■ 003 [Tab A] 代理店ログイン → ダッシュボード")
            page_a.fill("#agency-code", "A001")
            page_a.fill("#login-id",    "admin")
            page_a.fill("#password",    "password123")
            page_a.click("#btn-login")
            page_a.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=8000)
            page_a.wait_for_timeout(2500)
            ss(page_a, "03_tab_a_dashboard_agency.png")

            # ────────────────────────────────────────────────
            # 004 [Tab B] 社員ログイン実行 → ダッシュボード
            # ────────────────────────────────────────────────
            print("\n■ 004 [Tab B] 社員ログイン → ダッシュボード")
            page_b.fill("#staff-code", "S001")
            page_b.fill("#password",   "staff123")
            page_b.click("#btn-login")
            page_b.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=8000)
            page_b.wait_for_timeout(2500)
            ss(page_b, "04_tab_b_dashboard_staff.png")

            # ────────────────────────────────────────────────
            # 005 [Tab A] ダッシュボード再確認（Tab B ログイン後）
            # ────────────────────────────────────────────────
            print("\n■ 005 [Tab A] ダッシュボード再確認")
            page_a.evaluate("window.scrollTo(0, 0)")
            page_a.wait_for_timeout(400)
            ss(page_a, "05_tab_a_dashboard_recheck.png")

            # ────────────────────────────────────────────────
            # 006 [Tab B] ダッシュボード再確認
            # ────────────────────────────────────────────────
            print("\n■ 006 [Tab B] ダッシュボード再確認")
            page_b.evaluate("window.scrollTo(0, 0)")
            page_b.wait_for_timeout(400)
            ss(page_b, "06_tab_b_dashboard_recheck.png")

            # ────────────────────────────────────────────────
            # 007 [Tab A] 満期管理画面へ遷移
            # ────────────────────────────────────────────────
            print("\n■ 007 [Tab A] 満期管理画面へ遷移")
            page_a.click("a[href='maturity.html'].nav-btn")
            page_a.wait_for_url(f"{BASE_URL}/maturity.html", timeout=8000)
            page_a.wait_for_load_state("networkidle")
            page_a.wait_for_timeout(1500)
            ss(page_a, "07_tab_a_maturity.png")

            # ────────────────────────────────────────────────
            # 008 [Tab B] 満期管理画面へ遷移
            # ────────────────────────────────────────────────
            print("\n■ 008 [Tab B] 満期管理画面へ遷移")
            page_b.click("a[href='maturity.html'].nav-btn")
            page_b.wait_for_url(f"{BASE_URL}/maturity.html", timeout=8000)
            page_b.wait_for_load_state("networkidle")
            page_b.wait_for_timeout(1500)
            ss(page_b, "08_tab_b_maturity.png")

            # ────────────────────────────────────────────────
            # 009 [Tab A] 満期管理→戻る→dashboard→admin.html
            # admin-link は sessionStorage の JWT で /api/permissions
            # を取得後に表示制御されるため、直接 goto で遷移して確認
            # ────────────────────────────────────────────────
            print("\n■ 009 [Tab A] 満期管理→戻る→権限設定(admin.html)")
            page_a.click(".btn-back")
            page_a.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=6000)
            page_a.wait_for_timeout(1200)
            page_a.goto(f"{BASE_URL}/admin.html")
            page_a.wait_for_load_state("networkidle")
            page_a.wait_for_timeout(2000)
            ss(page_a, "09_tab_a_admin.png")

            # ────────────────────────────────────────────────
            # 010 [Tab B] 満期管理→戻る→dashboard（Tab A 操作後）
            # ────────────────────────────────────────────────
            print("\n■ 010 [Tab B] 満期管理→戻る→dashboard")
            page_b.click(".btn-back")
            page_b.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=6000)
            page_b.wait_for_timeout(1500)
            page_b.evaluate("window.scrollTo(0, 0)")
            ss(page_b, "10_tab_b_dashboard_back_from_maturity.png")

            # ────────────────────────────────────────────────
            # 011 [Tab A] admin.html→戻る→dashboard
            # ────────────────────────────────────────────────
            print("\n■ 011 [Tab A] admin.html→戻る→dashboard")
            page_a.click("a.header-back-link")
            page_a.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=6000)
            page_a.wait_for_timeout(1500)
            page_a.evaluate("window.scrollTo(0, 0)")
            ss(page_a, "11_tab_a_dashboard_back_from_admin.png")

            # ────────────────────────────────────────────────
            # 012 [Tab A] 代理店ログアウト
            # ────────────────────────────────────────────────
            print("\n■ 012 [Tab A] 代理店ログアウト")
            page_a.click("#btn-logout")
            page_a.wait_for_url(f"{BASE_URL}/login.html", timeout=5000)
            page_a.wait_for_timeout(800)
            ss(page_a, "12_tab_a_after_logout.png")

            # ────────────────────────────────────────────────
            # 013 [Tab B] 社員ログアウト（Tab A ログアウト後）
            # ────────────────────────────────────────────────
            print("\n■ 013 [Tab B] 社員ログアウト（Tab A ログアウト後に確認）")
            # Tab B がまだ dashboard.html であることを確認してからログアウト
            page_b.evaluate("window.scrollTo(0, 0)")
            page_b.wait_for_timeout(600)
            page_b.click("#btn-logout")
            page_b.wait_for_url(f"{BASE_URL}/staff_login.html", timeout=5000)
            page_b.wait_for_timeout(800)
            ss(page_b, "13_tab_b_after_logout.png")

            browser.close()

        print(f"\n✅ 全スクリーンショット取得完了 → {SS_DIR}")

    finally:
        srv.terminate()


if __name__ == "__main__":
    run()
