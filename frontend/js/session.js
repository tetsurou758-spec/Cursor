/**
 * session.js - 認証セッション共通ユーティリティ
 *
 * タブ別にセッションを独立管理するためsessionStorageを主ストレージとする。
 * localStorageにデータが存在する場合はsessionStorageへ移行して使用する（後方互換）。
 */

// ─── 保存キー定数 ─────────────────────────────────────────────
const KEY = {
  USER_TYPE:   'user_type',
  JWT_TOKEN:   'jwt_token',
  USER_INFO:   'user_info',
  // 後方互換用（既存画面が直接参照するキーを維持）
  AGENCY_TOKEN:      'token',
  AGENCY_CODE:       'agency_code',
  AGENCY_LOGIN_ID:   'login_id',
  AGENCY_NAME:       'name',
  STAFF_TOKEN:       'staff_token',
  STAFF_CODE:        'staff_code',
  STAFF_NAME:        'staff_name',
  STAFF_ROLE_ID:     'staff_role_id',
  STAFF_ROLE_NAME:   'staff_role_name',
  STAFF_BUKA_CODE:   'staff_buka_code',
  STAFF_PERMISSIONS: 'staff_permissions',
};

/**
 * sessionStorageから値を取得する。
 * 未設定の場合はlocalStorageから読み込んでsessionStorageへ移行する。
 * @param {string} key
 * @returns {string|null}
 */
function _ssGet(key) {
  let val = sessionStorage.getItem(key);
  if (val === null) {
    val = localStorage.getItem(key);
    if (val !== null) sessionStorage.setItem(key, val);
  }
  return val;
}

/**
 * 代理店ログイン成功時にsessionStorageへ保存する。
 * タブ毎に独立したセッションを持たせるためlocalStorageには書き込まない。
 * @param {string} token - JWTアクセストークン
 * @param {string} agencyCode
 * @param {string} loginId
 * @param {string} name
 * @param {number} roleId
 * @param {string} roleName
 * @param {string} groupCode
 * @param {string[]} permissions
 */
function saveAgencySession(token, agencyCode, loginId, name, roleId, roleName, groupCode, permissions) {
  sessionStorage.setItem(KEY.USER_TYPE,  'agency');
  sessionStorage.setItem(KEY.JWT_TOKEN,  token);
  sessionStorage.setItem(KEY.USER_INFO,  JSON.stringify({
    user_type: 'agency', agency_code: agencyCode, login_id: loginId,
    name, role_id: roleId, role_name: roleName, group_code: groupCode, permissions,
  }));
  // 後方互換キーもsessionStorageに保存する
  sessionStorage.setItem(KEY.AGENCY_TOKEN,    token);
  sessionStorage.setItem(KEY.AGENCY_CODE,     agencyCode);
  sessionStorage.setItem(KEY.AGENCY_LOGIN_ID, loginId);
  sessionStorage.setItem(KEY.AGENCY_NAME,     name);
}

/**
 * 社員ログイン成功時にsessionStorageへ保存する。
 * @param {string} token - JWTアクセストークン
 * @param {string} staffCode
 * @param {string} name
 * @param {number} roleId
 * @param {string} roleName
 * @param {string} bukaCode
 * @param {string[]} permissions
 * @param {string[]} managedAgencies
 */
function saveStaffSession(token, staffCode, name, roleId, roleName, bukaCode, permissions, managedAgencies) {
  sessionStorage.setItem(KEY.USER_TYPE,  'staff');
  sessionStorage.setItem(KEY.JWT_TOKEN,  token);
  sessionStorage.setItem(KEY.USER_INFO,  JSON.stringify({
    user_type: 'staff', staff_code: staffCode, name,
    role_id: roleId, role_name: roleName, buka_code: bukaCode,
    permissions, managed_agencies: managedAgencies,
  }));
  // 後方互換キーもsessionStorageに保存する
  sessionStorage.setItem(KEY.STAFF_TOKEN,       token);
  sessionStorage.setItem(KEY.STAFF_CODE,        staffCode);
  sessionStorage.setItem(KEY.STAFF_NAME,        name);
  sessionStorage.setItem(KEY.STAFF_ROLE_ID,     String(roleId));
  sessionStorage.setItem(KEY.STAFF_ROLE_NAME,   roleName);
  sessionStorage.setItem(KEY.STAFF_BUKA_CODE,   bukaCode);
  sessionStorage.setItem(KEY.STAFF_PERMISSIONS, JSON.stringify(permissions));
}

/**
 * sessionStorageからuser_infoオブジェクトを取得する。
 * 未ログインの場合はnullを返す。
 * @returns {object|null}
 */
function getUserInfo() {
  const raw = _ssGet(KEY.USER_INFO);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

/**
 * JWTトークンを返す。sessionStorage優先、なければlocalStorageから移行する。
 * @returns {string|null}
 */
function getToken() {
  return _ssGet(KEY.JWT_TOKEN) || null;
}

/**
 * data-theme属性をdocument.documentElementに設定してテーマを適用する。
 * theme.cssのCSS変数定義と連動する。
 */
function applyTheme() {
  const userType = sessionStorage.getItem('user_type');
  document.documentElement.setAttribute(
    'data-theme',
    userType === 'staff' ? 'staff' : 'agency'
  );
}

/**
 * ダッシュボードへ遷移する。統合後はdashboard.htmlに一本化。
 * user_typeの判定はdashboard.html側で行う。
 */
function goToDashboard() {
  window.location.href = 'dashboard.html';
}

/**
 * ユーザー種別に応じたログイン画面URLを返す。
 * @returns {string}
 */
function getLoginUrl() {
  const userType = _ssGet(KEY.USER_TYPE);
  return (userType === 'staff') ? 'staff_login.html' : 'login.html';
}

/**
 * ログアウト処理。
 * sessionStorageとlocalStorageの両方をクリアし、ログイン画面へリダイレクトする。
 */
async function doLogout() {
  const loginUrl = getLoginUrl();
  Object.values(KEY).forEach(k => {
    sessionStorage.removeItem(k);
    localStorage.removeItem(k);
  });
  window.location.href = loginUrl;
}

/**
 * 認証ガード：未ログインの場合は適切なログイン画面へリダイレクトする。
 * ページロード時に呼び出す。
 * @returns {string|null} - ログイン済みならJWTトークン、未ログインならnull（リダイレクト実行）
 */
function requireAuth() {
  const token    = getToken();
  const userType = _ssGet(KEY.USER_TYPE);
  if (!token) {
    window.location.href = (userType === 'staff') ? 'staff_login.html' : 'login.html';
    return null;
  }
  return token;
}

/**
 * 認証ガード（代理店専用）：staff JWTでのアクセスを拒否する。
 * @returns {string|null}
 */
function requireAgencyAuth() {
  const token    = getToken();
  const userType = _ssGet(KEY.USER_TYPE);
  if (!token || userType === 'staff') {
    window.location.href = 'login.html';
    return null;
  }
  return token;
}

/**
 * 認証ガード（社員専用）：agency JWTでのアクセスを拒否する。
 * @returns {string|null}
 */
function requireStaffAuth() {
  const token    = getToken();
  const userType = _ssGet(KEY.USER_TYPE);
  if (!token || userType !== 'staff') {
    window.location.href = 'staff_login.html';
    return null;
  }
  return token;
}
