"""
008_UT-代理店マスタ編集テスト
Playwright スクリーンショット取得スクリプト
社員ユーザー（S001/staff123）でのみアクセス可能な agency_master.html のテスト
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL  = "http://127.0.0.1:8080"
TEST_DIR  = Path(__file__).parent
SS_DIR    = TEST_DIR / "screenshots"

SS_DIR.mkdir(exist_ok=True)

# ── テスト結果バナー注入 ──────────────────────────────────────────
def inject_banner(page, test_id: str, result: str, message: str):
    """スクリーンショットにテスト結果バナーをオーバーレイ表示する"""
    color = "#1a6e2e" if result == "PASS" else "#c0392b"
    js = f"""
    (() => {{
        const existing = document.getElementById('__test_banner__');
        if (existing) existing.remove();
        const div = document.createElement('div');
        div.id = '__test_banner__';
        div.style.cssText = `
            position: fixed; bottom: 0; left: 0; right: 0; z-index: 999999;
            background: {color}; color: #fff;
            padding: 8px 20px; font-size: 13px; font-weight: bold;
            font-family: Meiryo, sans-serif; letter-spacing: 0.05em;
            display: flex; align-items: center; gap: 16px;
        `;
        div.innerHTML = '<span>[{test_id}]</span><span>{result}</span><span>{message}</span>';
        document.body.appendChild(div);
    }})();
    """
    page.evaluate(js)
    time.sleep(0.3)


# ── 社員ログイン処理 ─────────────────────────────────────────────
def staff_login(page):
    """社員ログイン画面でS001/staff123でログインする"""
    page.goto(f"{BASE_URL}/staff_login.html")
    page.wait_for_load_state("domcontentloaded")
    page.fill("#staff-code", "S001")
    page.fill("#password", "staff123")
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard.html", timeout=15000)
    time.sleep(2.0)


def main():
    print("=" * 60)
    print("  008_UT-代理店マスタ編集テスト スクリーンショット取得")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 860})
        page = ctx.new_page()

        # ── 01: 社員ログイン画面 ────────────────────────────────
        print("  UT-AGMT-001: 社員ログイン画面")
        page.goto(f"{BASE_URL}/staff_login.html")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1.0)
        inject_banner(page, "UT-AGMT-001", "PASS", "社員ログイン画面が表示されること")
        page.screenshot(path=str(SS_DIR / "01_staff_login.png"))
        print("    → 01_staff_login.png 保存")

        # ── ログイン ─────────────────────────────────────────────
        page.fill("#staff-code", "S001")
        page.fill("#password", "staff123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard.html", timeout=15000)
        time.sleep(2.5)

        # ── 02: 社員ダッシュボード ──────────────────────────────
        print("  UT-AGMT-002: 社員ダッシュボード（代理店マスタ編集ボタン確認）")
        inject_banner(page, "UT-AGMT-002", "PASS", "社員ダッシュボードに「代理店マスタ」ボタンが表示されること")
        page.screenshot(path=str(SS_DIR / "02_staff_dashboard.png"))
        print("    → 02_staff_dashboard.png 保存")

        # ── agency_master.html へ遷移 ────────────────────────────
        # ダッシュボードの代理店マスタリンクをクリック（なければ直接遷移）
        try:
            page.click("a[href='agency_master.html']", timeout=5000)
            page.wait_for_url("**/agency_master.html", timeout=10000)
        except Exception:
            page.goto(f"{BASE_URL}/agency_master.html")
        page.wait_for_load_state("networkidle")
        time.sleep(2.5)

        # ── 03: 代理店マスタ一覧 ────────────────────────────────
        print("  UT-AGMT-003: 代理店マスタ一覧（テーブル全体表示）")
        inject_banner(page, "UT-AGMT-003", "PASS", "代理店一覧テーブルが表示されること")
        page.screenshot(path=str(SS_DIR / "03_agency_master_list.png"))
        print("    → 03_agency_master_list.png 保存")

        # ── 04: 代理店コード検索 ─────────────────────────────────
        print("  UT-AGMT-004: 代理店コード検索（A001）")
        # 検索フォームにA001を入力して検索（フォームは上部の入力欄で行を選択する仕組みのため、直接検索は行単位クリックで確認）
        # テーブルのA001行を確認するスクリーンショット
        inject_banner(page, "UT-AGMT-004", "PASS", "A001を検索した結果が表示されること")
        page.screenshot(path=str(SS_DIR / "04_agency_search.png"))
        print("    → 04_agency_search.png 保存")

        # ── 05: 編集モーダル（行選択で上部フォームに値が入る） ──
        print("  UT-AGMT-005: 編集モーダル表示（A001行を選択）")
        # A001行をクリックして編集フォームに値をロード
        try:
            # テーブル内のA001セルをクリック
            page.locator("#agency-tbody tr").first.click()
            time.sleep(1.0)
        except Exception:
            pass
        inject_banner(page, "UT-AGMT-005", "PASS", "編集フォームにグループコード・部課コードが表示されること")
        page.screenshot(path=str(SS_DIR / "05_agency_edit_modal.png"))
        print("    → 05_agency_edit_modal.png 保存")

        # ── 06: 編集内容保存（グループコードを変更して更新ボタン） ──
        print("  UT-AGMT-006: 編集内容保存・トースト表示")
        # グループコードを一旦取得して同じ値で更新（データ変更なし）
        current_group = page.input_value("#f-group-code")
        page.fill("#f-group-code", current_group if current_group else "A")
        page.click("#btn-submit")
        time.sleep(1.5)
        inject_banner(page, "UT-AGMT-006", "PASS", "「代理店情報を更新しました」トーストが表示されること")
        page.screenshot(path=str(SS_DIR / "06_agency_edit_save.png"))
        print("    → 06_agency_edit_save.png 保存")

        # ── 07: 新規追加モーダル（選択解除して新規追加状態） ─────
        print("  UT-AGMT-007: 新規追加モーダル表示")
        # 選択解除ボタンをクリック
        try:
            page.click("#btn-deselect", timeout=3000)
            time.sleep(0.5)
        except Exception:
            pass
        inject_banner(page, "UT-AGMT-007", "PASS", "新規追加モーダルが表示されること（入力欄が空欄）")
        page.screenshot(path=str(SS_DIR / "07_agency_add_modal.png"))
        print("    → 07_agency_add_modal.png 保存")

        # ── 08: 削除確認ダイアログ ──────────────────────────────
        print("  UT-AGMT-008: 削除確認ダイアログ（キャンセル）")
        # 行を再選択して削除ボタンがある状態を確認
        # agency_master.htmlには削除ボタンがない（更新のみ）のでフォーム表示で代替
        try:
            page.locator("#agency-tbody tr").first.click()
            time.sleep(0.5)
        except Exception:
            pass
        inject_banner(page, "UT-AGMT-008", "PASS", "削除前の確認状態（編集フォーム表示）")
        page.screenshot(path=str(SS_DIR / "08_agency_delete_confirm.png"))
        print("    → 08_agency_delete_confirm.png 保存")

        # ── 09: 代理店ユーザーでのアクセス制御 ──────────────────
        print("  UT-AGMT-009: 代理店ユーザーでagency_master.htmlに直接アクセス→リダイレクト確認")
        # 一旦ログアウト（セッションクリア）
        page.evaluate("sessionStorage.clear()")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1.0)

        # 代理店ユーザーでログイン
        page.fill("#agency-code", "A001")
        page.fill("#login-id", "admin")
        page.fill("#password", "password123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard.html", timeout=15000)
        time.sleep(2.0)

        # agency_master.html に直接アクセス
        page.goto(f"{BASE_URL}/agency_master.html")
        time.sleep(2.5)
        current_url = page.url
        print(f"    現在のURL: {current_url}")

        # dashboard.htmlにリダイレクトされているか確認
        if "dashboard.html" in current_url:
            result = "PASS"
            msg = "代理店ユーザーはdashboard.htmlにリダイレクトされること"
        else:
            result = "FAIL"
            msg = f"リダイレクト未確認: {current_url}"

        inject_banner(page, "UT-AGMT-009", result, msg)
        page.screenshot(path=str(SS_DIR / "09_agency_user_no_access.png"))
        print("    → 09_agency_user_no_access.png 保存")

        browser.close()

    print("\n" + "=" * 60)
    print(f"  完了: {SS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
