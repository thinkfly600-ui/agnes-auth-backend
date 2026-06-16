import os, json
from flask import Flask, request, jsonify, session, send_from_directory, Response
from db import init_db, get_or_create_free_code, verify_code, upgrade_with_vip
from db import get_stats, generate_vip_codes, get_vip_codes, revoke_vip_code, assign_vip_code
from db import get_free_users, export_vip_csv, backup_db
from db import generate_free_codes_batch, get_free_codes_admin, assign_free_code, revoke_free_code
from auth import login_required, try_login, SECRET_KEY

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SECRET_KEY

@app.route("/api/get-code", methods=["POST"])
def api_get_code():
    data = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    if not phone or len(phone) != 11 or not phone.isdigit() or not phone.startswith("1"):
        return jsonify({"error": "请输入正确的11位手机号"}), 400
    result = get_or_create_free_code(phone)
    return jsonify({"phone": phone[:3] + "****" + phone[-4:], "code": result["code"], "expires_at": result["expires_at"], "is_new": result["new"]})

@app.route("/api/verify")
def api_verify():
    code = request.args.get("code", "").strip()
    if not code: return jsonify({"valid": False, "reason": "请输入激活码"})
    return jsonify(verify_code(code))

@app.route("/api/upgrade", methods=["POST"])
def api_upgrade():
    data = request.get_json(force=True)
    free_code = data.get("code", "").strip()
    vip_code = data.get("vip_code", "").strip()
    if not free_code or not vip_code: return jsonify({"success": False, "error": "请提供激活码和VIP码"}), 400
    return jsonify(upgrade_with_vip(free_code, vip_code))

@app.route("/admin/api/login", methods=["POST"])
def api_admin_login():
    return jsonify(try_login(request.get_json(force=True).get("password", "")))

@app.route("/admin/api/check")
def api_admin_check():
    return jsonify({"logged_in": session.get("admin_logged_in", False)})

@app.route("/admin/api/logout", methods=["POST"])
def api_admin_logout():
    session.clear(); return jsonify({"success": True})

@app.route("/admin/api/stats")
@login_required
def api_stats(): return jsonify(get_stats())

@app.route("/admin/api/vip-generate", methods=["POST"])
@login_required
def api_vip_generate():
    d = request.get_json(force=True)
    return jsonify(generate_vip_codes(min(max(int(d.get("count", 10)), 1), 500), d.get("note", "")))

@app.route("/admin/api/vip-codes")
@login_required
def api_vip_codes():
    return jsonify(get_vip_codes(request.args.get("status"), request.args.get("search"), int(request.args.get("page", 1))))

@app.route("/admin/api/vip-revoke", methods=["POST"])
@login_required
def api_vip_revoke():
    return jsonify(revoke_vip_code(request.get_json(force=True).get("vip_code", "").strip()))

@app.route("/admin/api/vip-assign", methods=["POST"])
@login_required
def api_vip_assign():
    d = request.get_json(force=True)
    phone = d.get("phone", "").strip()
    if not phone or len(phone) != 11 or not phone.isdigit(): return jsonify({"success": False, "error": "请输入正确的11位手机号"}), 400
    return jsonify(assign_vip_code(d.get("vip_code", "").strip(), phone, d.get("note", "")))

@app.route("/admin/api/free-generate", methods=["POST"])
@login_required
def api_free_generate():
    d = request.get_json(force=True)
    return jsonify(generate_free_codes_batch(min(max(int(d.get("count", 10)), 1), 500), d.get("note", "")))

@app.route("/admin/api/free-codes")
@login_required
def api_free_codes():
    return jsonify(get_free_codes_admin(request.args.get("status"), request.args.get("search"), int(request.args.get("page", 1))))

@app.route("/admin/api/free-assign", methods=["POST"])
@login_required
def api_free_assign():
    d = request.get_json(force=True)
    phone = d.get("phone", "").strip()
    if not phone or len(phone) != 11 or not phone.isdigit(): return jsonify({"success": False, "error": "请输入正确的11位手机号"}), 400
    return jsonify(assign_free_code(d.get("code", "").strip(), phone))

@app.route("/admin/api/free-revoke", methods=["POST"])
@login_required
def api_free_revoke():
    return jsonify(revoke_free_code(request.get_json(force=True).get("code", "").strip()))

@app.route("/admin/api/free-users")
@login_required
def api_free_users():
    return jsonify(get_free_users(int(request.args.get("page", 1))))

@app.route("/admin/api/export")
@login_required
def api_export():
    return Response(export_vip_csv(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=vip_codes.csv"})

@app.route("/admin/api/export-free")
@login_required
def api_export_free():
    import io, csv
    from db import get_db
    conn = get_db()
    rows = conn.execute("SELECT * FROM free_codes ORDER BY id DESC").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["激活码","手机号","等级","创建时间","到期日","VIP码"])
    for r in rows: writer.writerow([r["code"],r["phone"],r["tier"],r["created_at"],r["expires_at"],r["vip_code"] or ""])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=free_codes.csv"})

@app.route("/admin/api/backup", methods=["POST"])
@login_required
def api_backup():
    return jsonify({"success": True, "path": backup_db()})

@app.route("/")
def index(): return send_from_directory("static", "activate.html")

@app.route("/activate.html")
def activate_page(): return send_from_directory("static", "activate.html")

@app.route("/admin")
@app.route("/admin/")
def admin_login_page(): return send_from_directory("static/admin", "login.html")

@app.route("/admin/<path:filename>")
@login_required
def admin_pages(filename):
    valid = ("dashboard", "vip-codes", "free-codes", "free-users")
    if filename in valid or filename.endswith(".html"):
        target = filename if filename.endswith(".html") else f"{filename}.html"
        return send_from_directory("static/admin", target)
    return "Not Found", 404

if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("AI全驱数字人视频营销系统 - 后端服务")
    print(f"管理后台: http://0.0.0.0:5000/admin")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)