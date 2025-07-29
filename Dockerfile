# ベースイメージには Debian Bullseye 上の Python 3.11 スリム版を使用
FROM python:3.12-slim-bullseye

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係を先にコピー・インストールしてキャッシュ活用
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# コンテナ内の 3000 番ポートを公開
EXPOSE 3000

# コンテナ起動時にサーバを立ち上げ
CMD ["python", "server.py"]