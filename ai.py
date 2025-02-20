import pandas as pd
import os
import sqlite3
from groq import Client, Groq

# データベースのパス
DB_PATH = "Bunseki.db"
# GoogleスプレッドシートのURL
sheet_url = 'https://docs.google.com/spreadsheets/d/1xtnpVmvv4NOU5-4KrA2xWWtnSuZFYfMI/export?format=csv'

# SQLite データベースを初期化
def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # テーブルの作成
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tokai (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mondai TEXT NOT NULL,
                yougo TEXT NOT NULL
            )
        """)

        # Googleスプレッドシートからデータを取得して挿入
        dates = pd.read_csv(sheet_url).values.tolist()
        cur.executemany("INSERT INTO tokai (mondai, yougo) VALUES (?, ?)", dates)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ データベースを作成しました！")

# search 関数
def search(user_question):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    document = pd.read_sql_query("SELECT mondai FROM tokai WHERE yougo = ?", conn, params=[user_question])
    cur.close()
    conn.close()
    
    print(document)
    return document

# output 関数
def output(client, model, user_question, document):
    system_prompt = '''
    あなたは優秀なAIアシスタントです。必ず日本語で丁寧に回答してください。装飾はつけないでください。解説のみを表示してください。
    '''

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Question: 参考文章を参考に必ず日本語で次の用語を解説してください。また、解説のみを回答してください。\n\n{user_question}\n参考文章：{document}"},
        ],
        model=model,
        temperature=0.3
    )

    response = chat_completion.choices[0].message.content
    return response

# main 関数
def main(user_question):
    init_db()  # データベース初期化

    # Groq のモデル設定
    model = 'llama3-8b-8192'

    # 環境変数から API キーを取得 (環境変数は Render 側で設定する)
    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY が設定されていません")

    client = Groq(api_key=groq_api_key)

    document = search(user_question)

    # Groq に送信
    response = output(client, model, user_question, str(document))
    print("Content-Type: text/plain\n")
    print(response)

    return response
