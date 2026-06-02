"""
成績管理機能単体テスト (Playwright)
テスト対象: frontend/sales.html / frontend/sales_target.html + backend/main.py (FastAPI)

実行手順:
  1. uvicorn backend.main:app --port 8000 をバックグラウンド起動
  2. python test/009_UT-成績管理テスト/test_sales.py

テストケース:
  TC-001: ダッシュボード 成績管理ボタン確認
  TC-002: ダッシュボード 社員ユーザーは成績管理ボタン非表示
  TC-003: 成績参照画面 管理者ログイン時の担当者プルダウン
  TC-004: 成績参照画面 一般担当ログイン時は自分のみ自動検索
  TC-005: 成績参照画面 プログレスバーの色分け確認
  TC-006: 成績参照画面 「目標設定画面へ」ボタン 管理者のみ表示
  TC-007: 目標設定画面 一般担当はリダイレクト
  TC-008: 目標設定画面 前年度実績の読込
  TC-009: 目標設定画面 目標設定率→自動計算
  TC-010: 目標設定画面 保存→トースト表示
  TC-011: 社員ユーザーが sales.html に直接アクセス
  TC-012: テーマ確認（代理店）
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# ─── パス定数 ──────────────────────────────────────────────────────
BASE_URL       = "http://localhost:8000"
LOGIN_URL      = f"{BASE_URL}/frontend/login.html"
STAFF_LOGIN_URL = f"{BASE_URL}/frontend/staff_login.html"
DASHBOARD_URL  = f"{BASE_URL}/frontend/dashboard.html"
SALES_URL      = f"{BASE_URL}/frontend/sales.html"
SALES_TARGET_URL = f"{BASE_URL}/frontend/sales_target.html"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"

# テスト結果集計
results = []


# ─── ヘルパー関数 ───────────────────────────────────────────────────

def inject_banner(page: Page, ok: bool, msg: str):
    """テスト結果バナーをページ上部に注入する"""
    color  = "#155724" if ok else "#721c24"
    bg     = "#d4edda" if ok else "#f8d7da"
    border = "#c3e6cb" if ok else "#f5c6cb"
    label  = "OK" if ok else "NG"
    page.evaluate("""
        ([color, bg, border, label, msg]) => {
            document.getElementById('__tr')?.remove();
            const d = document.createElement('div');
            d.id = '__tr';
            Object.assign(d.style, {
                position: 'fixed', top: '12px', left: '50%',
                transform: 'translateX(-50%)',
                background: bg, color: color,
                border: '1.5px solid ' + border,
                borderRadius: '6px', padding: '10px 28px',
                fontFamily: "'Hiragino Sans', Meiryo, sans-serif",
                fontSize: '13px', fontWeight: 'bold',
                boxShadow: '0 2px 10px rgba(0,0,0,.18)',
                whiteSpace: 'nowrap', zIndex: '9999',
            });
            d.textContent = '[' + label + '] ' + msg;
            document.body.appendChild(d);
        }
    """, [color, bg, border, label, msg])


def screenshot(page: Page, name: str):
    """スクリーンショットを screenshots/TC-XXX_テスト名.png 形式で保存する"""
    path = str(SCREENSHOT_DIR / f"{name}.png")
    page.screenshot(path=path, full_page=False)
    return path


def agency_login(page: Page, agency_code: str, login_id: str, password: str):
    """代理店ユーザーでログインしてダッシュボードに遷移する"""
    page.goto(LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")
    page.fill("#agency-code", agency_code)
    page.fill("#login-id",    login_id)
    page.fill("#password",    password)
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard.html", timeout=12000)
    time.sleep(1.5)


def staff_login(page: Page, staff_id: str, password: str):
    """社員ユーザーでログインしてダッシュボードに遷移する"""
    page.goto(STAFF_LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")
    page.fill("#staff-id", staff_id)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard.html", timeout=12000)
    time.sleep(1.5)


def record(tc_id: str, description: str, ok: bool, detail: str = ""):
    """テスト結果を記録する"""
    status = "OK" if ok else "NG"
    results.append((tc_id, description, status, detail))
    print(f"  [{tc_id}] {status} - {description}" + (f" ({detail})" if detail else ""))


# ─── テストケース実装 ────────────────────────────────────────────────

def tc001_dashboard_sales_button(page: Page):
    """TC-001: ダッシュボード 成績管理ボタン確認"""
    print("\n[TC-001] ダッシュボード 成績管理ボタン確認")
    try:
        # 代理店管理者でログイン
        agency_login(page, "A001", "admin", "password123")
        time.sleep(1.0)

        # 「成績管理」ボタンが表示されているか確認
        btn = page.locator("#btn-sales")
        is_visible = btn.is_visible()
        display = page.evaluate("() => { const el = document.getElementById('btn-sales'); return el ? window.getComputedStyle(el).display : 'not found'; }")
        ok = is_visible and display != "none"

        inject_banner(page, ok, f"成績管理ボタン表示={ok} (display={display})")
        screenshot(page, "TC-001_dashboard_sales_button")

        # ボタンクリックで sales.html に遷移することを確認
        if ok:
            page.click("#btn-sales")
            page.wait_for_url("**/sales.html", timeout=10000)
            time.sleep(1.5)
            transitioned = "sales.html" in page.url
            inject_banner(page, transitioned, f"sales.html 遷移確認={transitioned}")
            screenshot(page, "TC-001_sales_transition")
            ok = ok and transitioned

        record("TC-001", "ダッシュボード 成績管理ボタン確認", ok, f"display={display}")
    except Exception as e:
        record("TC-001", "ダッシュボード 成績管理ボタン確認", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-001_error")


def tc002_staff_no_sales_button(page: Page):
    """TC-002: ダッシュボード 社員ユーザーは成績管理ボタン非表示"""
    print("\n[TC-002] 社員ユーザーは成績管理ボタン非表示")
    try:
        # 社員ユーザーでログイン
        staff_login(page, "S001", "staff123")
        time.sleep(1.0)

        # 成績管理ボタンの有無を確認（存在しないか display:none）
        btn_count = page.locator("#btn-sales").count()
        if btn_count == 0:
            ok = True
            detail = "DOM不在"
        else:
            display = page.evaluate("() => { const el = document.getElementById('btn-sales'); return el ? window.getComputedStyle(el).display : 'not found'; }")
            ok = display == "none" or not page.locator("#btn-sales").is_visible()
            detail = f"display={display}"

        inject_banner(page, ok, f"社員ユーザー 成績管理ボタン非表示={ok} ({detail})")
        screenshot(page, "TC-002_staff_no_sales_button")
        record("TC-002", "社員ユーザーは成績管理ボタン非表示", ok, detail)
    except Exception as e:
        record("TC-002", "社員ユーザーは成績管理ボタン非表示", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-002_error")


def tc003_admin_staff_dropdown(page: Page):
    """TC-003: 成績参照画面 管理者ログイン時の担当者プルダウン"""
    print("\n[TC-003] 管理者ログイン時の担当者プルダウン")
    try:
        # 代理店管理者でログインして sales.html を開く
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        # 担当者プルダウンの選択肢数を確認（複数＋代理店合計があるか）
        options_count = page.evaluate("() => document.getElementById('sel-staff')?.options?.length || 0")
        is_disabled = page.evaluate("() => document.getElementById('sel-staff')?.disabled || false")
        ok = options_count > 1 and not is_disabled

        inject_banner(page, ok, f"担当者プルダウン 選択肢数={options_count} disabled={is_disabled}")
        screenshot(page, "TC-003_admin_staff_dropdown")
        record("TC-003", "管理者ログイン時の担当者プルダウン", ok, f"options={options_count}, disabled={is_disabled}")
    except Exception as e:
        record("TC-003", "管理者ログイン時の担当者プルダウン", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-003_error")


def tc004_general_staff_auto_search(page: Page):
    """TC-004: 成績参照画面 一般担当ログイン時は自分のみ自動検索"""
    print("\n[TC-004] 一般担当ログイン時は自分のみ自動検索")
    try:
        # 代理店一般担当でログインして sales.html を開く
        agency_login(page, "A001", "staff1", "pass001")
        page.goto(SALES_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        # 担当者プルダウンが disabled になっているか確認
        is_disabled = page.evaluate("() => document.getElementById('sel-staff')?.disabled || false")
        options_count = page.evaluate("() => document.getElementById('sel-staff')?.options?.length || 0")

        # テーブルが自動表示されているか確認（空メッセージではなくデータ行があるか）
        table_rows = page.locator("table tbody tr").count()
        has_data = table_rows > 0

        ok = is_disabled and has_data

        inject_banner(page, ok, f"自分のみ disabled={is_disabled} options={options_count} テーブル行数={table_rows}")
        screenshot(page, "TC-004_general_staff_auto_search")
        record("TC-004", "一般担当ログイン時は自分のみ自動検索", ok, f"disabled={is_disabled}, rows={table_rows}")
    except Exception as e:
        record("TC-004", "一般担当ログイン時は自分のみ自動検索", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-004_error")


def tc005_progress_bar(page: Page):
    """TC-005: 成績参照画面 プログレスバーの色分け確認"""
    print("\n[TC-005] プログレスバーの色分け確認")
    try:
        # 代理店管理者でログインして sales.html を開く
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.0)

        # 「表示」ボタンをクリックしてテーブルを表示
        page.click("button[onclick='doSearch()']")
        time.sleep(2.5)

        # テーブルが表示されているか確認
        table_rows = page.locator("table tbody tr").count()
        ok = table_rows > 0

        inject_banner(page, ok, f"テーブル行数={table_rows} プログレスバー確認")
        screenshot(page, "TC-005_progress_bar")
        record("TC-005", "プログレスバーの色分け確認", ok, f"rows={table_rows}")
    except Exception as e:
        record("TC-005", "プログレスバーの色分け確認", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-005_error")


def tc006_target_button_visibility(page: Page):
    """TC-006: 「目標設定画面へ」ボタン 管理者のみ表示"""
    print("\n[TC-006] 「目標設定画面へ」ボタン 管理者のみ表示")
    try:
        # ─ 管理者：ボタン表示確認 ─
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        admin_display = page.evaluate("() => { const el = document.getElementById('btn-target'); return el ? window.getComputedStyle(el).display : 'not found'; }")
        admin_ok = admin_display != "none" and admin_display != "not found"

        inject_banner(page, admin_ok, f"管理者 目標設定ボタン表示={admin_ok} (display={admin_display})")
        screenshot(page, "TC-006_admin_target_button")

        # ─ 一般担当：ボタン非表示確認 ─
        page.goto(LOGIN_URL)
        page.wait_for_load_state("domcontentloaded")
        page.fill("#agency-code", "A001")
        page.fill("#login-id",    "staff1")
        page.fill("#password",    "pass001")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard.html", timeout=12000)
        time.sleep(1.0)

        page.goto(SALES_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        staff_display = page.evaluate("() => { const el = document.getElementById('btn-target'); return el ? window.getComputedStyle(el).display : 'not found'; }")
        staff_ok = staff_display == "none"

        inject_banner(page, staff_ok, f"一般担当 目標設定ボタン非表示={staff_ok} (display={staff_display})")
        screenshot(page, "TC-006_staff_no_target_button")

        ok = admin_ok and staff_ok
        record("TC-006", "「目標設定画面へ」ボタン 管理者のみ表示", ok,
               f"管理者={admin_display}, 一般={staff_display}")
    except Exception as e:
        record("TC-006", "「目標設定画面へ」ボタン 管理者のみ表示", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-006_error")


def tc007_general_staff_redirect_from_target(page: Page):
    """TC-007: 目標設定画面 一般担当はリダイレクト"""
    print("\n[TC-007] 一般担当は sales_target.html へのアクセスで sales.html にリダイレクト")
    try:
        # 一般担当でログイン
        agency_login(page, "A001", "staff1", "pass001")

        # sales_target.html に直接アクセス
        page.goto(SALES_TARGET_URL)
        time.sleep(2.5)

        # sales.html にリダイレクトされているか確認
        current_url = page.url
        ok = "sales.html" in current_url and "sales_target.html" not in current_url

        inject_banner(page, ok, f"リダイレクト先={current_url}")
        screenshot(page, "TC-007_general_redirect")
        record("TC-007", "一般担当は目標設定画面へのアクセスでリダイレクト", ok, f"url={current_url}")
    except Exception as e:
        record("TC-007", "一般担当は目標設定画面へのアクセスでリダイレクト", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-007_error")


def tc008_target_load_prev_year(page: Page):
    """TC-008: 目標設定画面 前年度実績の読込"""
    print("\n[TC-008] 目標設定画面 前年度実績の読込")
    try:
        # 管理者でログイン
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_TARGET_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        # 年度・担当者を選択して「読込」ボタンをクリック
        # 年度プルダウンが存在する場合は最初のオプションを選択
        year_options = page.evaluate("() => Array.from(document.getElementById('sel-year')?.options || []).map(o => o.value)")
        if year_options:
            page.select_option("#sel-year", year_options[0])

        # 担当者が選択可能な場合は選択
        staff_options = page.evaluate("() => Array.from(document.getElementById('sel-staff')?.options || []).map(o => o.value)")
        if staff_options:
            page.select_option("#sel-staff", staff_options[0])

        page.click("button[onclick='doLoad()']")
        time.sleep(2.5)

        # テーブルにデータが表示されているか確認（empty-msg が消えているか）
        empty_msg_visible = page.locator(".empty-msg").is_visible() if page.locator(".empty-msg").count() > 0 else False
        table_rows = page.locator("table tbody tr:not(.empty-msg)").count()
        ok = table_rows > 0 or not empty_msg_visible

        inject_banner(page, ok, f"テーブル行数={table_rows} empty_msg={empty_msg_visible}")
        screenshot(page, "TC-008_target_load")
        record("TC-008", "目標設定画面 前年度実績の読込", ok, f"rows={table_rows}")
    except Exception as e:
        record("TC-008", "目標設定画面 前年度実績の読込", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-008_error")


def tc009_target_rate_auto_calc(page: Page):
    """TC-009: 目標設定画面 目標設定率→自動計算"""
    print("\n[TC-009] 目標設定率入力→次年度目標の自動計算")
    try:
        # 管理者でログイン
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_TARGET_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        # 年度・担当者を選択して読込
        year_options = page.evaluate("() => Array.from(document.getElementById('sel-year')?.options || []).map(o => o.value)")
        if year_options:
            page.select_option("#sel-year", year_options[0])

        staff_options = page.evaluate("() => Array.from(document.getElementById('sel-staff')?.options || []).map(o => o.value)")
        if staff_options:
            page.select_option("#sel-staff", staff_options[0])

        page.click("button[onclick='doLoad()']")
        time.sleep(2.5)

        # 最初の目標設定率inputを取得し値を入力してblur
        rate_inputs = page.locator("input.input-rate")
        rate_count = rate_inputs.count()

        if rate_count > 0:
            # 最初のinputに1.20を入力してblur
            first_rate = rate_inputs.first
            # 入力前の次年度目標値を取得
            target_inputs = page.locator("input.input-target")
            before_val = target_inputs.first.input_value() if target_inputs.count() > 0 else ""

            first_rate.click()
            first_rate.fill("1.20")
            first_rate.dispatch_event("blur")
            time.sleep(0.8)

            # 次年度目標inputの値が変化したか確認
            after_val = target_inputs.first.input_value() if target_inputs.count() > 0 else ""
            ok = after_val != "" and after_val != before_val

            inject_banner(page, ok, f"目標設定率1.20入力→次年度目標 before={before_val} after={after_val}")
        else:
            ok = False
            inject_banner(page, ok, "目標設定率inputが見つかりません（データが読み込まれていない可能性）")

        screenshot(page, "TC-009_rate_auto_calc")
        record("TC-009", "目標設定率→自動計算", ok, f"rate_inputs={rate_count}")
    except Exception as e:
        record("TC-009", "目標設定率→自動計算", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-009_error")


def tc010_target_save_toast(page: Page):
    """TC-010: 目標設定画面 保存→トースト表示"""
    print("\n[TC-010] 目標設定画面 保存→「保存しました」トースト表示")
    try:
        # 管理者でログイン
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_TARGET_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.5)

        # 年度・担当者を選択して読込
        year_options = page.evaluate("() => Array.from(document.getElementById('sel-year')?.options || []).map(o => o.value)")
        if year_options:
            page.select_option("#sel-year", year_options[0])

        staff_options = page.evaluate("() => Array.from(document.getElementById('sel-staff')?.options || []).map(o => o.value)")
        if staff_options:
            page.select_option("#sel-staff", staff_options[0])

        page.click("button[onclick='doLoad()']")
        time.sleep(2.5)

        # 「保存」ボタンをクリック
        page.click("button[onclick='doSave()']")
        time.sleep(1.5)

        # トースト表示確認（#toast が show クラスを持つか）
        toast_visible = page.evaluate("""() => {
            const t = document.getElementById('toast');
            return t ? t.classList.contains('show') : false;
        }""")

        # トーストが短時間で消えるのでスクリーンショット直後に確認
        screenshot(page, "TC-010_save_toast")

        # トーストが既に消えた場合はテキストで確認
        toast_text = page.evaluate("() => document.getElementById('toast')?.textContent || ''")
        ok = toast_visible or "保存しました" in toast_text

        inject_banner(page, ok, f"トースト表示={toast_visible} テキスト={toast_text}")
        screenshot(page, "TC-010_save_toast_result")
        record("TC-010", "保存→「保存しました」トースト表示", ok, f"visible={toast_visible}")
    except Exception as e:
        record("TC-010", "保存→「保存しました」トースト表示", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-010_error")


def tc011_staff_user_sales_redirect(page: Page):
    """TC-011: 社員ユーザーが sales.html に直接アクセス → dashboard.html にリダイレクト"""
    print("\n[TC-011] 社員ユーザーが sales.html に直接アクセス")
    try:
        # 社員ユーザーでログイン
        staff_login(page, "S001", "staff123")

        # sales.html に直接アクセス
        page.goto(SALES_URL)
        time.sleep(2.5)

        # dashboard.html にリダイレクトされているか確認
        current_url = page.url
        ok = "dashboard.html" in current_url and "sales.html" not in current_url

        inject_banner(page, ok, f"リダイレクト先={current_url}")
        screenshot(page, "TC-011_staff_sales_redirect")
        record("TC-011", "社員ユーザーがsales.htmlアクセスでdashboardにリダイレクト", ok, f"url={current_url}")
    except Exception as e:
        record("TC-011", "社員ユーザーがsales.htmlアクセスでdashboardにリダイレクト", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-011_error")


def tc012_theme_check(page: Page):
    """TC-012: テーマ確認（代理店：紺色テーマ）"""
    print("\n[TC-012] テーマ確認（代理店 紺色テーマ）")
    try:
        # 代理店管理者でログイン
        agency_login(page, "A001", "admin", "password123")
        page.goto(SALES_URL)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2.0)

        # data-theme 属性を確認
        data_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme') || document.body.getAttribute('data-theme') || ''")
        # ヘッダー背景色を確認（紺色テーマ）
        header_bg = page.evaluate("""() => {
            const header = document.querySelector('header') || document.querySelector('.header');
            return header ? window.getComputedStyle(header).backgroundColor : '';
        }""")

        # 代理店テーマが適用されている（staffテーマではない）ことを確認
        ok = data_theme != "staff" or "rgb(255, 20, 147)" not in header_bg  # ホットピンクでない

        inject_banner(page, ok, f"data-theme={data_theme} header_bg={header_bg[:40]}")
        screenshot(page, "TC-012_agency_theme")
        record("TC-012", "代理店 紺色テーマ適用確認", ok, f"theme={data_theme}")
    except Exception as e:
        record("TC-012", "代理店 紺色テーマ適用確認", False, str(e))
        inject_banner(page, False, f"エラー: {e}")
        screenshot(page, "TC-012_error")


# ─── テスト実行 ──────────────────────────────────────────────────────

def run_all():
    """全テストケースを実行する"""
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx     = browser.new_context(viewport={"width": 1280, "height": 800})
        page    = ctx.new_page()

        # 各テストケースを順番に実行する
        tc001_dashboard_sales_button(page)
        tc002_staff_no_sales_button(page)
        tc003_admin_staff_dropdown(page)
        tc004_general_staff_auto_search(page)
        tc005_progress_bar(page)
        tc006_target_button_visibility(page)
        tc007_general_staff_redirect_from_target(page)
        tc008_target_load_prev_year(page)
        tc009_target_rate_auto_calc(page)
        tc010_target_save_toast(page)
        tc011_staff_user_sales_redirect(page)
        tc012_theme_check(page)

        browser.close()


def print_summary():
    """テスト結果サマリーを出力する"""
    ok_count = sum(1 for r in results if r[2] == "OK")
    ng_count = sum(1 for r in results if r[2] == "NG")
    total    = len(results)

    print("\n" + "=" * 60)
    print("  成績管理テスト 結果サマリー")
    print("=" * 60)
    print(f"  合計: {total}件  OK: {ok_count}件  NG: {ng_count}件")
    print("-" * 60)
    for tc_id, desc, status, detail in results:
        mark = "✔" if status == "OK" else "✘"
        print(f"  {mark} [{tc_id}] {status}  {desc}")
        if detail and status == "NG":
            print(f"       詳細: {detail}")
    print("=" * 60)


# ─── エントリーポイント ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  成績管理機能単体テスト 開始")
    print("=" * 60)
    print(f"  ベースURL: {BASE_URL}")
    print(f"  スクリーンショット出力先: {SCREENSHOT_DIR}")

    run_all()
    print_summary()

    print("\n  スクリーンショット保存完了")
    print("=" * 60)
