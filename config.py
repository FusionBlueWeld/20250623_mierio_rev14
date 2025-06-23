import os

# ユーザーデータ用のベースディレクトリ（このファイルがあるディレクトリからの相対パス）
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_data')

# CSVファイル用のアップロードフォルダ
UPLOAD_FOLDER = os.path.join(USER_DATA_DIR, 'uploads')

# JSON設定ファイル用の設定フォルダ
SETTINGS_FOLDER = os.path.join(USER_DATA_DIR, 'settings')
JSON_SUBFOLDER = os.path.join(SETTINGS_FOLDER, 'json')

# meshフォルダ
MESH_FOLDER = os.path.join(USER_DATA_DIR, 'mesh')

# Flaskセッション用の秘密鍵（重要：本番環境では、強力でランダムな値に変更してください）
SECRET_KEY = 'super_secret_key_for_mierio_app'

# 各ディレクトリが存在しない場合は作成する
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(JSON_SUBFOLDER, exist_ok=True)
