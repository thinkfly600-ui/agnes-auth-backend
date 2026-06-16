import os, json
from flask import Flask, request, jsonify, session, send_file, send_from_directory
from db import init_db, get_or_create_free_code, verify_code, upgrade_with_vip
from db import get_stats, generate_vip_codes, get_vip_codes, revoke_vip_code
from db import get_free_users, export_vip_csv, backup_db
from auth import login_required, try_login, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ============================================================
# Public API
# ============================================================

@app.route("/api/get-code", methods=["POST"])
def api_get_code():
    data = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    
    # Basic phone validation (Chinese mobile: 11 digits starting with 1)
    if not phone or len(phone) != 11 or not phone.isdigit() or not phone.startswith("1"):
        return jsonify({"error": "请输入正确的11位手机号"}), 400
    
    result = get_or_create_free_code(phone)
    return jsonify({
        "phone": phone[:3] + "****" + phone[-4:],
        "code": result["code"],
        "expires_at": result["expires_at"],
        "is_new": result["new"]
    })

@app.route("/api/verify")
def api_verify():
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"valid": False, "reason": "请输入激活码"})
    
    result = verify_code(code)
    return jsonify(result)

@app.route("/api/upgrade", methods=["POST"])
def api_upgrade():
    data = request.get_json(force=True)
    free_code = data.get("code", "").strip()
    vip_code = data.get("vip_code", "").strip()
    
    if not free_code or not vip_code:
        return jsonify({"success": False, "error": "请提供激活码和VIP码"}), 400
    
    result = upgrade_with_vip(free_code, vip_code)
    return jsonify(result)

# ============================================================
# Admin API (requires login)
# ============================================================

@app.route("/admin/api/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(force=True)
    result = try_login(data.get("password", ""))
    return jsonify(result)

@app.route("/admin/api/check")
def api_admin_check():
    return jsonify({"logged_in": session.get("admin_logged_in", False)})

@app.route("/admin/api/logout", methods=["POST"])
def api_admin_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/admin/api/stats")
@login_required
def api_stats():
    return jsonify(get_stats())

@app.route("/admin/api/vip-generate", methods=["POST"])
@login_required
def api_vip_generate():
    data = request.get_json(force=True)
    count = min(max(int(data.get("count", 10)), 1), 500)
    note = data.get("note", "")
    result = generate_vip_codes(count, note)
    return jsonify(result)

@app.route("/admin/api/vip-codes")
@login_required
def api_vip_codes():
    status = request.args.get("status")
    search = request.args.get("search")
    page = int(request.args.get("page", 1))
    return jsonify(get_vip_codes(status=status, search=search, page=page))

@app.route("/admin/api/vip-revoke", methods=["POST"])
@login_required
def api_vip_revoke():
    data = request.get_json(force=True)
    vip_code = data.get("vip_code", "").strip()
    return jsonify(revoke_vip_code(vip_code))

@app.route("/admin/api/free-users")
@login_required
def api_free_users():
    page = int(request.args.get("page", 1))
    return jsonify(get_free_users(page=page))

@app.route("/admin/api/export")
@login_required
def api_export():
    csv_data = export_vip_csv()
    import io
    from flask import Response
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=vip_codes.csv"}
    )

@app.route("/admin/api/backup", methods=["POST"])
@login_required
def api_backup():
    path = backup_db()
    return jsonify({"success": True, "path": path})

# ============================================================
# Static Pages
# ============================================================

@app.route("/")
def index():
    return send_from_directory("static", "activate.html")

@app.route("/activate.html")
def activate_page():
    return send_from_directory("static", "activate.html")

@app.route("/admin")
@app.route("/admin/")
def admin_login_page():
    return send_from_directory("static/admin", "login.html")

@app.route("/admin/<path:filename>")
@login_required
def admin_pages(filename):
    if filename in ("dashboard", "vip-codes", "free-users") or filename.endswith(".html"):
        target = filename if filename.endswith(".html") else f"{filename}.html"
        return send_from_directory("static/admin", target)
    return "Not Found", 404

# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("Agnes AI Auth Backend")
    print(f"Admin: http://0.0.0.0:5000/admin")
    print(f"Activate: http://0.0.0.0:5000/activate.html")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)