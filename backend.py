from flask import Flask, request, Response
import sqlite3
import json
import os

app = Flask(__name__)

DB = "ogretmen.db"

def query(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.route("/isler-ogretmen")
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

    data = query(sql, params)

    return Response(
        json.dumps({
            "status": "success",
            "count": len(data),
            "data": data
        }, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

@app.route("/")
def home():
    return Response(
        json.dumps({
            "status": "ok",
            "records": 313745
        }, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

# 🔥 BURASI ÇOK ÖNEMLİ (Render için)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
