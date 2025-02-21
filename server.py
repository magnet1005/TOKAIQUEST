import sqlite3
import os
import ai
from groq import Client, Groq
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DB_PATH = "Bunseki.db"  # データベースを統一


# SQLite データベースを作成（もし存在しない場合）
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


# SQLite データベースに接続
def connect_db():
    return sqlite3.connect(DB_PATH)

@app.route("/add", methods=["POST"])
def add_yougo():
    try:
        init_db()
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
        # JSONレスポンスとUTF-8エンコーディングヘッダーを設定
        return jsonify({"response": response}), 200, {"Content-Type": "application/json; charset=utf-8"}
    except Exception as e:
        # エラーレスポンスにもUTF-8エンコーディングを設定
        return jsonify({"error": str(e)}), 500, {"Content-Type": "application/json; charset=utf-8"}

## top関数
def top():
  filepath = "Bunseki.db"
  conn = sqlite3.connect(filepath)
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
  ) AS top_yougo;
  """, (z, z, z, z, z, z, z, z, z))

  top_yougo = [row[0] for row in cur.fetchall()]

  cur.close()
  conn.close()

  return top_yougo

## bottom関数
def bottom():
  filepath = "Bunseki.db"
  conn = sqlite3.connect(filepath)
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
  ) AS top_yougo;
  """, (z, z, z, z, z, z, z, z, z))

  bottom_yougo = [row[0] for row in cur.fetchall()]

  cur.close()
  conn.close()

  return bottom_yougo

## len_yougo関数
def len_yougo():
  filepath = "Bunseki.db"
  conn = sqlite3.connect(filepath)
  cur = conn.cursor()

  z = 1.96
  cur.execute("""
  SELECT COUNT(DISTINCT yougo) FROM bunseki;
  """)

  len_yougo = cur.fetchall()

  cur.close()
  conn.close()

  return len_yougo

@app.route("/analyze", methods=["GET"])
def output(client, model, top_yougo, bottom_yougo, len_yougo):

  # システムプロンプトの設定
  system_prompt = '''
  あなたは全商情報処理検定の学習アドバイザーです。  必ず日本語で丁寧に回答してください。装飾はつけないでください。
  '''

  # 事前に学習されたモデルを使用してユーザーの質問に対する応答を生成
  chat_completion = client.chat.completions.create(
      messages = [
          {
              "role": "system",
              "content":  system_prompt
          },
          {
              "role": "user",
              "content": """以下の結果をもとに、個々に寄り添ったアドバイスを【テンプレート】に沿って日本語にて行ってください。

                            - 正答率上位のものは、「できている点」を具体的に褒め、さらに伸ばせる勉強法を提案してください。また、結果からどの分野が得意であるかも教えてください。
                            - 正答率下位のものは、「努力している点」に触れたうえで、どのように改善すればよいかを前向きに提案してください。  また、結果からどの分野が苦手であるかも教えてください。
                            - 学習者の向上心を高めるような励ましの言葉を入れてください。
                            - 装飾をつけずに簡潔に出力してください。

                            正答率上位3位：{""" + top_yougo + """}
                            正答率下位3位：{""" + bottom_yougo + """}
                            回答用語数：""" + len_yougo + """

                            【テンプレート】
                            ---正答率上位3位---
                            [yougo, yougo, yougo]

                            褒めるような文章

                            ---正答率下位3位---
                            [yougo, yougo, yougo]

                            正答率を改善するための勉強法

                            """,
          }
      ],
      # modelはllama3-8b-8192
      model = model,
      # 回答のばらつき、使わないと英語出てくる
      temperature = 0.3
  )

  # 応答を抽出
  response = chat_completion.choices[0].message.content

  return response

##### main関数
def main():
  # Groqのモデル
  model = 'llama3-8b-8192'

  # GroqのAPIキーを設定
  os.environ["GROQ_API_KEY"] = "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"
  groq_api_key = os.getenv('GROQ_API_KEY')

  client = Groq(
      api_key=groq_api_key
  )

  response = output(client, model, ", ".join(top), ", ".join(bottom),", ".join(len_yougo))
        
  return jsonify({"response": chat_completion.choices[0].message.content})

except Exception as e:
return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)
