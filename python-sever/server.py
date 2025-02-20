import sqlite3
import os
import ai
from groq import Client, Groq
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# SQLite データベースに接続
def connect_db():
    filepath = "Bunseki.db"
    return sqlite3.connect(filepath)

@app.route("/add", methods=["POST"])
def add_yougo():
    try:
        data = request.get_json()
        yougo = data.get("yougo")
        seigo = int(data.get("seigo"))
        
        conn = connect_db()
        cur = conn.cursor()
        
        # データを挿入
        cur.execute('INSERT INTO bunseki (yougo, seigo) VALUES (?, ?)', (yougo, seigo))
        conn.commit()

        cur.close()
        conn.close()
        
        return jsonify({"message": "データを追加しました！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    try:
        query = request.args.get('query', '')
        return ai.main(query)
    except Exception as e:
        return str(e)

@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        model = 'llama3-8b-8192'
        os.environ["GROQ_API_KEY"] = "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"
        groq_api_key = os.getenv('GROQ_API_KEY')
        client = Groq(api_key=groq_api_key)
        
        def get_top_bottom(query):
            conn = connect_db()
            cur = conn.cursor()
            z = 1.96
            cur.execute(query, (z, z, z, z, z, z, z, z, z))
            result = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            return result
        
        top_yougo = get_top_bottom("""
        WITH score_data AS (
            SELECT yougo, SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) AS correct_answers,
            COUNT(seigo) AS total_attempts,
            CASE WHEN COUNT(seigo) = 0 THEN 0
            ELSE SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(seigo) END AS p
            FROM bunseki GROUP BY yougo
        )
        SELECT yougo FROM (
            SELECT yougo, (p + (? * ?) / (2 * total_attempts)) / (1 + (? * ?) / total_attempts) -
            (? * SQRT((p * (1 - p) / total_attempts) + (? * ?) / (4 * total_attempts * total_attempts))) /
            (1 + (? * ?) / total_attempts) AS wilson_score
            FROM score_data ORDER BY wilson_score DESC LIMIT 3
        ) AS top_yougo;
        """)
        
        bottom_yougo = get_top_bottom("""
        WITH score_data AS (
            SELECT yougo, SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) AS correct_answers,
            COUNT(seigo) AS total_attempts,
            CASE WHEN COUNT(seigo) = 0 THEN 0
            ELSE SUM(CASE WHEN seigo = 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(seigo) END AS p
            FROM bunseki GROUP BY yougo
        )
        SELECT yougo FROM (
            SELECT yougo, (p + (? * ?) / (2 * total_attempts)) / (1 + (? * ?) / total_attempts) -
            (? * SQRT((p * (1 - p) / total_attempts) + (? * ?) / (4 * total_attempts * total_attempts))) /
            (1 + (? * ?) / total_attempts) AS wilson_score
            FROM score_data ORDER BY wilson_score LIMIT 3
        ) AS bottom_yougo;
        """)
        
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT yougo) FROM bunseki;")
        len_yougo = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        system_prompt = """あなたは全商情報処理検定の学習アドバイザーです。必ず日本語で丁寧に回答してください。"""
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"正答率上位3位: {top_yougo}\n正答率下位3位: {bottom_yougo}\n回答用語数: {len_yougo}"}
            ],
            model=model,
            temperature=0.3
        )
        
        return jsonify({"response": chat_completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
