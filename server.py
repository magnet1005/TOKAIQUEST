import sqlite3
import os
import ai
from groq import Client, Groq
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DB_PATH = "Bunseki.db"  # Render上でのパス

# SQLite データベースを作成（もし存在しない場合）
def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # `bunseki` テーブル作成
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bunseki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                yougo TEXT NOT NULL,
                seigo INTEGER NOT NULL
            )
        """)
        
        # `tokai` テーブル作成（必要なら）
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
        print("✅ `Bunseki.db` を作成しました！")

# SQLite データベースに接続
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
        response = ai.main(query)
        return jsonify({"response": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        model = 'llama3-8b-8192'

        groq_api_key = os.getenv('GROQ_API_KEY')
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY が設定されていません")

        client = Groq(api_key=groq_api_key)

        def get_top_bottom(query):
            conn = connect_db()
            cur = conn.cursor()
            z = 1.96  # Wilson スコア用のZ値
            cur.execute(query, (z, z, z, z, z, z, z, z, z))
            result = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            return result

        top_yougo = get_top_bottom("""
        -- SQLクエリはそのまま
        """)

        bottom_yougo = get_top_bottom("""
        -- SQLクエリはそのまま
        """)

        # 総データ数取得
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT yougo) FROM bunseki;")
        len_yougo = cur.fetchone()[0]
        cur.close()
        conn.close()

        # AIにデータを送信
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
    init_db()  # 起動時にデータベースを初期化
    app.run(host="0.0.0.0", port=10000)
