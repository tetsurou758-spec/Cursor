/**
 * session.js - 認証セッション共通ユーティリティ
 *
 * ログイン種別（agency / staff）を localStorage.user_type で管理し、
 * トークン保存・画面遷移・ログアウトを一元化する。
 */

// ─── 保存キー定数 ─────────────────────────────────────────────
const KEY = {
  USER_TYPE:   'user_type',
  JWT_TOKEN:   'jwt_token',
  USER_INFO:   'user_info',
  // 後方互換用（既存コードが直接参照している可能性があるため残す）
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
 * 代理店ログイン成功時にlocalStorageへ保存する。
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
  localStorage.setItem(KEY.USER_TYPE,  'agency');
  localStorage.setItem(KEY.JWT_TOKEN,  token);
  localStorage.setItem(KEY.USER_INFO,  JSON.stringify({
    user_type: 'agency', agency_code: agencyCode, login_id: loginId,
    name, role_id: roleId, role_name: roleName, group_code: groupCode, permissions,
  }));
  // 後方互換
  localStorage.setItem(KEY.AGENCY_TOKEN,    token);
  localStorage.setItem(KEY.AGENCY_CODE,     agencyCode);
  localStorage.setItem(KEY.AGENCY_LOGIN_ID, loginId);
  localStorage.setItem(KEY.AGENCY_NAME,     name);
}

/**
 * 社員ログイン成功時にlocalStorageへ保存する。
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
  localStorage.setItem(KEY.USER_TYPE,  'staff');
  localStorage.setItem(KEY.JWT_TOKEN,  token);
  localStorage.setItem(KEY.USER_INFO,  JSON.stringify({
    user_type: 'staff', staff_code: staffCode, name,
    role_id: roleId, role_name: roleName, buka_code: bukaCode,
    permissions, managed_agencies: managedAgencies,
  }));
  // 後方互換
  localStorage.setItem(KEY.STAFF_TOKEN,       token);
  localStorage.setItem(KEY.STAFF_CODE,        staffCode);
  localStorage.setItem(KEY.STAFF_NAME,        name);
  localStorage.setItem(KEY.STAFF_ROLE_ID,     String(roleId));
  localStorage.setItem(KEY.STAFF_ROLE_NAME,   roleName);
  localStorage.setItem(KEY.STAFF_BUKA_CODE,   bukaCode);
  localStorage.setItem(KEY.STAFF_PERMISSIONS, JSON.stringify(permissions));
}

/**
 * localStorageからuser_infoオブジェクトを取得する。
 * 未ログインの場合はnullを返す。
 * @returns {object|null}
 */
function getUserInfo() {
  const raw = localStorage.getItem(KEY.USER_INFO);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

/**
 * 現在のuser_typeに応じたJWTトークンを返す。
 * @returns {string|null}
 */
function getToken() {
  return localStorage.getItem(KEY.JWT_TOKEN) || null;
}

/**
 * ユーザー種別に応じたダッシュボードへ遷移する。
 * agency → dashboard.html
 * staff  → staff_dashboard.html
 * 不明   → login.html
 */
function goToDashboard() {
  const userType = localStorage.getItem(KEY.USER_TYPE);
  if (userType === 'staff') {
    window.location.href = 'staff_dashboard.html';
  } else if (userType === 'agency') {
    window.location.href = 'dashboard.html';
  } else {
    window.location.href = 'login.html';
  }
}

/**
 * ユーザー種別に応じたログイン画面URLを返す。
 * @returns {string}
 */
function getLoginUrl() {
  const userType = localStorage.getItem(KEY.USER_TYPE);
  return (userType === 'staff') ? 'staff_login.html' : 'login.html';
}

/**
 * ログアウト処理。
 * localStorageを全クリアし、user_typeに応じたログイン画面へリダイレクトする。
 */
async function doLogout() {
  const loginUrl = getLoginUrl();
  // 全キーをクリアする
  Object.values(KEY).forEach(k => localStorage.removeItem(k));
  window.location.href = loginUrl;
}

/**
 * 認証ガード：未ログインの場合は適切なログイン画面へリダイレクトする。
 * ページロード時に呼び出す。
 * @returns {string|null} - ログイン済みならJWTトークン、未ログインならnull（リダイレクト実行）
 */
function requireAuth() {
  const token    = getToken();
  const userType = localStorage.getItem(KEY.USER_TYPE);
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
  const userType = localStorage.getItem(KEY.USER_TYPE);
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
  const userType = localStorage.getItem(KEY.USER_TYPE);
  if (!token || userType !== 'staff') {
    window.location.href = 'staff_login.html';
    return null;
  }
  return token;
}
