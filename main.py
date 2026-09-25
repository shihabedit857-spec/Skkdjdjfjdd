# main.py — SB AURA Backend — FULL FINAL + SETTINGS
# Like + Bio + Friend + Guild + EAT + Info/Level + Token Cache + Stop Button + Site Settings

import os, json, time, binascii, base64, asyncio, urllib3, tempfile, signal, sys
import threading as _threading
from collections import deque
from functools import wraps
from urllib.parse import urlparse, parse_qs
from threading import RLock
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
from google.protobuf import json_format
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

try:
    from google.protobuf import runtime_version as _runtime_version
    _HAS_RUNTIME_VERSION = True
except ImportError:
    _HAS_RUNTIME_VERSION = False

import requests
import aiohttp
import jwt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import orjson
    def _jsonify(data, status=200):
        return Response(orjson.dumps(data, option=orjson.OPT_INDENT_2), status=status,
                        mimetype='application/json')
except ImportError:
    def _jsonify(data, status=200):
        return Response(json.dumps(data, indent=2, ensure_ascii=False),
                        status=status, mimetype='application/json')

try: import like_pb2
except ImportError: like_pb2 = None
try: import like_count_pb2
except ImportError: like_count_pb2 = None
try: import uid_generator_pb2
except ImportError: uid_generator_pb2 = None

try:
    import RemoveFriend_Req_pb2
    _HAS_REMOVE_FRIEND = True
except ImportError:
    RemoveFriend_Req_pb2 = None; _HAS_REMOVE_FRIEND = False

try:
    import ReqCLan_pb2
    _HAS_REQ_CLAN = True
except ImportError:
    ReqCLan_pb2 = None; _HAS_REQ_CLAN = False

try:
    import QuitClanReq_pb2
    _HAS_QUIT_CLAN = True
except ImportError:
    QuitClanReq_pb2 = None; _HAS_QUIT_CLAN = False

try:
    from AccountPersonalShow_pb2 import AccountPersonalShowInfo
    _HAS_PERSONAL_SHOW = True
except ImportError:
    AccountPersonalShowInfo = None; _HAS_PERSONAL_SHOW = False
    print("[WARN] AccountPersonalShow_pb2.py missing")

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════
#  BRANDING (DEFAULTS)
# ═══════════════════════════════════════════════════════════
OWNER_HANDLE = "TG: @shihab23"
DEV_NAME     = "SHIHAB"
TELEGRAM     = "@shihab23"
BRAND_NAME   = "SB AURA"
MASTER_ACCESS_KEY = "SB-AURA"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLIENT_VERSION = "1.132.1"
OB_VERSION     = "OB55"
LOGIN_URL      = "https://loginbp.ppmainecoonghj.com"
BIO_UPDATE_URL = "https://clientbp.ppmainecoonghj.com/UpdateSocialBasicInfo"

JWT_WORKERS = 60
LIKE_CONCUR = 300

SERVER_ACCOUNT_FILES = {
    "BD": "account_bd.json", "IND": "account_ind.json", "BR": "account_br.json",
    "US": "account_us.json", "SAC": "account_sac.json", "NA": "account_na.json",
}

BDT = timezone(timedelta(hours=6))
def now_bdt(): return datetime.now(BDT)
def now_bdt_str(): return now_bdt().strftime("%Y-%m-%d %H:%M:%S")
def now_bdt_full(): return now_bdt().strftime("%Y-%m-%d %H:%M:%S")

# ═══════════════════════════════════════════════════════════
#  GRACEFUL SHUTDOWN
# ═══════════════════════════════════════════════════════════
_shutdown_flag = _threading.Event()

def _graceful_shutdown(signum, frame):
    print("\n[SHUTDOWN] Closing...")
    _shutdown_flag.set()
    try:
        os._exit(0)
    except Exception:
        sys.exit(0)

try:
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)
except (ValueError, AttributeError):
    pass

# ═══════════════════════════════════════════════════════════
#  LIVE LOG
# ═══════════════════════════════════════════════════════════
LOG_BUFFER = deque(maxlen=500)
LOG_LOCK = RLock()
LOG_COUNTER = [0]

def _log(msg, level="info"):
    try:
        with LOG_LOCK:
            LOG_COUNTER[0] += 1
            LOG_BUFFER.append({"id": LOG_COUNTER[0],
                               "ts": now_bdt().strftime("%H:%M:%S"),
                               "level": level, "msg": str(msg)})
    except Exception: pass

# ═══════════════════════════════════════════════════════════
#  CONFIG PATH
# ═══════════════════════════════════════════════════════════
def _pick_writable_config_path():
    cand = [os.path.join(BASE_DIR, "keys.json"), os.path.join(BASE_DIR, "data", "keys.json")]
    try: cand.append(os.path.join(tempfile.gettempdir(), "ff_keys.json"))
    except Exception: pass
    cand.append("/tmp/ff_keys.json")
    for p in cand:
        try:
            d = os.path.dirname(p)
            if d and not os.path.exists(d): os.makedirs(d, exist_ok=True)
            with open(p, "a", encoding="utf-8"): pass
            return p
        except OSError: continue
    return os.path.join(BASE_DIR, "keys.json")

CONFIG_RO_PATH = os.path.join(BASE_DIR, "keys.json")
CONFIG_RW_PATH = _pick_writable_config_path()
config_lock = RLock()
print(f"[CONFIG] RW: {CONFIG_RW_PATH}")

def _active_config_path_for_read():
    for p in (CONFIG_RW_PATH, CONFIG_RO_PATH):
        if p and os.path.exists(p): return p
    return CONFIG_RO_PATH

def _read_config():
    path = _active_config_path_for_read()
    if not path or not os.path.exists(path):
        cfg = {"ALLOWED_KEYS": {}, "ADMIN_KEYS": ["NIROBxLIKE"], "RESET_TZ": "Asia/Dhaka"}
        _write_config(cfg); return cfg
    try:
        with open(path, "r", encoding="utf-8") as f: cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        cfg = {"ALLOWED_KEYS": {}, "ADMIN_KEYS": ["NIROBxLIKE"], "RESET_TZ": "Asia/Dhaka"}
    cfg.setdefault("ALLOWED_KEYS", {}); cfg.setdefault("ADMIN_KEYS", [])
    cfg.setdefault("RESET_TZ", "Asia/Dhaka"); return cfg

def _write_config(cfg):
    with config_lock:
        for path in (CONFIG_RW_PATH, CONFIG_RO_PATH):
            if not path: continue
            try:
                d = os.path.dirname(path)
                if d and not os.path.exists(d): os.makedirs(d, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                return True
            except OSError as e: print(f"[CONFIG] Write failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  SITE SETTINGS
# ═══════════════════════════════════════════════════════════
SETTINGS_RW_PATH = os.path.join(os.path.dirname(CONFIG_RW_PATH), "settings.json")
SETTINGS_RO_PATH = os.path.join(BASE_DIR, "settings.json")
settings_lock = RLock()

DEFAULT_SETTINGS = {
    "site_name":       BRAND_NAME,
    "title":           f"{BRAND_NAME} — Control Panel",
    "logo_url":        "https://i.ibb.co/VYdbCNm4/20260323-082630.webp",
    "favicon_url":     "https://i.ibb.co/VYdbCNm4/20260323-082630.webp",
    "primary_color":   "#ef4444",
    "secondary_color": "#f97316",
    "accent_color":    "#fbbf24",
    "owner_handle":    OWNER_HANDLE,
    "telegram":        TELEGRAM,
    "dev_name":        DEV_NAME,
    "admin_key":       MASTER_ACCESS_KEY,
}

def _active_settings_path_for_read():
    for p in (SETTINGS_RW_PATH, SETTINGS_RO_PATH):
        if p and os.path.exists(p):
            return p
    return SETTINGS_RO_PATH

def _read_settings():
    path = _active_settings_path_for_read()
    if not path or not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        if isinstance(data, dict):
            merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)

def _write_settings(data):
    with settings_lock:
        for path in (SETTINGS_RW_PATH, SETTINGS_RO_PATH):
            if not path: continue
            try:
                d = os.path.dirname(path)
                if d and not os.path.exists(d):
                    os.makedirs(d, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return True
            except OSError as e:
                print(f"[SETTINGS] Write failed: {e}")
        return False

def _get_admin_key():
    try:
        return str(_read_settings().get("admin_key") or MASTER_ACCESS_KEY).strip()
    except Exception:
        return MASTER_ACCESS_KEY

def _auth_matches_admin(auth: str) -> bool:
    """Case-insensitive admin key check (SB-AURA == sb-aura)."""
    a = (auth or "").strip()
    if not a:
        return False
    return a.casefold() == _get_admin_key().casefold()

def _get_branding():
    s = _read_settings()
    return {
        "site_name": s.get("site_name", BRAND_NAME),
        "dev": s.get("dev_name", DEV_NAME),
        "tg": s.get("telegram", TELEGRAM),
        "owner": s.get("owner_handle", OWNER_HANDLE),
        "badge": "Premium",
    }

def _require_master(f):
    @wraps(f)
    def wrapper(*a, **k):
        auth = (request.args.get("auth") or "").strip()
        if not auth:
            try:
                body = request.get_json(silent=True) or {}
                auth = str(body.get("auth", "")).strip()
            except Exception: pass
        if not _auth_matches_admin(auth):
            return _jsonify({"status": 0, "success": False,
                             "error": "Unauthorized — admin only 🔒"}), 403
        return f(*a, **k)
    return wrapper

def _pick_writable_account_dir():
    cand = [os.path.join(BASE_DIR, "data", "accounts"), os.path.join(BASE_DIR, "accounts"),
            os.path.join(tempfile.gettempdir(), "ff_accounts"), "/tmp/ff_accounts"]
    for p in cand:
        try:
            os.makedirs(p, exist_ok=True)
            with open(os.path.join(p, ".t"), "w") as f: f.write("x")
            os.remove(os.path.join(p, ".t")); return p
        except OSError: continue
    return BASE_DIR

ACCOUNT_RW_DIR = _pick_writable_account_dir()

# ═══════════════════════════════════════════════════════════
#  KEY HELPERS
# ═══════════════════════════════════════════════════════════
def _normalize_key_entry(entry, limit=9999, days=30, customer=""):
    if isinstance(entry, dict): return entry
    now = now_bdt(); exp = (now + timedelta(days=days)).isoformat() if days > 0 else None
    return {"limit": int(entry) if isinstance(entry, (int, float, str)) else limit,
            "days": days, "customer": customer, "created_at": now.isoformat(),
            "expires_at": exp, "used": 0}

def is_valid_key(api_key):
    if _auth_matches_admin(api_key): return True
    try:
        cfg = _read_config()
        if api_key in cfg.get("ADMIN_KEYS", []): return True
        allowed = cfg.get("ALLOWED_KEYS", {})
        if api_key not in allowed: return False
        entry = _normalize_key_entry(allowed[api_key])
        exp = entry.get("expires_at")
        if exp:
            try:
                ed = datetime.fromisoformat(exp)
                if ed.tzinfo is None: ed = ed.replace(tzinfo=BDT)
                if now_bdt() > ed: return False
            except Exception: pass
        limit = int(entry.get("limit", 9999)); used = int(entry.get("used", 0))
        if limit > 0 and used >= limit: return False
        return True
    except Exception: return False

def increment_key_usage(api_key):
    if _auth_matches_admin(api_key): return
    try:
        cfg = _read_config()
        if api_key in cfg.get("ADMIN_KEYS", []): return
        with config_lock:
            cfg = _read_config(); allowed = cfg.get("ALLOWED_KEYS", {})
            if api_key in allowed:
                entry = _normalize_key_entry(allowed[api_key])
                entry["used"] = int(entry.get("used", 0)) + 1
                allowed[api_key] = entry; _write_config(cfg)
    except Exception: pass

def _key_response_fields(key):
    if _auth_matches_admin(key):
        return {"KeyExpiresAt": "unlimited", "KeyRemainingRequests": "∞/∞"}
    try:
        cfg = _read_config()
        if key in cfg.get("ADMIN_KEYS", []):
            return {"KeyExpiresAt": "unlimited", "KeyRemainingRequests": "∞/∞"}
        allowed = cfg.get("ALLOWED_KEYS", {})
        info = _normalize_key_entry(allowed[key]) if key in allowed else None
    except Exception: info = None
    if not info: return {"KeyExpiresAt": "N/A", "KeyRemainingRequests": "0/0"}
    try:
        ea = datetime.fromisoformat(info['expires_at']).isoformat() if info.get('expires_at') else "N/A"
    except Exception: ea = "N/A"
    limit = int(info.get("limit", 9999)); used = int(info.get("used", 0))
    rem = "∞/∞" if limit == 0 else f"{max(0, limit - used)}/{limit}"
    return {"KeyExpiresAt": ea, "KeyRemainingRequests": rem}

# ═══════════════════════════════════════════════════════════
#  INLINE FreeFire_pb2
# ═══════════════════════════════════════════════════════════
if _HAS_RUNTIME_VERSION:
    try:
        _runtime_version.ValidateProtobufRuntimeVersion(
            _runtime_version.Domain.PUBLIC, 6, 30, 0, "", "FreeFire.proto")
    except Exception: pass

_sym_db_ff = _symbol_database.Default()
_FF_DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x0e\x46reeFire.proto"c\n\x08LoginReq\x12\x0f\n\x07open_id\x18\x16 \x01(\t'
    b'\x12\x14\n\x0copen_id_type\x18\x17 \x01(\t\x12\x13\n\x0blogin_token\x18\x1d '
    b'\x01(\t\x12\x1b\n\x13orign_platform_type\x18\x63 \x01(\t"]\n\x10\x42lacklist'
    b'InfoRes\x12\x1e\n\nban_reason\x18\x01 \x01(\x0e\x32\n.BanReason\x12\x17\n'
    b'\x0f\x65xpire_duration\x18\x02 \x01(\r\x12\x10\n\x08\x62\x61n_time\x18\x03 '
    b'\x01(\r"f\n\x0eLoginQueueInfo\x12\r\n\x05\x61llow\x18\x01 \x01(\x08\x12'
    b'\x16\n\x0equeue_position\x18\x02 \x01(\r\x12\x16\n\x0eneed_wait_secs\x18'
    b'\x03 \x01(\r\x12\x15\n\rqueue_is_full\x18\x04 \x01(\x08"\xa0\x03\n\x08'
    b'LoginRes\x12\x12\n\naccount_id\x18\x01 \x01(\x04\x12\x13\n\x0block_region'
    b'\x18\x02 \x01(\t\x12\x13\n\x0bnoti_region\x18\x03 \x01(\t\x12\x11\n\tip_'
    b'region\x18\x04 \x01(\t\x12\x19\n\x11\x61gora_environment\x18\x05 \x01(\t'
    b'\x12\x19\n\x11new_active_region\x18\x06 \x01(\t\x12\x19\n\x11recommend_'
    b'regions\x18\x07 \x03(\t\x12\r\n\x05token\x18\x08 \x01(\t\x12\x0b\n\x03ttl'
    b'\x18\t \x01(\r\x12\x12\n\nserver_url\x18\n \x01(\t\x12\x16\n\x0e\x65mul'
    b'ator_score\x18\x0b \x01(\r\x12$\n\tblacklist\x18\x0c \x01(\x0b\x32\x11.'
    b'BlacklistInfoRes\x12#\n\nqueue_info\x18\r \x01(\x0b\x32\x0f.LoginQueue'
    b'Info\x12\x0e\n\x06tp_url\x18\x0e \x01(\t\x12\x15\n\rapp_server_id\x18'
    b'\x0f \x01(\r\x12\x0f\n\x07\x61no_url\x18\x10 \x01(\t\x12\x0f\n\x07ip_city'
    b'\x18\x11 \x01(\t\x12\x16\n\x0eip_subdivision\x18\x12 \x01(\t*\xa8\x01\n'
    b'\tBanReason\x12\x16\n\x12\x42\x41N_REASON_UNKNOWN\x10\x00\x12\x1b\n\x17'
    b'\x42\x41N_REASON_IN_GAME_AUTO\x10\x01\x12\x15\n\x11\x42\x41N_REASON_'
    b'REFUND\x10\x02\x12\x15\n\x11\x42\x41N_REASON_OTHERS\x10\x03\x12\x16\n'
    b'\x12\x42\x41N_REASON_SKINMOD\x10\x04\x12 \n\x1b\x42\x41N_REASON_IN_GAME'
    b'_AUTO_NEW\x10\xf6\x07\x62\x06proto3'
)
_ff_globals = globals()
_builder.BuildMessageAndEnumDescriptors(_FF_DESCRIPTOR, _ff_globals)
_builder.BuildTopDescriptorsAndMessages(_FF_DESCRIPTOR, "FreeFire_pb2", _ff_globals)
if not _descriptor._USE_C_DESCRIPTORS:
    _FF_DESCRIPTOR._loaded_options = None
    _ff_globals["_LOGINREQ"]._serialized_start = 18
    _ff_globals["_LOGINREQ"]._serialized_end = 117
    _ff_globals["_LOGINRES"]._serialized_start = 319
    _ff_globals["_LOGINRES"]._serialized_end = 735
LoginReq = _ff_globals["LoginReq"]
LoginRes = _ff_globals["LoginRes"]

# ═══════════════════════════════════════════════════════════
#  JWT SETTINGS
# ═══════════════════════════════════════════════════════════
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'
RELEASEVERSION = "OB55"
FF_USERAGENT = "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"

_http_adapter = requests.adapters.HTTPAdapter(
    pool_connections=20, pool_maxsize=50, max_retries=0, pool_block=False)
_http_client = requests.Session()
_http_client.mount('https://', _http_adapter)
_http_client.mount('http://', _http_adapter)

PLATFORM_MAP = {3:"Facebook",4:"Guest",5:"VK",6:"Huawei",8:"Google",11:"X",13:"AppleId"}

INFO_FALLBACK_ACCOUNTS = {
    'IND': {'uid': '4218389302', 'password': 'NILAY-9LRRJQ7P3-NR-CODEX'},
    'BD':  {'uid': '6549243316', 'password': 'Shihabkaksk_B44XB_xSaeed_EG9U1'},
    'BR':  {'uid': '4218400521', 'password': 'BY_XRSUPER-JZRQ3RURQ-XRRRR'},
    'US':  {'uid': '4218400521', 'password': 'BY_XRSUPER-JZRQ3RURQ-XRRRR'},
    'ME':  {'uid': '4218400521', 'password': 'BY_XRSUPER-JZRQ3RURQ-XRRRR'},
    'SG':  {'uid': '4218400521', 'password': 'BY_XRSUPER-JZRQ3RURQ-XRRRR'},
}
info_token_cache = {}
INFO_TOKEN_DURATION = 21600

# ═══════════════════════════════════════════════════════════
#  ACCOUNT LOADER
# ═══════════════════════════════════════════════════════════
def _account_rw_path(srv):
    f = SERVER_ACCOUNT_FILES.get(srv.upper())
    return os.path.join(ACCOUNT_RW_DIR, f) if f else ""
def _account_ro_path(srv):
    f = SERVER_ACCOUNT_FILES.get(srv.upper())
    return os.path.join(BASE_DIR, f) if f else ""
def _account_file_path(srv):
    rw = _account_rw_path(srv); ro = _account_ro_path(srv)
    return rw if rw and os.path.exists(rw) else ro

def _parse_account_text(text):
    text = (text or "").strip()
    if not text: return []
    try:
        data = json.loads(text); out = []
        if isinstance(data, dict):
            for uid, pw in data.items():
                uid, pw = str(uid).strip(), str(pw).strip()
                if uid and pw: out.append((uid, pw))
            return out
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    uid = str(item.get("uid", "")).strip()
                    pw  = str(item.get("password", item.get("pass", ""))).strip()
                    if uid and pw: out.append((uid, pw))
                else:
                    s = str(item).strip()
                    if ":" in s:
                        u, p = s.split(":", 1); out.append((u.strip(), p.strip()))
            return out
    except (json.JSONDecodeError, ValueError): pass
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ":" not in ln: continue
        uid, pw = ln.split(":", 1)
        if uid.strip() and pw.strip(): out.append((uid.strip(), pw.strip()))
    return out

def _load_accounts_for_server(srv):
    path = _account_file_path(srv)
    if not path or not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _parse_account_text(f.read())
    except OSError: return []

def _save_accounts_for_server(srv, accounts):
    rw = _account_rw_path(srv)
    if not rw: return False
    try:
        os.makedirs(os.path.dirname(rw), exist_ok=True)
        with open(rw, "w", encoding="utf-8") as f:
            json.dump({str(u): str(p) for u, p in accounts}, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"[ACCOUNTS] Save failed: {e}"); return False

# ═══════════════════════════════════════════════════════════
#  JWT CORE
# ═══════════════════════════════════════════════════════════
def _decode_ff_name(b64_str):
    try:
        if not b64_str: return ""
        key = b"1e5898ccb8dfdd921f9bdea848768b64a201"
        b64_str = b64_str.strip(); b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
        enc = base64.b64decode(b64_str); dec = bytearray()
        for i, b in enumerate(enc): dec.append(b ^ key[i % len(key)])
        return dec.decode('utf-8', errors='ignore')
    except Exception: return ""

def _aes_cbc_encrypt(key, iv, pt):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(pt, AES.block_size))

def _json_to_proto(js, msg):
    json_format.ParseDict(json.loads(js), msg); return msg.SerializeToString()

def _try_parse_login_res(data):
    try:
        msg = LoginRes(); msg.ParseFromString(data)
        if msg.account_id and msg.account_id > 9999999:
            return json.loads(json_format.MessageToJson(msg))
    except Exception: pass
    return None

def _extract_login_res(raw):
    p = _try_parse_login_res(raw)
    if p: return p
    idx = 0
    while True:
        idx = raw.find(b"\x08", idx)
        if idx == -1: break
        p = _try_parse_login_res(raw[idx:])
        if p: return p
        idx += 1
    m = raw.find(b"eyJhbGciOiJIUzI1NiIs")
    if m != -1:
        for i in range(m - 1, max(m - 300, -1), -1):
            if raw[i] == 0x42:
                p = _try_parse_login_res(raw[i:])
                if p: return p
                break
    raise Exception(f"Could not parse LoginRes. Raw: {raw[:120]}")

def _fetch_open_id(access_token):
    try:
        url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        headers = {"Accept": "application/json",
                   "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) Chrome/124.0.0.0 Mobile"}
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        return res.json().get("open_id"), None
    except Exception as e: return None, str(e)

def _internal_generate_jwt(access_token, open_id=None):
    if not open_id:
        open_id, error = _fetch_open_id(access_token)
        if error: return {"status": "error", "message": error}, 400
    platforms = [4, 8, 3, 6]; last_error = None
    for pt in platforms:
        try:
            body = json.dumps({"open_id": open_id, "open_id_type": str(pt),
                               "login_token": access_token, "orign_platform_type": str(pt)})
            proto_bytes = _json_to_proto(body, LoginReq())
            payload = _aes_cbc_encrypt(AES_KEY, AES_IV, proto_bytes)
            headers = {
                "User-Agent": FF_USERAGENT, "Accept": "*/*",
                "Accept-Encoding": "deflate, gzip", "X-Ga-Sv": "1789534056",
                "Authorization": "Bearer", "X-Ga": "v1 1",
                "Releaseversion": RELEASEVERSION,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Unity-Version": "2018.4.12f1",
                "PlAy_VeR": "1.132.1", "Ob_VeR": RELEASEVERSION,
            }
            resp = _http_client.post(f"{LOGIN_URL}/MajorLogin", data=payload,
                                     headers=headers, verify=False, timeout=15)
            msg = _extract_login_res(resp.content)
            tv = msg.get("token")
            if not tv: continue
            result = {
                "access_token": access_token,
                "account_id": None, "account_name": "",
                "open_id": open_id,
                "platform": PLATFORM_MAP.get(pt, f"Unknown ({pt})"),
                "region": msg.get("lockRegion"),
                "status": "success", "token": tv,
            }
            aid = msg.get("accountId")
            if aid: result["account_id"] = str(aid)
            try:
                decoded = jwt.decode(tv, options={"verify_signature": False})
                jid = decoded.get("account_id")
                if jid: result["account_id"] = str(jid)
                result["account_name"] = _decode_ff_name(decoded.get("nickname", ""))
                result["platform"] = PLATFORM_MAP.get(decoded.get("external_type"),
                                                      f"Unknown ({decoded.get('external_type')})")
                result["region"] = decoded.get("lock_region") or msg.get("lockRegion")
            except Exception: pass
            return result, 200
        except Exception as e:
            last_error = str(e); continue
    return {"status": "error", "message": f"No valid platform. Last: {last_error}"}, 400

def _guest_login_oauth(uid, pw, timeout=12):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    payload = {'uid': uid, 'password': pw, 'response_type': "token", 'client_type': "2",
               'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
               'client_id': "100067"}
    headers = {'User-Agent': "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt,BR;)",
               'Connection': "Keep-Alive", 'Accept-Encoding': "gzip"}
    try:
        r = requests.post(url, data=payload, headers=headers, timeout=timeout, verify=False)
        if r.status_code != 200: return None, None
        j = r.json(); return j.get('access_token'), j.get('open_id')
    except Exception: return None, None

def _fetch_single_jwt(uid, pw, timeout=12, max_attempts=3):
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            at, oid = _guest_login_oauth(uid, pw, timeout=timeout)
            if not at or not oid:
                last_err = "oauth_fail"
                if attempt < max_attempts: time.sleep(0.5 * attempt)
                continue
            result, code = _internal_generate_jwt(at, oid)
            if code == 200 and result.get("token"):
                return uid, result["token"]
            last_err = result.get("message", "jwt_fail")
        except Exception as e: last_err = str(e)[:80]
        if attempt < max_attempts: time.sleep(0.5 * attempt)
    _log(f"✗ {uid} failed — {last_err}", "err")
    return uid, None

# ═══════════════════════════════════════════════════════════
#  TOKEN CACHE + STOP FLAGS
# ═══════════════════════════════════════════════════════════
TOKEN_CACHE_FILES = {srv: os.path.join(BASE_DIR, f"token_{srv.lower()}.json")
                     for srv in SERVER_ACCOUNT_FILES.keys()}
TOKEN_CACHE = {}
TOKEN_CACHE_LOCK = RLock()
TOKEN_TTL = 6 * 3600

STOP_FLAGS = {srv: _threading.Event() for srv in SERVER_ACCOUNT_FILES.keys()}
print(f"[TOKEN-CACHE] TTL = {TOKEN_TTL // 3600}h")

def _load_token_cache_from_disk(srv):
    path = TOKEN_CACHE_FILES.get(srv)
    if not path or not os.path.exists(path): return None
    try:
        with open(path, "r", encoding="utf-8") as f: data = json.load(f)
        expiry = float(data.get("expiry", 0)); tokens = data.get("tokens", [])
        if expiry > time.time() and tokens:
            return {"tokens": tokens, "expiry": expiry, "building": False,
                    "generated_at": data.get("generated_at", ""), "stopped": False}
    except Exception as e: print(f"[TOKEN-CACHE] Load {srv} failed: {e}")
    return None

def _save_token_cache_to_disk(srv, tokens, expiry):
    path = TOKEN_CACHE_FILES.get(srv)
    if not path: return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tokens": tokens, "expiry": expiry,
                       "generated_at": now_bdt_str(), "count": len(tokens)},
                      f, ensure_ascii=False)
    except OSError as e: print(f"[TOKEN-CACHE] Save {srv} failed: {e}")

def _build_token_cache(srv):
    srv = srv.upper()
    _log(f"🔄 Building cache for {srv}...", "info")
    t0 = time.time()

    STOP_FLAGS[srv].clear()

    accounts = _load_accounts_for_server(srv)
    if not accounts:
        _log(f"❌ No accounts for {srv}", "err")
        with TOKEN_CACHE_LOCK:
            TOKEN_CACHE[srv] = {"tokens": [], "expiry": 0, "building": False,
                                "generated_at": "", "total_accounts": 0, "stopped": False}
        return []

    total = len(accounts)
    tokens = []
    failed_accounts = []
    stopped = False

    _log(f"▶ Token gen started: {total} accounts", "info")

    with ThreadPoolExecutor(max_workers=JWT_WORKERS) as pool:
        futures = {pool.submit(_fetch_single_jwt, uid, pw, 12, 3): (uid, pw)
                   for uid, pw in accounts}
        done = 0
        for fut in as_completed(futures):
            if STOP_FLAGS[srv].is_set():
                stopped = True
                _log(f"⛔ Stop requested — cancelling", "warn")
                for f in futures:
                    f.cancel()
                break
            uid, tok = fut.result()
            done += 1
            if tok: tokens.append(tok)
            else: failed_accounts.append(futures[fut])
            if done % 50 == 0 or done == total:
                _log(f"⏳ {done}/{total} — ✅ {len(tokens)}, ❌ {len(failed_accounts)}", "info")

    _log(f"{'✅ First pass' if not stopped else '⛔ Stopped at'}: {len(tokens)}/{total}",
         "ok" if not stopped else "warn")

    if failed_accounts and not stopped and not STOP_FLAGS[srv].is_set():
        _log(f"↻ Retrying {len(failed_accounts)} failed...", "warn")
        second_batch = []
        rw = max(1, min(JWT_WORKERS // 2, 30))
        with ThreadPoolExecutor(max_workers=rw) as pool:
            futures = {pool.submit(_fetch_single_jwt, uid, pw, 15, 5): (uid, pw)
                       for uid, pw in failed_accounts}
            for fut in as_completed(futures):
                if STOP_FLAGS[srv].is_set():
                    stopped = True
                    for f in futures:
                        f.cancel()
                    break
                uid, tok = fut.result()
                if tok: tokens.append(tok)
                else: second_batch.append(futures[fut])
        recovered = len(failed_accounts) - len(second_batch)
        _log(f"✅ 2nd: +{recovered} recovered, {len(second_batch)} failed", "ok")

    elapsed = round(time.time() - t0, 1)
    expiry = time.time() + TOKEN_TTL

    with TOKEN_CACHE_LOCK:
        TOKEN_CACHE[srv] = {
            "tokens": tokens, "expiry": expiry, "building": False,
            "generated_at": now_bdt_str(), "total_accounts": total,
            "stopped": stopped,
        }

    if tokens:
        _save_token_cache_to_disk(srv, tokens, expiry)

    if stopped:
        _log(f"⛔ Stopped at {len(tokens)}/{total} in {elapsed}s", "warn")
    else:
        _log(f"🎯 Done: {len(tokens)}/{total} in {elapsed}s", "ok")

    return tokens

def get_cached_tokens(srv, force_refresh=False):
    srv = srv.upper()
    if force_refresh: return _build_token_cache(srv)
    with TOKEN_CACHE_LOCK:
        entry = TOKEN_CACHE.get(srv)
        if entry and not entry.get("building") and entry.get("expiry", 0) > time.time() and entry.get("tokens"):
            return entry["tokens"]
    if not entry:
        disk = _load_token_cache_from_disk(srv)
        if disk:
            with TOKEN_CACHE_LOCK: TOKEN_CACHE[srv] = disk
            _log(f"💾 Loaded {srv} from disk: {len(disk['tokens'])}", "info")
            return disk["tokens"]
    with TOKEN_CACHE_LOCK:
        entry = TOKEN_CACHE.get(srv)
        if entry and entry.get("building"):
            ws = time.time()
            while entry.get("building") and time.time() - ws < 300:
                time.sleep(0.5); entry = TOKEN_CACHE.get(srv)
                if entry and not entry.get("building"): return entry.get("tokens", [])
            return TOKEN_CACHE.get(srv, {}).get("tokens", [])
        TOKEN_CACHE[srv] = {"tokens": [], "expiry": 0, "building": True,
                            "generated_at": "", "total_accounts": 0, "stopped": False}
    try: return _build_token_cache(srv)
    except Exception as e:
        with TOKEN_CACHE_LOCK:
            TOKEN_CACHE[srv] = {"tokens": [], "expiry": 0, "building": False,
                                "generated_at": "", "total_accounts": 0, "stopped": False}
        _log(f"❌ Cache build error {srv}: {e}", "err"); return []

def refresh_token_cache_background(srv):
    srv = srv.upper()
    def _w():
        try: _build_token_cache(srv)
        except Exception as e:
            _log(f"❌ BG refresh {srv}: {e}", "err")
            with TOKEN_CACHE_LOCK:
                if srv in TOKEN_CACHE:
                    TOKEN_CACHE[srv]["building"] = False
    _threading.Thread(target=_w, daemon=True, name=f"cache-{srv}").start()

def _token_cache_scheduler():
    _log("⏰ Scheduler started (5h50m)", "info")
    while not _shutdown_flag.is_set():
        try:
            for _ in range(5 * 360 + 50 * 6):
                if _shutdown_flag.is_set(): return
                time.sleep(10)
            if _shutdown_flag.is_set(): return
            for srv in list(SERVER_ACCOUNT_FILES.keys()):
                if _shutdown_flag.is_set(): return
                try:
                    if _load_accounts_for_server(srv):
                        refresh_token_cache_background(srv)
                except Exception as e: _log(f"⏰ Sched err {srv}: {e}", "err")
        except Exception as e: _log(f"⏰ Sched err: {e}", "err")

_scheduler_thread = _threading.Thread(target=_token_cache_scheduler, daemon=True, name="token-sched")
_scheduler_thread.start()

def preload_token_cache():
    _log("🔃 Preloading caches...", "info")
    for srv in SERVER_ACCOUNT_FILES.keys():
        try:
            if _load_accounts_for_server(srv):
                disk = _load_token_cache_from_disk(srv)
                if disk:
                    with TOKEN_CACHE_LOCK: TOKEN_CACHE[srv] = disk
                    _log(f"💾 {srv}: {len(disk['tokens'])} from disk", "ok")
                else: refresh_token_cache_background(srv)
        except Exception as e: _log(f"❌ Preload err {srv}: {e}", "err")

# ═══════════════════════════════════════════════════════════
#  LIKE HELPERS
# ═══════════════════════════════════════════════════════════
def _enc_like(pt):
    c = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return binascii.hexlify(c.encrypt(pad(pt, AES.block_size))).decode("utf-8")

def _create_like_msg(uid, region):
    if like_pb2 is None: return b""
    m = like_pb2.like(); m.uid = int(uid); m.region = region
    return m.SerializeToString()

def _enc_uid(uid):
    if uid_generator_pb2 is None: return ""
    m = uid_generator_pb2.uid_generator(); m.krishna_ = int(uid); m.teamXdarks = 1
    return _enc_like(m.SerializeToString())

def _like_url_for(srv):
    s = srv.upper()
    if s == "IND": return "https://client.ind.freefiremobile.com/LikeProfile"
    if s in {"BR","US","SAC","NA"}: return "https://client.us.freefiremobile.com/LikeProfile"
    return "https://clientbp.ppmainecoonghj.com/LikeProfile"

def _show_url_for(srv):
    s = srv.upper()
    if s == "IND": return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    if s in {"BR","US","SAC","NA"}: return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    return "https://clientbp.ppmainecoonghj.com/GetPlayerPersonalShow"

def _show_request(encrypted, srv, token):
    url = _show_url_for(srv)
    edata = bytes.fromhex(encrypted)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive", 'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'Expect': "100-continue", 'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1", 'ReleaseVersion': RELEASEVERSION,
    }
    try:
        r = requests.post(url, data=edata, headers=headers, verify=False, timeout=30)
        binary = bytes.fromhex(r.content.hex())
        obj = like_count_pb2.Info(); obj.ParseFromString(binary); return obj
    except Exception: return None

def _parse_show_info(pb_obj):
    try:
        if pb_obj is None: return None
        js = json.loads(MessageToJson(pb_obj))
        ai = js.get("AccountInfo", {})
        uid = int(ai.get("UID", 0)); likes = int(ai.get("Likes", 0))
        name = str(ai.get("PlayerNickname", ""))
        if uid <= 0: return None
        return {"uid": uid, "likes": likes, "name": name}
    except Exception: return None

async def _send_one_like(enc_uid, token, url, session_, sem):
    async with sem:
        edata = bytes.fromhex(enc_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive", 'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue", 'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1", 'ReleaseVersion': RELEASEVERSION,
        }
        for _ in range(2):
            try:
                async with session_.post(url, data=edata, headers=headers) as resp:
                    if resp.status == 200: return 1
                    if resp.status in (401, 403): return 0
                    await asyncio.sleep(0.3)
            except Exception: await asyncio.sleep(0.3)
        return 0

async def _burst_all(uid, srv, url, tokens, concurrency=LIKE_CONCUR):
    msg = _create_like_msg(uid, srv); enc_uid = _enc_like(msg)
    if not tokens: return []
    conn = aiohttp.TCPConnector(limit=concurrency, ssl=False)
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=conn) as sess:
        tasks = [_send_one_like(enc_uid, t, url, sess, sem) for t in tokens if t and len(t) > 10]
        return await asyncio.gather(*tasks, return_exceptions=True)

def send_likes_from_all_tokens(uid, srv, url, tokens):
    if not tokens: return {"success": 0, "failed": 0, "total": 0}
    results = asyncio.run(_burst_all(uid, srv, url, tokens, concurrency=LIKE_CONCUR))
    success = sum(1 for r in results if r == 1)
    return {"success": success, "failed": len(results) - success, "total": len(results)}

# ═══════════════════════════════════════════════════════════
#  BIO HELPERS
# ═══════════════════════════════════════════════════════════
BIO_HEADERS = {
    "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1",
    "ReleaseVersion": RELEASEVERSION, "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
    "Connection": "Keep-Alive", "Accept-Encoding": "gzip",
}

def _encode_varint(value):
    out = []
    while True:
        b = value & 0x7F; value >>= 7
        if value: out.append(b | 0x80)
        else: out.append(b); break
    return bytes(out)

def _build_payload_from_dict(fields_dict):
    payload = b''
    for key, value in sorted(fields_dict.items()):
        fn = int(key)
        if isinstance(value, bool):
            payload += _encode_varint((fn << 3) | 0) + _encode_varint(1 if value else 0)
        elif isinstance(value, int):
            payload += _encode_varint((fn << 3) | 0) + _encode_varint(value)
        elif isinstance(value, str):
            data = value.encode('utf-8')
            payload += _encode_varint((fn << 3) | 2) + _encode_varint(len(data)) + data
        elif isinstance(value, bytes):
            payload += _encode_varint((fn << 3) | 2) + _encode_varint(len(value)) + value
        elif isinstance(value, dict):
            sub = _build_payload_from_dict(value)
            payload += _encode_varint((fn << 3) | 2) + _encode_varint(len(sub)) + sub
        else: raise TypeError(f"Unsupported type {fn}")
    return payload

def _upload_bio(jwt_token, bio_text):
    try:
        fields = {2: 17, 5: {}, 6: {}, 8: bio_text, 9: 1, 11: {}, 12: {}}
        data_bytes = _build_payload_from_dict(fields)
        encrypted = _aes_cbc_encrypt(AES_KEY, AES_IV, data_bytes)
        headers = BIO_HEADERS.copy(); headers["Authorization"] = f"Bearer {jwt_token}"
        r = requests.post(BIO_UPDATE_URL, headers=headers, data=encrypted, timeout=20, verify=False)
        status_text = "success" if r.status_code == 200 else "failed"
        raw_hex = binascii.hexlify(r.content).decode('utf-8')
        return {"status": status_text, "code": r.status_code, "server_response": raw_hex}
    except Exception as e:
        return {"status": "failed", "code": 500, "server_response": str(e)}

def _decode_jwt_info(token):
    try:
        d = jwt.decode(token, options={"verify_signature": False})
        return (d.get("account_id"), _decode_ff_name(d.get("nickname", "")),
                d.get("lock_region"), d.get("external_type"))
    except Exception: return None, None, None, None

# ═══════════════════════════════════════════════════════════
#  FRIEND / GUILD HELPERS
# ═══════════════════════════════════════════════════════════
def _client_host(region):
    r = (region or "BD").upper()
    if r == "IND": return "client.ind.freefiremobile.com"
    if r in {"BR","US","SAC","NA"}: return "client.us.freefiremobile.com"
    return "clientbp.ppmainecoonghj.com"

def _client_headers(jwt_token):
    return {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1", "ReleaseVersion": RELEASEVERSION,
    }

def _get_target_player_info(target_uid, jwt_token, region):
    try:
        encrypted_uid = _enc_uid(target_uid)
        show_obj = _show_request(encrypted_uid, region, jwt_token)
        info = _parse_show_info(show_obj)
        if info:
            return {"nickname": info["name"], "uid": str(info["uid"]),
                    "likes": info["likes"], "level": 0,
                    "region": region, "release_version": RELEASEVERSION}
    except Exception: pass
    return {"nickname": "Unknown", "uid": str(target_uid), "likes": 0,
            "level": 0, "region": region, "release_version": RELEASEVERSION}

def _get_login_jwt_info(uid=None, password=None, access_token=None, jwt_token=None):
    if jwt_token:
        j_uid, j_name, j_region, _ = _decode_jwt_info(jwt_token)
        return jwt_token, "Direct JWT", j_uid, j_name, j_region, None, None, None

    if access_token:
        oid, err = _fetch_open_id(access_token)
        if err or not oid:
            return None, None, None, None, None, None, None, f"Invalid access token: {err or 'no open_id'}"
        result, code = _internal_generate_jwt(access_token, oid)
        if code == 200 and result.get("token"):
            return (result["token"], "Access Token Login",
                    result.get("account_id"), result.get("account_name"),
                    result.get("region"), oid, access_token, None)
        return None, None, None, None, None, None, None, result.get("message", "JWT failed")

    if uid and password:
        at, oid = _guest_login_oauth(uid, password)
        if not at or not oid:
            return None, None, None, None, None, None, None, "Guest login failed"
        result, code = _internal_generate_jwt(at, oid)
        if code == 200 and result.get("token"):
            return (result["token"], "UID/Pass Login",
                    result.get("account_id"), result.get("account_name"),
                    result.get("region"), oid, at, None)
        return None, None, None, None, None, None, None, result.get("message", "JWT failed")

    return None, None, None, None, None, None, None, "No login credentials provided"

# ═══════════════════════════════════════════════════════════
#  FRIEND ADD / REMOVE / LIST
# ═══════════════════════════════════════════════════════════
def _friend_add(jwt_token, target_uid, region, author_uid):
    base = {"action": "add_friend", "status": "failed", "code": 500,
            "author_uid": str(author_uid) if author_uid else None,
            "uid": str(target_uid), "nickname": "Unknown", "name": "Unknown",
            "level": 0, "likes": 0, "region": region,
            "release_version": RELEASEVERSION,
            "login_method": "N/A", "open_id": None, "access_token": None,
            "server_response": "N/A", "time": now_bdt_full()}
    try:
        from byte import Encrypt_ID, encrypt_api
    except ImportError:
        base["message"] = "byte.py missing"; return base
    try:
        player = _get_target_player_info(target_uid, jwt_token, region)
        enc_id = Encrypt_ID(target_uid)
        payload = f"08a7c4839f1e10{enc_id}1801"
        enc_payload = encrypt_api(payload)
        url = f"https://{_client_host(region)}/RequestAddingFriend"
        r = requests.post(url, headers=_client_headers(jwt_token),
                          data=bytes.fromhex(enc_payload), verify=False, timeout=15)
        return {"action": "add_friend",
                "status": "success" if r.status_code == 200 else "failed",
                "code": r.status_code,
                "author_uid": str(author_uid) if author_uid else None,
                "uid": str(target_uid),
                "nickname": player.get("nickname", "Unknown"),
                "name": player.get("nickname", "Unknown"),
                "level": player.get("level", 0),
                "likes": player.get("likes", 0),
                "region": player.get("region", region),
                "release_version": player.get("release_version", RELEASEVERSION),
                "server_response": r.text[:500] if r.text else "N/A",
                "time": now_bdt_full()}
    except Exception as e:
        base["message"] = str(e); return base

def _friend_remove(jwt_token, author_uid, target_uid, region):
    base = {"action": "remove_friend", "status": "failed", "code": 500,
            "author_uid": str(author_uid) if author_uid else None,
            "uid": str(target_uid), "nickname": "Unknown", "name": "Unknown",
            "level": 0, "likes": 0, "region": region,
            "release_version": RELEASEVERSION,
            "login_method": "N/A", "open_id": None, "access_token": None,
            "server_response": "N/A", "time": now_bdt_full()}
    if not _HAS_REMOVE_FRIEND:
        base["message"] = "RemoveFriend_Req_pb2.py missing"; return base
    try:
        player = _get_target_player_info(target_uid, jwt_token, region)
        msg = RemoveFriend_Req_pb2.RemoveFriend()
        msg.AuthorUid = int(author_uid); msg.TargetUid = int(target_uid)
        encrypted = _aes_cbc_encrypt(AES_KEY, AES_IV, msg.SerializeToString())
        url = f"https://{_client_host(region)}/RemoveFriend"
        r = requests.post(url, headers=_client_headers(jwt_token),
                          data=encrypted, verify=False, timeout=15)
        return {"action": "remove_friend",
                "status": "success" if r.status_code == 200 else "failed",
                "code": r.status_code,
                "author_uid": str(author_uid),
                "uid": str(target_uid),
                "nickname": player.get("nickname", "Unknown"),
                "name": player.get("nickname", "Unknown"),
                "level": player.get("level", 0),
                "likes": player.get("likes", 0),
                "region": player.get("region", region),
                "release_version": player.get("release_version", RELEASEVERSION),
                "server_response": r.text[:500] if r.text else "N/A",
                "time": now_bdt_full()}
    except Exception as e:
        base["message"] = str(e); return base

def _friend_list(jwt_token, region):
    base = {"action": "friend_list", "success": False, "code": 500,
            "total_size_bytes": 0, "friends_count": 0, "friends_list": [],
            "region": region, "login_method": "N/A",
            "open_id": None, "access_token": None,
            "server_response": "N/A", "time": now_bdt_full()}
    try:
        url = f"https://{_client_host(region)}/GetFriend"
        headers = _client_headers(jwt_token)
        payload = bytes.fromhex('362b36f221ac9ed98b104f7b53c858dc')
        r = requests.post(url, headers=headers, data=payload, verify=False, timeout=15)
        raw = r.content

        def parse_pb(data):
            out = {}; pos = 0
            def rv():
                nonlocal pos
                v = 0; sh = 0
                while pos < len(data):
                    b = data[pos]; pos += 1
                    v |= (b & 0x7F) << sh
                    if not (b & 0x80): break
                    sh += 7
                return v
            while pos < len(data):
                try:
                    fb = data[pos]; pos += 1
                    fn = fb >> 3; wt = fb & 7
                    if wt == 0: out.setdefault(fn, []).append(rv())
                    elif wt == 2:
                        ln = rv(); chunk = data[pos:pos+ln]; pos += ln
                        try: out.setdefault(fn, []).append(chunk.decode('utf-8'))
                        except Exception: out.setdefault(fn, []).append(parse_pb(chunk))
                except Exception: break
            for k, v in list(out.items()):
                if isinstance(v, list) and len(v) == 1: out[k] = v[0]
            return out

        parsed = parse_pb(raw); friends = []
        if 1 in parsed and isinstance(parsed[1], list):
            for f in parsed[1]:
                if isinstance(f, dict):
                    friends.append({"user_id": f.get(1, "unknown"),
                                    "nickname": f.get(3, "unknown")})
        return {"action": "friend_list", "success": True, "code": r.status_code,
                "total_size_bytes": len(raw), "friends_count": len(friends),
                "friends_list": friends, "region": region,
                "server_response": f"raw_bytes={len(raw)}",
                "time": now_bdt_full()}
    except Exception as e:
        base["error"] = str(e); return base

def _guild_join(jwt_token, clan_id, region, uid, name):
    base = {"action": "Join Clan", "success": False, "code": 500,
            "clan_id": str(clan_id), "uid": str(uid) if uid else None,
            "name": name, "region": region, "login_method": "N/A",
            "open_id": None, "access_token": None, "server_response": "N/A",
            "time": now_bdt_full()}
    if not _HAS_REQ_CLAN:
        base["error"] = "ReqCLan_pb2.py missing"; return base
    try:
        msg = ReqCLan_pb2.MyMessage(); msg.field_1 = int(clan_id)
        encrypted = _aes_cbc_encrypt(AES_KEY, AES_IV, msg.SerializeToString())
        url = f"https://{_client_host(region)}/RequestJoinClan"
        r = requests.post(url, headers=_client_headers(jwt_token),
                          data=encrypted, verify=False, timeout=15)
        return {"action": "Join Clan", "success": r.status_code == 200,
                "code": r.status_code, "clan_id": str(clan_id),
                "uid": str(uid) if uid else None, "name": name, "region": region,
                "server_response": r.text[:500] if r.text else "N/A",
                "time": now_bdt_full()}
    except Exception as e:
        base["error"] = str(e); return base

def _guild_leave(jwt_token, clan_id, region, uid, name):
    base = {"action": "Quit Clan", "success": False, "code": 500,
            "clan_id": str(clan_id), "uid": str(uid) if uid else None,
            "name": name, "region": region, "login_method": "N/A",
            "open_id": None, "access_token": None, "server_response": "N/A",
            "time": now_bdt_full()}
    if not _HAS_QUIT_CLAN:
        base["error"] = "QuitClanReq_pb2.py missing"; return base
    try:
        msg = QuitClanReq_pb2.QuitClanReq(); msg.field_1 = int(clan_id)
        encrypted = _aes_cbc_encrypt(AES_KEY, AES_IV, msg.SerializeToString())
        url = f"https://{_client_host(region)}/QuitClan"
        r = requests.post(url, headers=_client_headers(jwt_token),
                          data=encrypted, verify=False, timeout=15)
        return {"action": "Quit Clan", "success": r.status_code == 200,
                "code": r.status_code, "clan_id": str(clan_id),
                "uid": str(uid) if uid else None, "name": name, "region": region,
                "server_response": r.text[:500] if r.text else "N/A",
                "time": now_bdt_full()}
    except Exception as e:
        base["error"] = str(e); return base

# ═══════════════════════════════════════════════════════════
#  INFO HELPERS
# ═══════════════════════════════════════════════════════════
def _get_info_token_sync(region):
    ru = region.upper()
    cached = info_token_cache.get(ru)
    if cached and time.time() < cached.get('expiry', 0): return cached['token']
    fb = INFO_FALLBACK_ACCOUNTS.get(ru)
    if not fb: return None
    at, oid = _guest_login_oauth(fb['uid'], fb['password'])
    if not at or not oid: return None
    try:
        result, code = _internal_generate_jwt(at, oid)
        if code == 200 and result.get("token"):
            info_token_cache[ru] = {'token': result['token'],
                                    'expiry': time.time() + INFO_TOKEN_DURATION}
            return result['token']
    except Exception: pass
    return None

def _get_player_info_full(encrypted_uid, region, token):
    if not _HAS_PERSONAL_SHOW: return None
    um = {
        'IND': 'https://client.ind.freefiremobile.com/GetPlayerPersonalShow',
        'BR': 'https://client.us.freefiremobile.com/GetPlayerPersonalShow',
        'US': 'https://client.us.freefiremobile.com/GetPlayerPersonalShow',
        'ME': 'https://client.us.freefiremobile.com/GetPlayerPersonalShow',
    }
    url = um.get(region, 'https://clientbp.ppmainecoonghj.com/GetPlayerPersonalShow')
    edata = bytes.fromhex(encrypted_uid)
    headers = {'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
               'Authorization': f"Bearer {token}",
               'Content-Type': "application/x-www-form-urlencoded",
               'X-GA': "v1 1", 'ReleaseVersion': RELEASEVERSION}
    try:
        r = requests.post(url, data=edata, headers=headers, verify=False, timeout=30)
        if r.status_code == 200:
            msg = AccountPersonalShowInfo(); msg.ParseFromString(r.content); return msg
    except Exception: pass
    return None

def _fetch_player_data_full(uid):
    try:
        eu = _enc_uid(uid)
        for region in ['BD','IND','SG','ID','ME','BR','US','UK','EU','TH','VN']:
            token = _get_info_token_sync(region)
            if not token: continue
            info = _get_player_info_full(eu, region, token)
            if info:
                data = json.loads(MessageToJson(info))
                if "basicInfo" not in data: data["basicInfo"] = {}
                if "region" not in data["basicInfo"]: data["basicInfo"]["region"] = region
                return data
        return {"error": "Player not found in any region"}
    except Exception as e: return {"error": str(e)}

LEVELS = {1:0,2:48,3:202,4:544,5:1012,6:1844,7:2792,8:3800,9:4870,10:6004,
          11:7192,12:8448,13:9776,14:11140,15:12566,16:14060,17:15610,18:17224,
          19:18902,20:20632,21:22424,22:24728,23:26192,24:28166,25:30200,
          26:32294,27:34448,28:37804,29:41174,30:44870,31:48852,32:53334,
          33:58566,34:64096,35:69994,36:76460,37:83108,38:91128,39:99322,
          40:108092,41:120144,42:133266,43:147472,44:162760,45:179126,
          46:196572,47:215368,48:235516,49:257010,50:279860,51:304056,52:348318,
          53:394982,54:444044,55:495508,56:549364,57:633756,58:721744,59:813336,
          60:908522,61:1041438,62:1180352,63:1325256,64:1476184,65:1634300,
          66:1840946,67:2056594,68:2281242,69:2514880,70:2757530,71:3059506,
          72:3372284,73:3699456,74:4041030,75:4397020,76:4829104,77:5282204,
          78:5756304,79:6251404,80:6767504,81:7381324,82:8043154,83:8752952,
          84:9510808,85:10316638,86:11277190,87:12360748,88:13360304,89:14482858,
          90:15659418,91:17026708,92:18453688,93:19941280,94:21488570,95:23095858,
          96:24763138,97:26490138,98:28277708,99:30124996,100:32032284}

def _level_progress(level, exp):
    try:
        level = int(level); exp = int(exp)
    except Exception:
        return {"next_level": "N/A", "needed": "N/A", "gained": 0, "span": 0,
                "percent": 0, "bar": "⬜" * 10}
    cur = LEVELS.get(level); nxt = LEVELS.get(level + 1)
    if cur is None or nxt is None:
        return {"next_level": level + 1 if level < max(LEVELS) else level,
                "needed": 0 if level >= max(LEVELS) else "N/A", "gained": 0, "span": 0,
                "percent": 100 if level >= max(LEVELS) else 0,
                "bar": "🟩" * 10 if level >= max(LEVELS) else "⬜" * 10}
    span = max(1, nxt - cur); gained = max(0, min(exp - cur, span))
    needed = max(0, nxt - exp); percent = (gained / span) * 100
    filled = max(0, min(10, round(percent / 10)))
    return {"next_level": level + 1, "needed": needed, "gained": gained,
            "span": span, "percent": percent,
            "bar": ("🟩" * filled) + ("⬜" * (10 - filled))}

# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════
@app.get("/")
def index():
    return render_template("index.html", **_get_branding())

@app.get("/health")
def route_health():
    return _jsonify({"status": "ok", "service": BRAND_NAME, "jwt_mode": "LOCAL",
                     "timezone": "Asia/Dhaka (BDT, UTC+6)", "now_bdt": now_bdt_str(),
                     "has_personal_show": _HAS_PERSONAL_SHOW,
                     "has_friend_proto": _HAS_REMOVE_FRIEND,
                     "has_clan_proto": _HAS_REQ_CLAN and _HAS_QUIT_CLAN,
                     "servers": list(SERVER_ACCOUNT_FILES.keys())})

@app.get("/stats")
def api_stats():
    try:
        total = sum(len(_load_accounts_for_server(s)) for s in SERVER_ACCOUNT_FILES)
        return _jsonify({"delivered": "1.2M+", "active": f"{total}+", "uptime": "99.9%",
                         "status": "Online", "total": total, "now_bdt": now_bdt_str()})
    except Exception:
        return _jsonify({"delivered": "1.2M+", "active": "45K+", "uptime": "99.9%",
                         "status": "Online", "total": 0, "now_bdt": now_bdt_str()})

def _fp(name):
    v = None
    try:
        if request.form and name in request.form: v = request.form.get(name)
    except Exception: pass
    if v is None:
        try:
            if request.is_json:
                body = request.get_json(silent=True) or {}
                v = body.get(name)
        except Exception: pass
    if v is None: v = request.args.get(name)
    return v

# ═══════════════════════════════════════════════════════════
#  /like
# ═══════════════════════════════════════════════════════════
@app.get("/like")
def handle_like():
    try:
        uid = request.args.get("uid"); srv = request.args.get("server_name", "").upper()
        api_key = request.args.get("key", "").strip()
        if not api_key or not is_valid_key(api_key):
            return _jsonify({"status": 0, "success": False,
                             "error": "Invalid or missing API key 🔑",
                             "KeyExpiresAt": "N/A", "KeyRemainingRequests": "0/0"}, 403)
        if not uid or not srv:
            return _jsonify({"status": 0, "success": False, "error": "UID and server_name required"}), 400
        if srv not in SERVER_ACCOUNT_FILES:
            return _jsonify({"status": 0, "success": False,
                             "error": f"Unsupported server '{srv}'",
                             "allowed": list(SERVER_ACCOUNT_FILES.keys())}), 400
        _log(f"🔍 /like uid={uid} region={srv}", "info")
        accounts = _load_accounts_for_server(srv)
        if not accounts:
            return _jsonify({"status": 0, "success": False, "error": f"No accounts for {srv}"}), 500
        tokens = get_cached_tokens(srv) or get_cached_tokens(srv, force_refresh=True)
        if not tokens:
            return _jsonify({"status": 0, "success": False, "error": "Failed to get tokens"}), 500
        _log(f"🔑 Using {len(tokens)} tokens", "info")
        token = tokens[0]; encrypted = _enc_uid(uid)
        before = _parse_show_info(_show_request(encrypted, srv, token))
        if before is None:
            return _jsonify({"status": 0, "success": False, "error": "Unable to fetch player info",
                             "LikesGivenByAPI": 0, "LikesbeforeCommand": 0, "LikesafterCommand": 0,
                             "PlayerNickname": "N/A", "UID": uid, "Region": srv,
                             **_key_response_fields(api_key)})
        before_likes = int(before["likes"]); player_name = before["name"]
        _log(f"📊 Before: {before_likes} | {player_name}", "info")
        url = _like_url_for(srv)
        like_t0 = time.time()
        result = send_likes_from_all_tokens(uid, srv, url, tokens)
        _log(f"✓ Burst {round(time.time()-like_t0,1)}s — {result['success']}/{result['total']}", "ok")
        after = _parse_show_info(_show_request(encrypted, srv, token)) or before
        after_likes = int(after["likes"]); like_given = max(0, after_likes - before_likes)
        charged = False
        if like_given > 0:
            increment_key_usage(api_key); charged = True
            _log(f"✅ +{like_given} likes", "ok")
        if like_given > 0:
            status_val = 1; msg = "✅ Success"
        elif before_likes >= 99999:
            status_val = 2; msg = "🎉 Max likes!"
        else:
            status_val = 2
            msg = "⚠️ No likes were given."
        resp = {"status": status_val, "success": status_val == 1, "message": msg,
                "PlayerNickname": player_name, "UID": str(uid), "Region": srv,
                "LikesbeforeCommand": before_likes, "LikesafterCommand": after_likes,
                "LikesGivenByAPI": like_given, "Owner": OWNER_HANDLE,
                "key_usage_charged": charged}
        resp.update(_key_response_fields(api_key))
        return _jsonify(resp)
    except Exception as e:
        return _jsonify({"status": 0, "success": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
#  /bio
# ═══════════════════════════════════════════════════════════
@app.route("/bio", methods=["GET", "POST"])
def bio_endpoint():
    try:
        bio = _fp("bio"); jwt_in = _fp("jwt")
        uid = _fp("uid"); password = _fp("pass") or _fp("password")
        access_token_in = _fp("access") or _fp("access_token")
        if not bio:
            return _jsonify({"status": "failed", "message": "Missing 'bio'",
                             "time": now_bdt_full()}), 400
        bio = str(bio).strip()
        if len(bio) > 300:
            return _jsonify({"status": "failed", "message": "Bio > 300 chars",
                             "time": now_bdt_full()}), 400

        final_jwt, method, f_uid, f_name, f_region, f_oid, f_at, err = _get_login_jwt_info(
            uid=uid, password=password, access_token=access_token_in, jwt_token=jwt_in)
        if not final_jwt:
            return _jsonify({"status": "failed", "message": err or "Login failed",
                             "time": now_bdt_full()}), 400

        _log(f"📝 /bio UID={f_uid} via {method}", "info")
        result = _upload_bio(final_jwt, bio)
        _log(f"{'✅' if result['status']=='success' else '❌'} Bio {result['status']} HTTP {result['code']}",
             "ok" if result["status"]=="success" else "err")

        return _jsonify({
            "status": result["status"], "code": result["code"], "bio": bio,
            "uid": str(f_uid) if f_uid else None, "name": f_name, "region": f_region,
            "login_method": method, "open_id": f_oid, "access_token": f_at,
            "server_response": result.get("server_response", "N/A"),
            "time": now_bdt_full()})
    except Exception as e:
        return _jsonify({"status": "failed", "message": str(e),
                         "time": now_bdt_full()}), 500

# ═══════════════════════════════════════════════════════════
#  /friend/add  /friend/remove  /friend/list
# ═══════════════════════════════════════════════════════════
@app.route("/friend/add", methods=["POST", "GET"])
def friend_add_endpoint():
    try:
        uid = _fp("uid"); password = _fp("pass") or _fp("password")
        access_token = _fp("access_token") or _fp("access")
        jwt_in = _fp("jwt")
        target = _fp("friend_uid") or _fp("target_uid") or _fp("target")
        region = (_fp("server_name") or _fp("region") or "BD").upper()
        if not target:
            return _jsonify({"status": "failed", "error": "friend_uid required",
                             "time": now_bdt_full()}), 400
        final_jwt, method, f_uid, f_name, f_region, f_oid, f_at, err = _get_login_jwt_info(
            uid=uid, password=password, access_token=access_token, jwt_token=jwt_in)
        if not final_jwt:
            return _jsonify({"status": "failed", "error": err or "Login failed",
                             "time": now_bdt_full()}), 400
        _log(f"👥 Friend add {target} ({region}) via {method}", "info")
        result = _friend_add(final_jwt, target, region, f_uid)
        result["login_method"] = method; result["open_id"] = f_oid; result["access_token"] = f_at
        _log(f"{'✅' if result['status']=='success' else '❌'} Friend add {target}",
             "ok" if result["status"]=="success" else "err")
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"status": "failed", "error": str(e),
                         "time": now_bdt_full()}), 500

@app.route("/friend/remove", methods=["POST", "GET"])
def friend_remove_endpoint():
    try:
        uid = _fp("uid"); password = _fp("pass") or _fp("password")
        access_token = _fp("access_token") or _fp("access")
        jwt_in = _fp("jwt")
        target = _fp("friend_uid") or _fp("target_uid") or _fp("target")
        region = (_fp("server_name") or _fp("region") or "BD").upper()
        if not target:
            return _jsonify({"status": "failed", "error": "friend_uid required",
                             "time": now_bdt_full()}), 400
        final_jwt, method, f_uid, f_name, f_region, f_oid, f_at, err = _get_login_jwt_info(
            uid=uid, password=password, access_token=access_token, jwt_token=jwt_in)
        if not final_jwt:
            return _jsonify({"status": "failed", "error": err or "Login failed",
                             "time": now_bdt_full()}), 400
        if not f_uid:
            return _jsonify({"status": "failed", "error": "Cannot decode author UID",
                             "time": now_bdt_full()}), 400
        _log(f"👥 Friend remove {target} ({region}) via {method}", "info")
        result = _friend_remove(final_jwt, f_uid, target, region)
        result["login_method"] = method; result["open_id"] = f_oid; result["access_token"] = f_at
        _log(f"{'✅' if result['status']=='success' else '❌'} Friend remove {target}",
             "ok" if result["status"]=="success" else "err")
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"status": "failed", "error": str(e),
                         "time": now_bdt_full()}), 500

@app.route("/friend/list", methods=["POST", "GET"])
def friend_list_endpoint():
    try:
        uid = _fp("uid"); password = _fp("pass") or _fp("password")
        access_token = _fp("access_token") or _fp("access")
        jwt_in = _fp("jwt")
        region = (_fp("server_name") or _fp("region") or "BD").upper()
        final_jwt, method, f_uid, f_name, f_region, f_oid, f_at, err = _get_login_jwt_info(
            uid=uid, password=password, access_token=access_token, jwt_token=jwt_in)
        if not final_jwt:
            return _jsonify({"success": False, "error": err or "Login failed",
                             "time": now_bdt_full()}), 400
        _log(f"👥 Friend list ({region}) via {method}", "info")
        result = _friend_list(final_jwt, region)
        result["login_method"] = method
        result["author_uid"] = str(f_uid) if f_uid else None
        result["author_name"] = f_name
        result["open_id"] = f_oid; result["access_token"] = f_at
        _log(f"{'✅' if result.get('success') else '❌'} Friend list: {result.get('friends_count',0)}",
             "ok" if result.get("success") else "err")
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"success": False, "error": str(e),
                         "time": now_bdt_full()}), 500

# ═══════════════════════════════════════════════════════════
#  /guild/join  /guild/leave
# ═══════════════════════════════════════════════════════════
@app.route("/guild/join", methods=["POST", "GET"])
def guild_join_endpoint():
    try:
        uid = _fp("uid"); password = _fp("pass") or _fp("password")
        access_token = _fp("access_token") or _fp("access")
        jwt_in = _fp("jwt")
        clan_id = _fp("clan_id") or _fp("clan")
        region = (_fp("server_name") or _fp("region") or "BD").upper()
        if not clan_id:
            return _jsonify({"success": False, "error": "clan_id required",
                             "time": now_bdt_full()}), 400
        final_jwt, method, f_uid, f_name, f_region, f_oid, f_at, err = _get_login_jwt_info(
            uid=uid, password=password, access_token=access_token, jwt_token=jwt_in)
        if not final_jwt:
            return _jsonify({"success": False, "error": err or "Login failed",
                             "time": now_bdt_full()}), 400
        _log(f"🛡 Guild join clan={clan_id} ({region})", "info")
        result = _guild_join(final_jwt, clan_id, region, f_uid, f_name)
        result["login_method"] = method; result["open_id"] = f_oid; result["access_token"] = f_at
        _log(f"{'✅' if result['success'] else '❌'} Guild join {clan_id}",
             "ok" if result["success"] else "err")
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"success": False, "error": str(e),
                         "time": now_bdt_full()}), 500

@app.route("/guild/leave", methods=["POST", "GET"])
def guild_leave_endpoint():
    try:
        uid = _fp("uid"); password = _fp("pass") or _fp("password")
        access_token = _fp("access_token") or _fp("access")
        jwt_in = _fp("jwt")
        clan_id = _fp("clan_id") or _fp("clan")
        region = (_fp("server_name") or _fp("region") or "BD").upper()
        if not clan_id:
            return _jsonify({"success": False, "error": "clan_id required",
                             "time": now_bdt_full()}), 400
        final_jwt, method, f_uid, f_name, f_region, f_oid, f_at, err = _get_login_jwt_info(
            uid=uid, password=password, access_token=access_token, jwt_token=jwt_in)
        if not final_jwt:
            return _jsonify({"success": False, "error": err or "Login failed",
                             "time": now_bdt_full()}), 400
        _log(f"🛡 Guild leave clan={clan_id} ({region})", "info")
        result = _guild_leave(final_jwt, clan_id, region, f_uid, f_name)
        result["login_method"] = method; result["open_id"] = f_oid; result["access_token"] = f_at
        _log(f"{'✅' if result['success'] else '❌'} Guild leave {clan_id}",
             "ok" if result["success"] else "err")
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"success": False, "error": str(e),
                         "time": now_bdt_full()}), 500

# ═══════════════════════════════════════════════════════════
#  /eat
# ═══════════════════════════════════════════════════════════
@app.route("/eat", methods=["POST", "GET"])
def eat_endpoint():
    try:
        eat_input = _fp("eat_token") or _fp("eat")
        if not eat_input:
            return _jsonify({"status": "failed", "message": "'eat_token' required",
                             "time": now_bdt_full()}), 400
        eat_token = str(eat_input).strip()
        if "http" in eat_token or "?" in eat_token:
            try:
                q = parse_qs(urlparse(eat_token).query)
                if "eat" in q: eat_token = q["eat"][0]
            except Exception: pass
        _log(f"🔑 /eat converting...", "info")
        api_url = f"https://api-otrss.garena.com/support/callback/?access_token={eat_token}"
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/114.0.0.0 Mobile"}
        response = requests.get(api_url, headers=headers, allow_redirects=True, timeout=10)
        final_params = parse_qs(urlparse(response.url).query)
        access_token = final_params.get("access_token", [None])[0]
        if not access_token:
            _log("❌ EAT resolve failed", "err")
            return _jsonify({"status": "failed",
                             "message": "Failed to resolve EAT → access_token",
                             "eat_token": eat_token[:20] + "..." if len(eat_token) > 20 else eat_token,
                             "time": now_bdt_full()}), 400
        oid, _ = _fetch_open_id(access_token)
        result, code = _internal_generate_jwt(access_token, oid)
        jwt_token = result.get("token") if code == 200 else None
        _log("✅ EAT converted", "ok")
        return _jsonify({"status": "success",
                         "eat_token": eat_token[:20] + "..." if len(eat_token) > 20 else eat_token,
                         "access_token": access_token, "open_id": oid,
                         "account_id": result.get("account_id") if code == 200 else None,
                         "account_name": result.get("account_name") if code == 200 else None,
                         "region": result.get("region") if code == 200 else None,
                         "platform": result.get("platform") if code == 200 else None,
                         "token": jwt_token, "time": now_bdt_full()})
    except Exception as e:
        _log(f"❌ /eat error: {e}", "err")
        return _jsonify({"status": "failed", "message": str(e),
                         "time": now_bdt_full()}), 500

# ═══════════════════════════════════════════════════════════
#  JWT GENERATOR
# ═══════════════════════════════════════════════════════════
@app.route("/token", methods=["GET", "POST"])
def jwt_token_endpoint():
    uid = _fp("uid"); password = _fp("password")
    if not uid or not password:
        return _jsonify({"status": "error", "message": "Both 'uid' and 'password' required"}), 400
    at, oid = _guest_login_oauth(uid, password)
    if not at or not oid:
        return _jsonify({"status": "error", "message": "Guest login failed"}), 401
    result, code = _internal_generate_jwt(at, oid)
    return _jsonify(result, code)

@app.route("/access", methods=["GET", "POST"])
def jwt_access_endpoint():
    access_token = _fp("access_token")
    if not access_token:
        return _jsonify({"status": "error", "message": "'access_token' required"}), 400
    result, code = _internal_generate_jwt(access_token)
    return _jsonify(result, code)

# ═══════════════════════════════════════════════════════════
#  INFO / REGION / LEVEL / CHECK
# ═══════════════════════════════════════════════════════════
@app.get("/info")
def api_info():
    uid = request.args.get("uid", "").strip()
    if not uid or not uid.isdigit() or not (8 <= len(uid) <= 11):
        return _jsonify({"status": 0, "success": False, "error": "Invalid UID"}, 400)
    if not _HAS_PERSONAL_SHOW:
        return _jsonify({"status": 0, "success": False, "error": "AccountPersonalShow_pb2.py missing"}, 500)
    try:
        data = _fetch_player_data_full(uid)
        if "error" in data:
            return _jsonify({"status": 0, "success": False, "error": data["error"]}, 404)
        return _jsonify({"status": 1, "success": True, "uid": uid, "data": data})
    except Exception as e:
        return _jsonify({"status": 0, "success": False, "error": str(e)}), 500

@app.get("/region")
def api_region():
    uid = request.args.get("uid", "").strip()
    if not uid or not uid.isdigit():
        return _jsonify({"status": 0, "success": False, "error": "Invalid UID"}, 400)
    try:
        data = _fetch_player_data_full(uid)
        if "error" in data:
            return _jsonify({"status": 0, "success": False, "error": data["error"]}, 404)
        b = data.get("basicInfo", {})
        return _jsonify({"status": 1, "success": True, "uid": uid,
                         "player_nickname": b.get("nickname", "N/A"),
                         "region": b.get("region", "N/A"),
                         "level": b.get("level", "N/A"),
                         "likes": b.get("liked", 0)})
    except Exception as e:
        return _jsonify({"status": 0, "success": False, "error": str(e)}), 500

@app.get("/level")
def api_level():
    uid = request.args.get("uid", "").strip()
    if not uid or not uid.isdigit():
        return _jsonify({"status": 0, "success": False, "error": "Invalid UID"}, 400)
    try:
        data = _fetch_player_data_full(uid)
        if "error" in data:
            return _jsonify({"status": 0, "success": False, "error": data["error"]}, 404)
        b = data.get("basicInfo", {})
        level = b.get("level", 0); exp = b.get("exp", 0)
        details = _level_progress(level, exp)
        return _jsonify({"status": 1, "success": True, "uid": uid,
                         "player_nickname": b.get("nickname", "N/A"),
                         "level": level, "exp": exp,
                         "next_level": details["next_level"],
                         "exp_needed": details["needed"],
                         "exp_gained": details["gained"],
                         "exp_span": details["span"],
                         "progress_percent": round(details["percent"], 2),
                         "bar": details["bar"]})
    except Exception as e:
        return _jsonify({"status": 0, "success": False, "error": str(e)}), 500

@app.get("/check")
def api_check():
    uid = request.args.get("uid", "").strip()
    if not uid or not uid.isdigit():
        return _jsonify({"status": 0, "success": False, "error": "Invalid UID"}, 400)
    try:
        rd = _fetch_player_data_full(uid)
        if "error" in rd: rd = {}
        url = f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}"
        h = {"User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
             "Accept": "application/json, text/plain, */*",
             "referer": "https://ff.garena.com/en/support/",
             "x-requested-with": "B6FksShzIgjfrYImLpTsadjS86sddhFH"}
        try:
            r = requests.get(url, headers=h, timeout=15, verify=False)
            bd = r.json() if r.status_code == 200 else {}
        except Exception: bd = {}
        isb = bd.get("data", {}).get("is_banned", 0)
        period = bd.get("data", {}).get("period", 0)
        b = rd.get("basicInfo", {})
        return _jsonify({"status": 1, "success": True, "uid": uid,
                         "player_nickname": b.get("nickname", "N/A"),
                         "region": b.get("region", "N/A"),
                         "level": b.get("level", "N/A"),
                         "is_banned": bool(isb), "ban_period": period,
                         "status_text": "BANNED" if isb else "NOT BANNED"})
    except Exception as e:
        return _jsonify({"status": 0, "success": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
#  ADMIN: LOGS
# ═══════════════════════════════════════════════════════════
@app.get("/logs")
@_require_master
def get_logs():
    try: since = int(request.args.get("since", 0))
    except Exception: since = 0
    with LOG_LOCK:
        logs = [l for l in LOG_BUFFER if l["id"] > since]
        last_id = LOG_COUNTER[0]
    return _jsonify({"status": "success", "logs": logs, "last_id": last_id, "count": len(logs)})

# ═══════════════════════════════════════════════════════════
#  ADMIN: TOKENS
# ═══════════════════════════════════════════════════════════
@app.get("/tokens/status")
@_require_master
def tokens_status():
    result = {}; ga = 0; gt = 0; gv = 0
    for srv in SERVER_ACCOUNT_FILES.keys():
        accs = _load_accounts_for_server(srv); ta = len(accs)
        entry = TOKEN_CACHE.get(srv, {})
        cached = len(entry.get("tokens", [])); expiry = entry.get("expiry", 0)
        building = entry.get("building", False)
        stopped = entry.get("stopped", False)
        if cached == 0 and not building:
            disk = _load_token_cache_from_disk(srv)
            if disk:
                cached = len(disk["tokens"]); expiry = disk["expiry"]
                generated = disk.get("generated_at", "")
            else: generated = ""
        else: generated = entry.get("generated_at", "")
        nts = time.time()
        if expiry > nts and cached > 0: valid = cached; expired = 0
        else: valid = 0; expired = cached
        result[srv] = {"total_accounts": ta, "total_tokens": cached, "valid_tokens": valid,
                       "expired_tokens": expired, "missing_tokens": max(0, ta - valid),
                       "expires_at_bdt": datetime.fromtimestamp(expiry, BDT).strftime("%Y-%m-%d %H:%M:%S") if expiry else "N/A",
                       "expires_in_sec": max(0, int(expiry - nts)) if expiry else 0,
                       "generated_at": generated, "building": building,
                       "stopped": stopped}
        ga += ta; gt += cached; gv += valid
    return _jsonify({"status": "success", "now_bdt": now_bdt_str(),
                     "ttl_hours": TOKEN_TTL // 3600,
                     "grand_total": {"total_accounts": ga, "total_tokens": gt,
                                     "valid_tokens": gv,
                                     "expired_tokens": max(0, gt - gv)},
                     "servers": result})

@app.get("/tokens/refresh")
@_require_master
def tokens_refresh():
    srv = request.args.get("server", "").upper().strip()
    if srv and srv in SERVER_ACCOUNT_FILES:
        _log(f"🔄 Manual refresh: {srv}", "info")
        refresh_token_cache_background(srv)
        return _jsonify({"status": "success", "message": f"Refreshing {srv}", "server": srv})
    _log("🔄 Manual refresh: ALL", "info")
    out = {}
    for s in SERVER_ACCOUNT_FILES.keys():
        if _load_accounts_for_server(s):
            refresh_token_cache_background(s); out[s] = "building"
    return _jsonify({"status": "success", "message": "All refreshing", "detail": out})

@app.get("/tokens/stop")
@_require_master
def tokens_stop():
    srv = request.args.get("server", "").upper().strip()
    if not srv or srv not in SERVER_ACCOUNT_FILES:
        return _jsonify({"status": "error", "message": "Invalid server"}), 400
    STOP_FLAGS[srv].set()
    _log(f"⛔ Stop requested: {srv}", "warn")
    with TOKEN_CACHE_LOCK:
        if srv in TOKEN_CACHE:
            TOKEN_CACHE[srv]["building"] = False
    return _jsonify({"status": "success",
                     "message": f"Stop signal sent to {srv}",
                     "server": srv})

@app.get("/tokens/clear")
@_require_master
def tokens_clear():
    srv = request.args.get("server", "").upper().strip()
    with TOKEN_CACHE_LOCK:
        if srv and srv in TOKEN_CACHE: del TOKEN_CACHE[srv]
        else: TOKEN_CACHE.clear()
    for s, p in TOKEN_CACHE_FILES.items():
        if (not srv or srv == s) and os.path.exists(p):
            try: os.remove(p)
            except OSError: pass
    _log(f"🗑 Cache cleared: {srv or 'ALL'}", "warn")
    return _jsonify({"status": "success", "message": "Cache cleared"})

# ═══════════════════════════════════════════════════════════
#  ADMIN: KEYS
# ═══════════════════════════════════════════════════════════
@app.get("/keys")
@_require_master
def api_keys_list():
    try:
        cfg = _read_config()
        allowed = cfg.get("ALLOWED_KEYS", {}) or {}
        admin = cfg.get("ADMIN_KEYS", []) or []
        keys = []
        for k, v in allowed.items():
            entry = _normalize_key_entry(v)
            keys.append({"key": k, "type": "normal",
                         "limit": int(entry.get("limit", 9999)),
                         "days": int(entry.get("days", 30)),
                         "customer": entry.get("customer", ""),
                         "created_at": entry.get("created_at", ""),
                         "expires_at": entry.get("expires_at"),
                         "used": int(entry.get("used", 0))})
        for k in admin:
            keys.append({"key": k, "type": "admin", "limit": "∞", "days": "∞",
                         "customer": "OWNER", "created_at": "", "expires_at": None, "used": 0})
        return _jsonify({"status": "success", "total": len(keys), "keys": keys})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.post("/keys")
@_require_master
def api_keys_add():
    try:
        body = request.get_json(silent=True) or {}
        nk = str(body.get("key", "")).strip()
        limit = int(body.get("limit", 9999)); days = int(body.get("days", 30))
        customer = str(body.get("customer", "")).strip()
        is_admin = bool(body.get("admin", False))
        if not nk: return _jsonify({"status": "error", "message": "Key required"}), 400
        cfg = _read_config()
        cfg.setdefault("ALLOWED_KEYS", {}); cfg.setdefault("ADMIN_KEYS", [])
        if is_admin:
            if nk in cfg["ADMIN_KEYS"]: return _jsonify({"status": "error", "message": "Exists"}), 409
            cfg["ADMIN_KEYS"].append(nk)
        else:
            if nk in cfg["ALLOWED_KEYS"]: return _jsonify({"status": "error", "message": "Exists"}), 409
            now = now_bdt(); exp = (now + timedelta(days=days)).isoformat() if days > 0 else None
            cfg["ALLOWED_KEYS"][nk] = {"limit": limit, "days": days, "customer": customer,
                                       "created_at": now.isoformat(), "expires_at": exp, "used": 0}
        if not _write_config(cfg):
            return _jsonify({"status": "error", "message": "Write failed"}), 500
        _log(f"🔑 Key created: {nk[:12]}...", "ok")
        return _jsonify({"status": "success", "message": "Key added", "key": nk})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.put("/keys/<path:key_val>")
@_require_master
def api_keys_edit(key_val):
    try:
        body = request.get_json(silent=True) or {}
        cfg = _read_config(); allowed = cfg.get("ALLOWED_KEYS", {})
        if key_val not in allowed:
            return _jsonify({"status": "error", "message": "Not found"}), 404
        entry = _normalize_key_entry(allowed[key_val])
        if "limit" in body: entry["limit"] = int(body["limit"])
        if "days" in body:
            entry["days"] = int(body["days"])
            if int(body["days"]) > 0:
                try:
                    base = datetime.fromisoformat(entry.get("created_at", now_bdt().isoformat()))
                    if base.tzinfo is None: base = base.replace(tzinfo=BDT)
                except Exception: base = now_bdt()
                entry["expires_at"] = (base + timedelta(days=int(body["days"]))).isoformat()
            else: entry["expires_at"] = None
        if "customer" in body: entry["customer"] = str(body["customer"])
        if "used" in body: entry["used"] = int(body["used"])
        allowed[key_val] = entry
        if not _write_config(cfg):
            return _jsonify({"status": "error", "message": "Write failed"}), 500
        return _jsonify({"status": "success", "message": "Updated"})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.delete("/keys/<path:key_val>")
@_require_master
def api_keys_delete(key_val):
    try:
        cfg = _read_config(); removed = False
        if key_val in cfg.get("ALLOWED_KEYS", {}):
            del cfg["ALLOWED_KEYS"][key_val]; removed = True
        if key_val in cfg.get("ADMIN_KEYS", []):
            cfg["ADMIN_KEYS"].remove(key_val); removed = True
        if not removed: return _jsonify({"status": "error", "message": "Not found"}), 404
        if not _write_config(cfg):
            return _jsonify({"status": "error", "message": "Write failed"}), 500
        return _jsonify({"status": "success", "message": "Deleted"})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

# ═══════════════════════════════════════════════════════════
#  ADMIN: ACCOUNTS
# ═══════════════════════════════════════════════════════════
@app.get("/accounts/stats")
@_require_master
def api_accounts_stats():
    try:
        stats = {}; total = 0
        for srv in SERVER_ACCOUNT_FILES:
            c = len(_load_accounts_for_server(srv)); stats[srv] = c; total += c
        return _jsonify({"status": "success", "total": total, "servers": stats})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.get("/accounts/<server_name>")
@_require_master
def api_accounts_list(server_name):
    srv = server_name.upper()
    if srv not in SERVER_ACCOUNT_FILES:
        return _jsonify({"status": "error", "message": "Invalid"}), 400
    try:
        accs = _load_accounts_for_server(srv)
        masked = [{"uid": u,
                   "password": (p[:4] + "*" * max(0, len(p) - 4)) if len(p) > 4 else "****",
                   "password_len": len(p)} for u, p in accs]
        return _jsonify({"status": "success", "server": srv, "total": len(masked), "accounts": masked})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.post("/accounts/upload")
@_require_master
def api_accounts_upload():
    try:
        body = request.get_json(silent=True) or {}
        srv = str(body.get("server", "")).upper().strip()
        content = str(body.get("content", "")); mode = str(body.get("mode", "merge")).lower()
        if srv not in SERVER_ACCOUNT_FILES:
            return _jsonify({"status": "error", "message": "Invalid server"}), 400
        if not content.strip():
            return _jsonify({"status": "error", "message": "Empty"}), 400
        na = _parse_account_text(content)
        if not na: return _jsonify({"status": "error", "message": "No valid uid"}), 400
        if mode == "replace": final = na
        else:
            ex = _load_accounts_for_server(srv)
            merged = {u: p for u, p in ex}
            for u, p in na: merged[u] = p
            final = list(merged.items())
        if not _save_accounts_for_server(srv, final):
            return _jsonify({"status": "error", "message": "Save failed"}), 500
        _log(f"📤 Uploaded {len(na)} to {srv} ({mode})", "ok")
        refresh_token_cache_background(srv)
        return _jsonify({"status": "success", "server": srv, "mode": mode,
                         "parsed": len(na), "total_now": len(final),
                         "note": "Cache refreshing"})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.delete("/accounts/<server_name>/<uid>")
@_require_master
def api_accounts_delete(server_name, uid):
    srv = server_name.upper()
    if srv not in SERVER_ACCOUNT_FILES:
        return _jsonify({"status": "error", "message": "Invalid"}), 400
    try:
        accs = _load_accounts_for_server(srv)
        na = [(u, p) for u, p in accs if str(u) != str(uid)]
        if len(na) == len(accs):
            return _jsonify({"status": "error", "message": "Not found"}), 404
        if not _save_accounts_for_server(srv, na):
            return _jsonify({"status": "error", "message": "Save failed"}), 500
        return _jsonify({"status": "success", "message": "Deleted", "total_now": len(na)})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

@app.delete("/accounts/<server_name>")
@_require_master
def api_accounts_clear(server_name):
    srv = server_name.upper()
    if srv not in SERVER_ACCOUNT_FILES:
        return _jsonify({"status": "error", "message": "Invalid"}), 400
    try:
        if not _save_accounts_for_server(srv, []):
            return _jsonify({"status": "error", "message": "Save failed"}), 500
        _log(f"🗑 Cleared {srv}", "warn")
        return _jsonify({"status": "success", "message": "Cleared"})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

# ═══════════════════════════════════════════════════════════
#  SETTINGS ROUTES
# ═══════════════════════════════════════════════════════════
@app.get("/settings")
def api_settings_public():
    """Public branding — admin_key leak হয় না"""
    s = _read_settings()
    public = {k: v for k, v in s.items() if k != "admin_key"}
    return _jsonify({"status": "success", "settings": public})

@app.get("/settings/full")
@_require_master
def api_settings_full():
    return _jsonify({"status": "success", "settings": _read_settings()})

@app.post("/settings")
@_require_master
def api_settings_update():
    try:
        body = request.get_json(silent=True) or {}
        current = _read_settings()
        allowed = {"site_name", "title", "logo_url", "favicon_url",
                   "primary_color", "secondary_color", "accent_color",
                   "owner_handle", "telegram", "dev_name", "admin_key"}
        for k in list(allowed):
            if k in body:
                v = body[k]
                if isinstance(v, str):
                    v = v.strip()
                if k == "admin_key" and not v:
                    continue
                current[k] = v
        if not _write_settings(current):
            return _jsonify({"status": "error", "message": "Write failed"}), 500
        _log(f"⚙️ Settings updated by admin", "ok")
        return _jsonify({"status": "success", "message": "Settings saved",
                         "settings": current})
    except Exception as e:
        return _jsonify({"status": "error", "message": str(e)}), 500

# ═══════════════════════════════════════════════════════════
#  BOOT
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(f"  {BRAND_NAME} — Running")
    print(f"  Current BDT: {now_bdt_str()}")
    print(f"  PersonalShow: {'✅' if _HAS_PERSONAL_SHOW else '❌'}")
    print(f"  Friend: {'✅' if _HAS_REMOVE_FRIEND else '❌'}")
    print(f"  Clan: {'✅' if _HAS_REQ_CLAN and _HAS_QUIT_CLAN else '❌'}")
    print(f"  Master key: {_get_admin_key()}")
    print("=" * 60)
    _log(f"🚀 {BRAND_NAME} starting...", "ok")
    preload_token_cache()
    _log("🌐 Port 5000", "ok")
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Clean exit")
        os._exit(0)