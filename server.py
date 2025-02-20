import sqlite3
import os
from groq import Groq
from flask import Flask, request, jsonify , make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DB_PATH = "Bunseki.db"  # データベースのパス

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response
    
# SQLite データベースを初期化
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bunseki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            yougo TEXT NOT NULL,
            seigo INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tokai (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            yougo TEXT NOT NULL,
            mondai TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ `Bunseki.db` が初期化されました！")

# SQLite データベース接続
def connect_db():
    return sqlite3.connect(DB_PATH)

@app.route("/add", methods=["POST"])
def add_yougo():
    try:
        data = request.get_json()
        yougo = data.get("yougo")
        seigo = int(data.get("seigo"))

        conn = connect_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO bunseki (yougo, seigo) VALUES (?, ?)', (yougo, seigo))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({"message": "データを追加しました！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 正答率上位3つ
def top():
    conn = connect_db()
    cur = conn.cursor()
    z = 1.96
    cur.execute("""
    WITH score_data AS (
        SELECT
            yougo,
            SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) AS correct_answers,
            COUNT(seigo) AS total_attempts,
            CASE
                WHEN COUNT(seigo) = 0 THEN 0
                ELSE SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(seigo)
            END AS p
        FROM bunseki
        GROUP BY yougo
    )
    SELECT yougo FROM (
        SELECT
            yougo,
            (p + (? * ?) / (2 * total_attempts)) / (1 + (? * ?) / total_attempts) - 
            (? * SQRT((p * (1 - p) / total_attempts) + (? * ?) / (4 * total_attempts * total_attempts))) / 
            (1 + (? * ?) / total_attempts) AS wilson_score
        FROM score_data
        ORDER BY wilson_score DESC
        LIMIT 3
    );
    """, (z, z, z, z, z, z, z, z, z))
    
    top_words = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return top_words

# 正答率下位3つ
def bottom():
    conn = connect_db()
    cur = conn.cursor()
    z = 1.96
    cur.execute("""
    WITH score_data AS (
        SELECT
            yougo,
            SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) AS correct_answers,
            COUNT(seigo) AS total_attempts,
            CASE
                WHEN COUNT(seigo) = 0 THEN 0
                ELSE SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(seigo)
            END AS p
        FROM bunseki
        GROUP BY yougo
    )
    SELECT yougo FROM (
        SELECT
            yougo,
            (p + (? * ?) / (2 * total_attempts)) / (1 + (? * ?) / total_attempts) - 
            (? * SQRT((p * (1 - p) / total_attempts) + (? * ?) / (4 * total_attempts * total_attempts))) / 
            (1 + (? * ?) / total_attempts) AS wilson_score
        FROM score_data
        ORDER BY wilson_score
        LIMIT 3
    );
    """, (z, z, z, z, z, z, z, z, z))
    
    bottom_words = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return bottom_words

# 用語数を取得
def len_yougo():
    filepath = "Bunseki.db"
    conn = sqlite3.connect(filepath)
    cur = conn.cursor()

    cur.execute("""
    SELECT COUNT(DISTINCT yougo) FROM bunseki;
    """)
    
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return result

@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        model = "llama3-8b-8192"
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            return jsonify({"error": "GROQ_API_KEY が設定されていません"}), 500

        client = Groq(api_key=groq_api_key)

        top_words = ", ".join(top()) or "なし"
        bottom_words = ", ".join(bottom()) or "なし"
        total_yougo = len_yougo() or "不明"

        system_prompt = """ あなたは必ず日本語で回答する全商情報処理検定の学習アドバイザーです。 必ず日本語で丁寧に回答してください。必ず日本語で装飾はつけないでください。 """

        prompt = f"""以下の結果をもとに、個々に寄り添ったアドバイスを必ず日本語で【テンプレート】に沿って日本語にて行ってください。

        正答率上位3位：{top_words}
        正答率下位3位：{bottom_words}
        回答用語数：{total_yougo}

        【テンプレート】
        ---正答率上位3位---
        [word,word,word]

        褒めるような文章

        ---正答率下位3位---
        [word,word,word]

        正答率を改善するための勉強法"""

        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model=model,
            temperature=0.3,
        )
        
        response = chat_completion.choices[0].message.content
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)
