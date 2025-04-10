import os
from binance.client import Client

# 環境変数からAPIキーを取得
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# クライアントの初期化
client = Client(api_key, api_secret)
