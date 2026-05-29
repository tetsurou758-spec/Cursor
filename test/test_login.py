"""
ログイン機能単体テスト (Playwright)
テスト対象: frontend/login.html  +  backend/main.py (FastAPI)

実行手順:
  1. uvicorn main:app --port 8000 をバックグラウンド起動
  2. python test/test_login.py
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
import openpyxl
from openpyxl.drawing.image import Image as XlImage

# ─── パス定数 ──────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent.parent
LOGIN_PAGE     = (BASE_DIR / "frontend" / "login.html").as_uri()
API_URL        = "http://127.0.0.1:8000/api/login"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
EXCEL_PATH     = Path(__file__).parent / "ログインテスト仕様書.xlsx"

# ─── テストケース定義 ───────────────────────────────────────────
# (明細番号, 代理店コード, ログインID, パスワード, 種別, 説明)
# 種別: api_success / api_fail / required_empty
TEST_CASES = [
    # 成功パターン 3件
    ("UT-LOGIN-001", "A001", "admin",   "password123",              "api_success",    "正常ログイン（A001/admin）"),
    ("UT-LOGIN-002", "B002", "agent1",  "pass456",                  "api_success",    "正常ログイン（B002/agent1）"),
    ("UT-LOGIN-003", "C003", "user1",   "pass789",                  "api_success",    "正常ログイン（C003/user1）"),
    # 失敗パターン 全件
    ("UT-LOGIN-004", "X999", "admin",   "password123",              "api_fail",       "代理店コード誤り"),
    ("UT-LOGIN-005", "A001", "unknown", "password123",              "api_fail",       "ログインID誤り"),
    ("UT-LOGIN-006", "A001", "admin",   "wrongpass",                "api_fail",       "パスワード誤り"),
    ("UT-LOGIN-007", "",     "admin",   "password123",              "required_empty", "代理店コード未入力"),
    ("UT-LOGIN-008", "A001", "",        "password123",              "required_empty", "ログインID未入力"),
    ("UT-LOGIN-009", "A001", "admin",   "",                         "required_empty", "パスワード未入力"),
    ("UT-LOGIN-010", "",     "",        "",                         "required_empty", "全項目未入力"),
    ("UT-LOGIN-011", "XXXXX","YYYYY",   "ZZZZZ",                    "api_fail",       "全項目不正値"),
    ("UT-LOGIN-012", "' OR '1'='1", "admin", "password123",         "api_fail",       "SQLインジェクション"),
    ("UT-LOGIN-013", "A001", "<script>alert(1)</script>", "password123", "api_fail",  "XSS攻撃"),
]


# ─── ヘルパー関数 ───────────────────────────────────────────────

def fill_form(page, agency_code, login_id, password):
    """フォームに値を入力する（空文字でフィールドをクリア）"""
    page.locator("#agency-code").fill(agency_code)
    page.locator("#login-id").fill(login_id)
    page.locator("#password").fill(password)


def call_api(page, agency_code, login_id, password) -> dict:
    """JavaScriptのfetchでAPIを直接呼び出す（CORS回避のためJS経由）"""
    return page.evaluate("""
        async ([url, body]) => {
            try {
                const r = await fetch(url, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
                return { status: r.status, data: await r.json() };
            } catch (e) {
                return { status: 0, error: e.message };
            }
        }
    """, [API_URL, {"agency_code": agency_code, "login_id": login_id, "password": password}])


def inject_banner(page, ok: bool, msg: str):
    """テスト結果バナーをページ上部に注入する"""
    c  = "#155724" if ok else "#721c24"
    bg = "#d4edda" if ok else "#f8d7da"
    bd = "#c3e6cb" if ok else "#f5c6cb"
    ic = "OK" if ok else "NG"
    page.evaluate("""
        ([c, bg, bd, ic, msg]) => {
            document.getElementById("__tr")?.remove();
            const d = document.createElement("div");
            d.id = "__tr";
            Object.assign(d.style, {
                position: "fixed", top: "12px", left: "50%",
                transform: "translateX(-50%)",
                background: bg, color: c,
                border: "1.5px solid " + bd,
                borderRadius: "6px", padding: "10px 28px",
                fontFamily: "'Hiragino Sans', Meiryo, sans-serif",
                fontSize: "13px", fontWeight: "bold",
                boxShadow: "0 2px 10px rgba(0,0,0,.18)",
                whiteSpace: "nowrap", zIndex: "9999",
            });
            d.textContent = "[" + ic + "] " + msg;
            document.body.appendChild(d);
        }
    """, [c, bg, bd, ic, msg])


def run_one(page, test_id, agency_code, login_id, password, test_type, description) -> str:
    """1件のテストを実行してスクリーンショットパスを返す"""
    print(f"  [{test_id}] {description}")

    # ページを開く
    page.goto(LOGIN_PAGE)
    page.wait_for_load_state("domcontentloaded")

    # フォームに入力値をセットする
    fill_form(page, agency_code, login_id, password)

    if test_type == "required_empty":
        # 送信ボタンをクリックしてブラウザの required バリデーションを発火させる
        page.locator("button[type='submit']").click()
        page.wait_for_timeout(800)
        inject_banner(page, True, f"ブラウザ必須バリデーション動作確認（送信ブロック）: {description}")

    else:
        # fetchでAPIを直接呼び出して結果を確認する
        res = call_api(page, agency_code, login_id, password)
        st  = res.get("status", 0)

        if test_type == "api_success":
            ok  = (st == 200)
            nm  = (res.get("data") or {}).get("name", "")
            msg = (f"ログイン成功 — {nm}  (HTTP {st})" if ok
                   else f"ログイン失敗  (HTTP {st}): {(res.get('data') or {}).get('detail','')}")
        else:
            ok  = (st == 401)
            det = ((res.get("data") or {}).get("detail") or "")[:60]
            msg = (f"認証エラー確認  (HTTP {st}): {det}" if ok
                   else f"予期しないレスポンス (HTTP {st}): {res.get('error','')}")

        inject_banner(page, ok, msg)

    page.wait_for_timeout(500)

    # スクリーンショットを保存する
    path = str(SCREENSHOT_DIR / f"{test_id}.png")
    page.screenshot(path=path)
    return path


# ─── テスト実行 ─────────────────────────────────────────────────

def run_all() -> dict:
    """全テストケースを実行してスクリーンショットパスの辞書を返す"""
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx     = browser.new_context(viewport={"width": 1280, "height": 800})
        page    = ctx.new_page()

        for row in TEST_CASES:
            results[row[0]] = run_one(page, *row)

        browser.close()

    return results


# ─── Excel 貼付 ─────────────────────────────────────────────────

def embed_screenshots(paths: dict):
    """xlsxの各明細Noシートにスクリーンショットを貼り付けて保存する"""
    wb = openpyxl.load_workbook(str(EXCEL_PATH))

    for test_id, img_path in paths.items():
        if test_id not in wb.sheetnames:
            print(f"  スキップ（シートなし）: {test_id}")
            continue
        if not os.path.exists(img_path):
            print(f"  スキップ（画像なし）: {img_path}")
            continue

        ws  = wb[test_id]
        img = XlImage(img_path)
        # 1280×800px のスクリーンショットを Excel 上で適切なサイズに縮小する
        img.width  = 900
        img.height = 563
        ws.add_image(img, "A3")
        # 画像が収まるよう行高を設定する（1pt ≈ 1.333px）
        ws.row_dimensions[3].height = 430
        ws.column_dimensions["A"].width = 18
        print(f"  貼付完了: {test_id}")

    wb.save(str(EXCEL_PATH))
    print(f"\n  Excel保存: {EXCEL_PATH}")


# ─── エントリーポイント ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  ログイン機能単体テスト 開始")
    print("=" * 50)

    print("\n【Step 1】Playwright テスト実行 ...")
    paths = run_all()
    print(f"  スクリーンショット保存完了: {len(paths)}件\n")

    print("【Step 2】Excel へスクリーンショット貼付 ...")
    embed_screenshots(paths)

    print("\n" + "=" * 50)
    print("  完了")
    print("=" * 50)
