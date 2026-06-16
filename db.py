import sqlite3, os, datetime, secrets, string

DB_PATH = os.path.join(os.path.dirname(__file__), "codes.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS free_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL UNIQUE,
            code TEXT UNIQUE NOT NULL,
            tier TEXT DEFAULT 'free',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            renewed_at TEXT,
            vip_code TEXT,
            upgraded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vip_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vip_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'unused',
            used_by_phone TEXT,
            used_by_free_code TEXT,
            used_at TEXT,
            revoked_at TEXT,
            generated_at TEXT NOT NULL,
            batch_id TEXT,
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

def _gen_code(prefix, length=8):
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"{prefix}-{part1}-{part2}"

def _gen_vip_code():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(secrets.choice(chars) for _ in range(4)) for _ in range(3)]
    return f"VIP-{parts[0]}-{parts[1]}-{parts[2]}"

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def expiry_date():
    return (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")

# ============== Public API functions ==============

def get_or_create_free_code(phone):
    """Get existing valid code for phone, or create new one. Expired codes get renewed."""
    conn = get_db()
    row = conn.execute("SELECT * FROM free_codes WHERE phone = ?", (phone,)).fetchone()
    now = datetime.datetime.now()
    
    if row:
        expires = datetime.datetime.strptime(row["expires_at"], "%Y-%m-%d")
        if expires > now:
            # Still valid, return existing
            conn.close()
            return {"code": row["code"], "expires_at": row["expires_at"], "new": False}
        else:
            # Expired, renew with new code
            new_code = _gen_code("FREE")
            conn.execute(
                "UPDATE free_codes SET code=?, renewed_at=?, expires_at=?, tier='free' WHERE phone=?",
                (new_code, now_str(), expiry_date(), phone)
            )
            conn.commit()
            _log_admin("renew_free", f"Phone {phone} renewed with {new_code}")
            conn.close()
            return {"code": new_code, "expires_at": expiry_date(), "new": True}
    else:
        # New user
        new_code = _gen_code("FREE")
        conn.execute(
            "INSERT INTO free_codes (phone, code, tier, created_at, expires_at) VALUES (?,?,?,?,?)",
            (phone, new_code, "free", now_str(), expiry_date())
        )
        conn.commit()
        _log_admin("new_free", f"Phone {phone} received {new_code}")
        conn.close()
        return {"code": new_code, "expires_at": expiry_date(), "new": True}

def verify_code(code):
    """Verify activation code validity, return info or error."""
    conn = get_db()
    row = conn.execute("SELECT * FROM free_codes WHERE code = ?", (code,)).fetchone()
    conn.close()
    
    if not row:
        return {"valid": False, "reason": "invalid"}
    
    expires = datetime.datetime.strptime(row["expires_at"], "%Y-%m-%d")
    if expires <= datetime.datetime.now():
        return {"valid": False, "reason": "expired"}
    
    # Mask phone
    phone = row["phone"]
    masked = phone[:3] + "****" + phone[-4:]
    
    return {
        "valid": True,
        "tier": row["tier"],
        "expires_at": row["expires_at"],
        "phone": masked,
        "code": row["code"]
    }

def upgrade_with_vip(free_code, vip_code):
    """Use a VIP code to upgrade a free activation."""
    conn = get_db()
    
    # Check free code exists and is valid
    free = conn.execute("SELECT * FROM free_codes WHERE code = ?", (free_code,)).fetchone()
    if not free:
        conn.close()
        return {"success": False, "error": "激活码无效"}
    
    expires = datetime.datetime.strptime(free["expires_at"], "%Y-%m-%d")
    if expires <= datetime.datetime.now():
        conn.close()
        return {"success": False, "error": "激活码已过期，请先重新激活"}
    
    if free["tier"] == "vip":
        conn.close()
        return {"success": False, "error": "当前已是VIP用户"}
    
    # Check VIP code
    vip = conn.execute("SELECT * FROM vip_codes WHERE vip_code = ?", (vip_code,)).fetchone()
    if not vip:
        conn.close()
        return {"success": False, "error": "VIP激活码无效"}
    
    if vip["status"] == "used":
        conn.close()
        return {"success": False, "error": "此VIP激活码已被使用"}
    
    if vip["status"] == "revoked":
        conn.close()
        return {"success": False, "error": "此VIP激活码已被撤销"}
    
    # Perform upgrade
    new_expires = expiry_date()
    conn.execute(
        "UPDATE free_codes SET tier='vip', vip_code=?, upgraded_at=?, expires_at=? WHERE code=?",
        (vip_code, now_str(), new_expires, free_code)
    )
    conn.execute(
        "UPDATE vip_codes SET status='used', used_by_phone=?, used_by_free_code=?, used_at=? WHERE vip_code=?",
        (free["phone"], free_code, now_str(), vip_code)
    )
    conn.commit()
    _log_admin("upgrade", f"{free['phone']} upgraded to VIP with {vip_code}")
    conn.close()
    
    return {"success": True, "new_expires": new_expires, "new_tier": "vip"}

# ============== Admin functions ==============

def _log_admin(action, detail=""):
    conn = get_db()
    conn.execute("INSERT INTO admin_logs (action, detail, created_at) VALUES (?,?,?)",
                 (action, detail, now_str()))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_db()
    now = datetime.datetime.now()
    week_ago = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    soon_expire = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    
    total_free = conn.execute("SELECT COUNT(*) FROM free_codes").fetchone()[0]
    total_vip = conn.execute("SELECT COUNT(*) FROM free_codes WHERE tier='vip'").fetchone()[0]
    week_free = conn.execute(
        "SELECT COUNT(*) FROM free_codes WHERE created_at >= ?", (week_ago,)
    ).fetchone()[0]
    week_vip = conn.execute(
        "SELECT COUNT(*) FROM free_codes WHERE upgraded_at >= ?", (week_ago,)
    ).fetchone()[0]
    vip_unused = conn.execute(
        "SELECT COUNT(*) FROM vip_codes WHERE status='unused'"
    ).fetchone()[0]
    vip_used = conn.execute(
        "SELECT COUNT(*) FROM vip_codes WHERE status='used'"
    ).fetchone()[0]
    soon = conn.execute(
        "SELECT COUNT(*) FROM free_codes WHERE expires_at <= ? AND expires_at >= ?",
        (soon_expire, now.strftime("%Y-%m-%d"))
    ).fetchone()[0]
    expired = conn.execute(
        "SELECT COUNT(*) FROM free_codes WHERE expires_at < ?",
        (now.strftime("%Y-%m-%d"),)
    ).fetchone()[0]
    
    conn.close()
    return {
        "total_free": total_free, "total_vip": total_vip,
        "week_free": week_free, "week_vip": week_vip,
        "vip_unused": vip_unused, "vip_used": vip_used,
        "soon_expire": soon, "expired": expired
    }

def generate_vip_codes(count, note=""):
    conn = get_db()
    batch_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    codes = []
    for _ in range(count):
        code = _gen_vip_code()
        conn.execute(
            "INSERT INTO vip_codes (vip_code, status, generated_at, batch_id, note) VALUES (?,?,?,?,?)",
            (code, "unused", now_str(), batch_id, note)
        )
        codes.append({"vip_code": code, "status": "unused"})
    conn.commit()
    _log_admin("generate_vip", f"Generated {count} codes, batch {batch_id}")
    conn.close()
    return {"batch_id": batch_id, "codes": codes, "count": count}

def get_vip_codes(status=None, search=None, page=1, per_page=50):
    conn = get_db()
    query = "SELECT * FROM vip_codes WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (vip_code LIKE ? OR used_by_phone LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    
    rows = conn.execute(query, params).fetchall()
    count_query = "SELECT COUNT(*) FROM vip_codes WHERE 1=1"
    count_params = []
    if status:
        count_query += " AND status = ?"
        count_params.append(status)
    if search:
        count_query += " AND (vip_code LIKE ? OR used_by_phone LIKE ?)"
        count_params.extend([f"%{search}%", f"%{search}%"])
    total = conn.execute(count_query, count_params).fetchone()[0]
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "id": r["id"], "vip_code": r["vip_code"], "status": r["status"],
            "used_by_phone": r["used_by_phone"], "used_by_free_code": r["used_by_free_code"],
            "used_at": r["used_at"], "generated_at": r["generated_at"],
            "batch_id": r["batch_id"], "note": r["note"]
        })
    return {"items": result, "total": total, "page": page, "per_page": per_page}

def revoke_vip_code(vip_code):
    conn = get_db()
    row = conn.execute("SELECT * FROM vip_codes WHERE vip_code = ? AND status = 'unused'", (vip_code,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "VIP码不存在或无法撤销（仅未使用的码可撤销）"}
    conn.execute("UPDATE vip_codes SET status='revoked', revoked_at=? WHERE vip_code=?", (now_str(), vip_code))
    conn.commit()
    _log_admin("revoke_vip", f"Revoked {vip_code}")
    conn.close()
    return {"success": True}

def get_free_users(page=1, per_page=50):
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM free_codes").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM free_codes ORDER BY id DESC LIMIT ? OFFSET ?",
        (per_page, (page - 1) * per_page)
    ).fetchall()
    conn.close()
    
    now = datetime.datetime.now()
    result = []
    for r in rows:
        phone = r["phone"]
        masked = phone[:3] + "****" + phone[-4:]
        expires = datetime.datetime.strptime(r["expires_at"], "%Y-%m-%d")
        expire_status = "expired" if expires <= now else ("soon" if expires <= now + datetime.timedelta(days=30) else "active")
        result.append({
            "id": r["id"], "phone": masked, "code": r["code"], "tier": r["tier"],
            "created_at": r["created_at"], "expires_at": r["expires_at"],
            "expire_status": expire_status, "vip_code": r["vip_code"], "upgraded_at": r["upgraded_at"]
        })
    return {"items": result, "total": count, "page": page, "per_page": per_page}

def export_vip_csv():
    import io, csv
    conn = get_db()
    rows = conn.execute("SELECT * FROM vip_codes ORDER BY id DESC").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["VIP码", "状态", "使用者手机号", "使用时间", "生成时间", "批次号", "备注"])
    for r in rows:
        writer.writerow([r["vip_code"], r["status"], r["used_by_phone"] or "",
                         r["used_at"] or "", r["generated_at"], r["batch_id"] or "", r["note"] or ""])
    return output.getvalue()

def backup_db():
    import shutil
    backup_path = DB_PATH + f".backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
# ============== New: VIP assign + Free codes batch management ==============

def assign_vip_code(vip_code, phone, note=""):
    """Mark a VIP code as assigned to a specific customer phone."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM vip_codes WHERE vip_code = ? AND status = 'unused'", (vip_code,)
    ).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "VIP码不存在或已被使用/分配"}
    
    conn.execute(
        "UPDATE vip_codes SET status='assigned', used_by_phone=?, note=? WHERE vip_code=?",
        (phone, note, vip_code)
    )
    conn.commit()
    _log_admin("assign_vip", f"Assigned {vip_code} to {phone}")
    conn.close()
    return {"success": True}

def generate_free_codes_batch(count, note=""):
    """Batch generate free activation codes (for manual distribution)."""
    conn = get_db()
    batch_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    codes = []
    for _ in range(count):
        code = _gen_code("FREE")
        conn.execute(
            "INSERT INTO free_codes (phone, code, tier, created_at, expires_at) VALUES (?,?,?,?,?)",
            ("", code, "free", now_str(), expiry_date())
        )
        codes.append({"code": code, "status": "unused"})
    conn.commit()
    _log_admin("generate_free", f"Generated {count} free codes, batch {batch_id}")
    conn.close()
    return {"batch_id": batch_id, "codes": codes, "count": count}

def get_free_codes_admin(status=None, search=None, page=1, per_page=50):
    """List free codes for admin panel (with filters)."""
    conn = get_db()
    query = "SELECT * FROM free_codes WHERE 1=1"
    params = []
    if status == "used":
        query += " AND phone != ''"
    elif status == "unused":
        query += " AND phone = ''"
    elif status == "expired":
        query += " AND expires_at < ?"
        params.append(datetime.datetime.now().strftime("%Y-%m-%d"))
    elif status == "assigned":
        query += " AND phone != '' AND tier='free'"
    if search:
        query += " AND (code LIKE ? OR phone LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    
    rows = conn.execute(query, params).fetchall()
    
    count_query = "SELECT COUNT(*) FROM free_codes WHERE 1=1"
    cp = []
    if status == "used":
        count_query += " AND phone != ''"
    elif status == "unused":
        count_query += " AND phone = ''"
    elif status == "expired":
        count_query += " AND expires_at < ?"
        cp.append(datetime.datetime.now().strftime("%Y-%m-%d"))
    if search:
        count_query += " AND (code LIKE ? OR phone LIKE ?)"
        cp.extend([f"%{search}%", f"%{search}%"])
    total = conn.execute(count_query, cp).fetchone()[0]
    conn.close()
    
    now = datetime.datetime.now()
    result = []
    for r in rows:
        phone = r["phone"]
        masked = phone[:3] + "****" + phone[-4:] if phone else ""
        expires = datetime.datetime.strptime(r["expires_at"], "%Y-%m-%d")
        expire_status = "expired" if expires <= now else ("soon" if expires <= now + datetime.timedelta(days=30) else "active")
        codestatus = "used" if phone else "unused"
        result.append({
            "id": r["id"], "code": r["code"], "phone": masked,
            "tier": r["tier"], "status": codestatus,
            "created_at": r["created_at"], "expires_at": r["expires_at"],
            "expire_status": expire_status, "vip_code": r["vip_code"], "upgraded_at": r["upgraded_at"]
        })
    return {"items": result, "total": total, "page": page, "per_page": per_page}

def assign_free_code(code, phone):
    """Assign a pre-generated free code to a phone number."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM free_codes WHERE code = ? AND phone = ''", (code,)
    ).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "激活码不存在或已被使用"}
    
    # Check phone not already in system
    existing = conn.execute("SELECT * FROM free_codes WHERE phone = ?", (phone,)).fetchone()
    if existing:
        now = datetime.datetime.now()
        expires = datetime.datetime.strptime(existing["expires_at"], "%Y-%m-%d")
        if expires > now:
            conn.close()
            return {"success": False, "error": f"该手机号已有激活码: {existing['code']}"}
    
    conn.execute("UPDATE free_codes SET phone=? WHERE code=?", (phone, code))
    conn.commit()
    _log_admin("assign_free", f"Assigned {code} to {phone}")
    conn.close()
    return {"success": True, "code": code, "phone": phone[:3] + "****" + phone[-4:]}

def revoke_free_code(code):
    """Revoke an unused free code."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM free_codes WHERE code = ? AND phone = ''", (code,)
    ).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "激活码不存在或已被使用，无法撤销"}
    conn.execute("DELETE FROM free_codes WHERE code = ?", (code,))
    conn.commit()
    _log_admin("revoke_free", f"Revoked free code {code}")
    conn.close()
    return {"success": True}
