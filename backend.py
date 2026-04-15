from flask import Flask, request, Response, jsonify
import sqlite3
import json
import os
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- UTF-8 ve temizlik yardımcıları ----------
def clean_text(text):
    """Metindeki kontrol karakterlerini (\\n, \\r, \\t) temizler ve strip yapar"""
    if text is None:
        return ""
    if isinstance(text, str):
        # \\n, \\r, \\t ve diğer boşlukları temizle
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return text.strip()
    return str(text)

def make_utf8_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.text_factory = bytes  # Önce bytes al, sonra utf-8 decode et
    conn.execute("PRAGMA encoding = 'UTF-8'")
    return conn

def row_to_dict(row, description):
    """Satırı sözlüğe çevirir, tüm metin alanlarını temizler"""
    result = {}
    for i, col in enumerate(description):
        val = row[i]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        result[col[0]] = clean_text(val)
    return result

# ======================== 1. IYS (TEK DOSYA: iys.db) ========================
IYS_DB = os.path.join(BASE_DIR, "iys.db")

def iys_query(where, params):
    result = []
    if os.path.exists(IYS_DB):
        try:
            conn = make_utf8_connection(IYS_DB)
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM data WHERE 1=1 {where}", params)
            rows = cur.fetchall()
            desc = cur.description
            for row in rows:
                result.append(row_to_dict(row, desc))
            conn.close()
        except Exception as e:
            print(f"IYS DB hatası: {e}")
    return result

@app.route("/search", methods=["GET"])
def iys_search():
    name = request.args.get("name")
    phone = request.args.get("phone")
    city = request.args.get("city")
    where = ""
    params = []
    if name:
        where += " AND (name LIKE ? OR fullname LIKE ?)"
        params += [f"%{name}%", f"%{name}%"]
    if phone:
        where += " AND phone LIKE ?"
        params.append(f"%{phone}%")
    if city:
        where += " AND city LIKE ?"
        params.append(f"%{city}%")
    result = iys_query(where, params)
    return Response(json.dumps({"count": len(result), "data": result}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== 2. VERGİ (vergi.db) - DÜZELTİLMİŞ ========================
VERGI_DB = os.path.join(BASE_DIR, "vergi.db")

def get_vergi_connection():
    conn = sqlite3.connect(VERGI_DB)
    conn.text_factory = bytes
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA encoding = 'UTF-8'")
    return conn

def clean_sql(column):
    return f"REPLACE(REPLACE(REPLACE({column}, char(10), ' '), char(13), ' '), '''', '')"

def clean_vergi_row(row):
    """Row nesnesini temiz sözlüğe çevirir"""
    d = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        d[key] = clean_text(val)
    return d

@app.route("/vergi-adi", methods=["GET"])
def vergi_adi():
    ad = request.args.get("adi", "").strip()
    soyad = request.args.get("soyadi", "").strip()
    if not ad and not soyad:
        return jsonify({"hata": "Ad veya soyad giriniz"}), 400
    
    conn = get_vergi_connection()
    cur = conn.cursor()
    
    if ad and soyad:
        sql = f"""SELECT * FROM kisiler WHERE 
                  ({clean_sql('fullname')} LIKE ?) AND 
                  ({clean_sql('fullname')} LIKE ?) LIMIT 50"""
        params = (f"%{ad}%", f"%{soyad}%")
    else:
        aranan = ad if ad else soyad
        sql = f"SELECT * FROM kisiler WHERE {clean_sql('fullname')} LIKE ? LIMIT 50"
        params = (f"%{aranan}%",)
    
    cur.execute(sql, params)
    rows = [clean_vergi_row(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"status": "success", "count": len(rows), "data": rows})

@app.route("/vergi-tc", methods=["GET"])
def vergi_tc():
    tc = request.args.get("tc", "").strip()
    conn = get_vergi_connection()
    cur = conn.cursor()
    sql = f"SELECT * FROM kisiler WHERE {clean_sql('identity')} LIKE ? LIMIT 50"
    cur.execute(sql, (f"%{tc}%",))
    rows = [clean_vergi_row(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"status": "success", "count": len(rows), "data": rows})

# ======================== 3. ÖĞRETMEN (ogretmen.db) ========================
OGRETMEN_DB = os.path.join(BASE_DIR, "ogretmen.db")

def clean_ogretmen_row(row):
    d = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        d[key] = clean_text(val)
    return d

@app.route("/isler-ogretmen", methods=["GET"])
def isler_ogretmen():
    ad = request.args.get("ad", "").strip()
    soyad = request.args.get("soyad", "").strip()
    il = request.args.get("il", "").strip()
    ilce = request.args.get("ilce", "").strip()
    sql = "SELECT * FROM kisiler WHERE 1=1"
    params = []
    if ad:
        sql += " AND fullname LIKE '%' || ? || '%' COLLATE NOCASE"
        params.append(ad)
    if soyad:
        sql += " AND fullname LIKE '%' || ? || '%' COLLATE NOCASE"
        params.append(soyad)
    if il:
        sql += " AND il LIKE '%' || ? || '%' COLLATE NOCASE"
        params.append(il)
    if ilce:
        sql += " AND ilce LIKE '%' || ? || '%' COLLATE NOCASE"
        params.append(ilce)
    sql += " LIMIT 50"
    conn = make_utf8_connection(OGRETMEN_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [clean_ogretmen_row(r) for r in cur.fetchall()]
    conn.close()
    return Response(json.dumps({"status": "success", "count": len(rows), "data": rows}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== 4. SERİNO (serino.db) ========================
SERINO_DB = os.path.join(BASE_DIR, "serino.db")

def clean_serino_row(row):
    d = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        d[key] = clean_text(val)
    return d

@app.route("/vergi", methods=["GET"])
def serino_vergi():
    tc = request.args.get("tc", "").strip()
    no = request.args.get("no", "").strip()
    ad = request.args.get("ad", "").strip()
    soyad = request.args.get("soyad", "").strip()
    conn = make_utf8_connection(SERINO_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT * FROM serino WHERE 1=1"
    params = []
    if tc:
        sql += " AND TC = ?"
        params.append(tc)
    if no:
        sql += " AND SERINO LIKE ?"
        params.append(f"%{no}%")
    if ad:
        sql += " AND ADI LIKE ?"
        params.append(f"%{ad}%")
    if soyad:
        sql += " AND SOYADI LIKE ?"
        params.append(f"%{soyad}%")
    sql += " LIMIT 50"
    cur.execute(sql, params)
    rows = [clean_serino_row(r) for r in cur.fetchall()]
    conn.close()
    return Response(json.dumps({"status": "success", "count": len(rows), "data": rows}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== 5. BURSA SİCİL (bursa.db) ========================
BURSA_DB = os.path.join(BASE_DIR, "bursa.db")

def clean_bursa_row(row):
    d = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        d[key] = clean_text(val)
    return d

@app.route("/bursasicil", methods=["GET"])
def bursasicil():
    tc = request.args.get("tc", "").strip()
    ad = request.args.get("ad", "").strip()
    soyad = request.args.get("soyad", "").strip()
    city = request.args.get("city", "").strip()
    sql = "SELECT * FROM data WHERE 1=1"
    params = []
    if tc:
        sql += " AND AVUKAT_TC_KIMLIK_NO LIKE ?"
        params.append(f"%{tc}%")
    if ad:
        sql += " AND KISI_ADI LIKE ?"
        params.append(f"%{ad}%")
    if soyad:
        sql += " AND KISI_SOYAD LIKE ?"
        params.append(f"%{soyad}%")
    if city:
        sql += " AND KURUM_ADI LIKE ?"
        params.append(f"%{city}%")
    sql += " LIMIT 100"
    conn = make_utf8_connection(BURSA_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [clean_bursa_row(r) for r in cur.fetchall()]
    conn.close()
    return Response(json.dumps({"status": "success", "count": len(rows), "data": rows}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== 6. PAPARA (70kpapara.sql) ========================
PAPARA_SQL = os.path.join(BASE_DIR, "70kpapara.sql")

def load_papara_data():
    data = []
    if not os.path.exists(PAPARA_SQL):
        return data
    with open(PAPARA_SQL, "r", encoding="utf-8", errors="ignore") as f:
        sql = f.read()
    match = re.search(r"INSERT INTO.*?VALUES\s*(.*?);", sql, re.S)
    if not match:
        return data
    values = match.group(1)
    rows = re.findall(r"\((.*?)\)", values, re.S)
    for r in rows:
        cols = []
        current = ""
        in_q = False
        for ch in r:
            if ch == "'" and not in_q:
                in_q = True
            elif ch == "'" and in_q:
                in_q = False
            if ch == "," and not in_q:
                cols.append(current.strip().strip("'"))
                current = ""
            else:
                current += ch
        cols.append(current.strip().strip("'"))
        if len(cols) >= 3:
            data.append({
                "id": clean_text(cols[0]),
                "paparano": clean_text(cols[1]),
                "adsoyad": clean_text(cols[2])
            })
    return data

PAPARA_DATA = load_papara_data()

@app.route("/papara", methods=["GET"])
def papara():
    no = request.args.get("no")
    ad = request.args.get("ad")
    soyad = request.args.get("soyad")
    adsoyad = request.args.get("adsoyad")
    result = PAPARA_DATA
    if no:
        result = [x for x in result if no in str(x["paparano"])]
    if ad:
        result = [x for x in result if ad.lower() in x["adsoyad"].lower()]
    if soyad:
        result = [x for x in result if soyad.lower() in x["adsoyad"].lower()]
    if adsoyad:
        result = [x for x in result if adsoyad.lower() in x["adsoyad"].lower()]
    return Response(json.dumps({"count": len(result), "data": result[:100]}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== 7. ECZANE (eczane.sql) ========================
ECZANE_SQL = os.path.join(BASE_DIR, "eczane.sql")

def load_eczane_data():
    data = []
    if not os.path.exists(ECZANE_SQL):
        return data
    with open(ECZANE_SQL, "r", encoding="utf-8", errors="ignore") as f:
        sql = f.read()
    inserts = re.findall(r"INSERT INTO mytable.*?VALUES\s*\((.*?)\);", sql)
    for row in inserts:
        parts = []
        current = ""
        in_q = False
        for ch in row:
            if ch == "'" and not in_q:
                in_q = True
            elif ch == "'" and in_q:
                in_q = False
            if ch == "," and not in_q:
                parts.append(current.strip().strip("'"))
                current = ""
            else:
                current += ch
        parts.append(current.strip().strip("'"))
        if len(parts) >= 4:
            data.append({
                "eczane": clean_text(parts[0]),
                "ad": clean_text(parts[1]),
                "adres": clean_text(parts[2]),
                "telefon": clean_text(parts[3])
            })
    return data

ECZANE_DATA = load_eczane_data()

@app.route("/eczane", methods=["GET"])
def eczane():
    ad = request.args.get("ad")
    ilce = request.args.get("ilce")
    adres = request.args.get("adres")
    result = ECZANE_DATA
    if ad:
        result = [x for x in result if ad.lower() in x["ad"].lower()]
    if ilce:
        result = [x for x in result if ilce.lower() in x["adres"].lower()]
    if adres:
        result = [x for x in result if adres.lower() in x["adres"].lower()]
    return Response(json.dumps({"count": len(result), "data": result[:100]}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== 8. ÜNİVERSİTE (universite.db) ========================
UNIVERSITE_DB = os.path.join(BASE_DIR, "universite.db")

def db_universite():
    conn = make_utf8_connection(UNIVERSITE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def clean_universite_row(row):
    d = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        d[key] = clean_text(val)
    return d

def to_json(data):
    return Response(json.dumps(data, ensure_ascii=False), content_type="application/json; charset=utf-8")

@app.route("/universite/arama", methods=["GET"])
def universite_arama():
    q = request.args.get("q", "")
    conn = db_universite()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data WHERE ad LIKE ? OR soyad LIKE ? OR universite LIKE ? OR bolum LIKE ?", (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
    rows = [clean_universite_row(r) for r in cur.fetchall()]
    conn.close()
    return to_json(rows)

@app.route("/universite/ad", methods=["GET"])
def universite_ad():
    q = request.args.get("ad", "")
    conn = db_universite()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data WHERE ad LIKE ?", (f"%{q}%",))
    rows = [clean_universite_row(r) for r in cur.fetchall()]
    conn.close()
    return to_json(rows)

@app.route("/universite/soyad", methods=["GET"])
def universite_soyad():
    q = request.args.get("soyad", "")
    conn = db_universite()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data WHERE soyad LIKE ?", (f"%{q}%",))
    rows = [clean_universite_row(r) for r in cur.fetchall()]
    conn.close()
    return to_json(rows)

@app.route("/universite/universite", methods=["GET"])
def universite_uni():
    q = request.args.get("universite", "")
    conn = db_universite()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data WHERE universite LIKE ?", (f"%{q}%",))
    rows = [clean_universite_row(r) for r in cur.fetchall()]
    conn.close()
    return to_json(rows)

@app.route("/universite/bolum", methods=["GET"])
def universite_bolum():
    q = request.args.get("bolum", "")
    conn = db_universite()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data WHERE bolum LIKE ?", (f"%{q}%",))
    rows = [clean_universite_row(r) for r in cur.fetchall()]
    conn.close()
    return to_json(rows)

@app.route("/universite/kisi", methods=["GET"])
def universite_kisi():
    ad = request.args.get("ad", "")
    soyad = request.args.get("soyad", "")
    conn = db_universite()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data WHERE ad LIKE ? AND soyad LIKE ?", (f"%{ad}%", f"%{soyad}%"))
    rows = [clean_universite_row(r) for r in cur.fetchall()]
    conn.close()
    return to_json(rows)

@app.route("/universite", methods=["GET"])
def universite_home():
    return to_json({"durum": "Üniversite API çalışıyor 🚀", "utf8": True})

# ======================== 9. PLAKA (plaka.db) ========================
PLAKA_DB = os.path.join(BASE_DIR, "plaka.db")

def clean_plaka_row(row):
    d = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        d[key] = clean_text(val)
    return d

@app.route("/plaka", methods=["GET"])
def plaka():
    plaka = request.args.get("plaka", "").strip()
    if not plaka:
        return jsonify({"hata": "Plaka giriniz"}), 400
    conn = make_utf8_connection(PLAKA_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM plakalar WHERE plaka LIKE ? LIMIT 50", (f"%{plaka}%",))
    rows = [clean_plaka_row(r) for r in cur.fetchall()]
    conn.close()
    return Response(json.dumps({"status": "success", "count": len(rows), "data": rows}, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== ANA SAYFA ========================
@app.route("/")
def home():
    return Response(json.dumps({
        "status": "ok",
        "message": "Tüm API'ler UTF-8 destekli ve temiz veri ile çalışıyor",
        "endpoints": {
            "IYS": "/search?name=&phone=&city=",
            "Vergi Ad/Soyad": "/vergi-adi?adi=&soyadi=",
            "Vergi TC": "/vergi-tc?tc=",
            "Öğretmen": "/isler-ogretmen?ad=&soyad=&il=&ilce=",
            "Serino/Vergi No": "/vergi?tc=&no=&ad=&soyad=",
            "Bursa Sicil": "/bursasicil?tc=&ad=&soyad=&city=",
            "Papara": "/papara?no=&ad=&soyad=&adsoyad=",
            "Eczane": "/eczane?ad=&ilce=&adres=",
            "Üniversite Arama": "/universite/arama?q=",
            "Üniversite Ad": "/universite/ad?ad=",
            "Üniversite Soyad": "/universite/soyad?soyad=",
            "Üniversite Üniversite": "/universite/universite?universite=",
            "Üniversite Bölüm": "/universite/bolum?bolum=",
            "Üniversite Kişi": "/universite/kisi?ad=&soyad=",
            "Üniversite Ana": "/universite",
            "Plaka": "/plaka?plaka="
        }
    }, ensure_ascii=False), content_type="application/json; charset=utf-8")

# ======================== RENDER ÇALIŞTIRMA ========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
