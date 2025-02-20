# pandasライブラリをインポート
import pandas as pd
import os
from groq import Client, Groq
from re import search
import sqlite3

#### search関数
def search(user_question):
    conn = sqlite3.connect('toukai.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    document = pd.read_sql_query("SELECT mondai FROM tokai WHERE yougo = ?" , conn,params=[user_question])
    cur.close()
    conn.close()
    print(document)
    return(document)

##### output関数：Groqで出力
def output(client, model, user_question, document):

    # システムプロンプトの設定
    system_prompt = '''
    あなたは優秀なAIアシスタントです。必ず日本語で丁寧に回答してください。装飾はつけないでください。解説のみを表示してください。
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
                "content": "User Question: 参考文章を参考に必ず日本語で次の用語を解説してください。また、解説のみを回答してください。\n\n" + user_question + '\n参考文章：' + document,
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
def main(user_question):

    #dbの作成

    # Groqのモデル
    model = 'llama3-8b-8192'

    # GroqのAPIキーを設定
    os.environ["GROQ_API_KEY"] = "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"
    groq_api_key = os.getenv('GROQ_API_KEY')

    client = Groq(
        api_key=groq_api_key
    )

    document = search(user_question)

    #Groqにて出力
    document = str(document)
    response = output(client, model, user_question, document)
    print("Content-Type: text/plain\n")
    print(response)

    return response