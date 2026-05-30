"""
権限管理テスト スクリーンショット取得スクリプト
シナリオ1: 一般担当ユーザー（権限なし確認）
シナリオ2: 管理者ユーザー（権限あり・ユーザー管理画面確認）
"""
import subprocess, time, sys, pathlib
from playwright.sync_api import sync_playwright, expect

BASE_URL   = "http://127.0.0.1:8080"
SS_DIR     = pathlib.Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)

def ss(page, name):
    path = str(SS_DIR / name)
    page.screenshot(path=path, full_page=False)
    print(f"  撮影: {name}")
    return path

def run():
    # フロントエンドをhttp-serverで配信
    frontend_dir = pathlib.Path(__file__).parent.parent.parent / "frontend"
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8080", "--directory", str(frontend_dir)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=120)
            ctx     = browser.new_context(viewport={"width": 1280, "height": 800})
            page    = ctx.new_page()

            # ────────────────────────────────────────────
            # シナリオ1：一般担当ユーザー（staff1）
            # ────────────────────────────────────────────
            print("\n■ シナリオ1：一般担当ユーザー（staff1）")

            # 01 ログイン画面
            page.goto(f"{BASE_URL}/login.html")
            page.wait_for_load_state("networkidle")
            ss(page, "01_login.png")

            # 02 一般担当でログイン → ダッシュボード遷移直後
            page.fill("#agency-code", "A001")
            page.fill("#login-id",    "staff1")
            page.fill("#password",    "pass001")
            page.click("#btn-login")
            page.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=8000)
            page.wait_for_timeout(2500)
            ss(page, "02_dashboard_staff1.png")

            # 03 ヘッダー＋メニュー部分（権限制御確認）
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
            ss(page, "03_dashboard_staff1_permission.png")

            # 04 保険金支払状況ボタンをホバー → tooltip表示
            pay_btn = page.locator(".nav-btn[data-feature='PAYMENT_VIEW']")
            pay_btn.hover()
            page.wait_for_timeout(500)
            ss(page, "04_tooltip_no_permission.png")

            # 05 ログアウト → ログイン画面に戻る
            page.click("#btn-logout")
            page.wait_for_url(f"{BASE_URL}/login.html", timeout=5000)
            page.wait_for_timeout(500)
            ss(page, "05_logout_back_to_login.png")

            # ────────────────────────────────────────────
            # シナリオ2：管理者ユーザー（admin）
            # ────────────────────────────────────────────
            print("\n■ シナリオ2：管理者ユーザー（admin）")

            # 06 管理者でログイン → ダッシュボード遷移直後
            page.fill("#agency-code", "A001")
            page.fill("#login-id",    "admin")
            page.fill("#password",    "password123")
            page.click("#btn-login")
            page.wait_for_url(f"{BASE_URL}/dashboard.html", timeout=8000)
            page.wait_for_timeout(2500)
            ss(page, "06_dashboard_admin.png")

            # 07 ヘッダー＋メニュー（管理者リンク・全ボタン活性確認）
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
            ss(page, "07_dashboard_admin_permission.png")

            # 08 ユーザー管理リンクをクリック → admin.html
            page.click("#admin-link")
            page.wait_for_url(f"{BASE_URL}/admin.html", timeout=8000)
            page.wait_for_timeout(2500)
            ss(page, "08_admin_page.png")

            # 09 ユーザー一覧テーブルが表示されている状態
            page.wait_for_selector("#users-tbody tr td", timeout=5000)
            page.evaluate("window.scrollTo(0, 0)")
            ss(page, "09_admin_user_list.png")

            # 10 ユーザー追加モーダルを開く
            page.click("#btn-add-user")
            page.wait_for_selector("#modal-overlay", state="visible", timeout=3000)
            page.wait_for_timeout(400)
            ss(page, "10_admin_add_modal.png")

            # 11 モーダルを閉じて権限マトリクスまでスクロール
            page.click("#btn-cancel")
            page.wait_for_timeout(300)
            matrix = page.locator(".matrix-section")
            matrix.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            ss(page, "11_admin_permission_matrix.png")

            browser.close()

        print(f"\n✅ 全スクリーンショット取得完了 → {SS_DIR}")

    finally:
        srv.terminate()

if __name__ == "__main__":
    run()
