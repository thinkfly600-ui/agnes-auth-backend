import os, hashlib, time, functools
from flask import session, request, redirect, url_for

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123456")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

# Rate limiting for login
_lockout = {}

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        return f(*args, **kwargs)
    return decorated

def check_password(pwd):
    return pwd == ADMIN_PASSWORD

def try_login(password):
    ip = request.remote_addr or "unknown"
    key = f"login_{ip}"
    now = time.time()
    
    if key in _lockout and _lockout[key]["until"] > now:
        remaining = int(_lockout[key]["until"] - now)
        return {"success": False, "error": f"登录锁定中，请{remaining}秒后重试"}
    
    if check_password(password):
        _lockout.pop(key, None)
        session["admin_logged_in"] = True
        return {"success": True}
    else:
        _lockout[key] = _lockout.get(key, {"count": 0, "until": 0})
        _lockout[key]["count"] += 1
        if _lockout[key]["count"] >= 3:
            _lockout[key]["until"] = now + 300  # 5 min lockout
            return {"success": False, "error": "密码错误3次，已锁定5分钟"}
        return {"success": False, "error": f"密码错误，剩余{3 - _lockout[key]['count']}次尝试"}