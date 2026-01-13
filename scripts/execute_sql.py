#!/usr/bin/env python3
"""
SQLスクリプトを実行するユーティリティ
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hubspot.config import Config
import aiomysql
import asyncio

async def execute_sql_file(sql_file_path: str):
    """SQLファイルを実行"""
    try:
        config = Config.get_mysql_config()
        
        # データベース接続
        conn = await aiomysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            db=config["db"],
            charset=config["charset"]
        )
        
        try:
            # SQLファイルを読み込み
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # コメント行を除外して実行可能なSQLのみを抽出
            sql_statements = []
            for line in sql_content.split('\n'):
                line = line.strip()
                # 空行やコメント行をスキップ
                if line and not line.startswith('--'):
                    sql_statements.append(line)
            
            # SQLを結合（セミコロンで区切られたステートメントとして処理）
            full_sql = '\n'.join(sql_statements)
            
            # セミコロンで分割して各ステートメントを実行
            statements = [s.strip() for s in full_sql.split(';') if s.strip()]
            
            async with conn.cursor() as cursor:
                for statement in statements:
                    if statement:
                        print(f"実行中: {statement[:100]}...")
                        await cursor.execute(statement)
                
                await conn.commit()
                print("SQLスクリプトの実行が完了しました。")
        
        finally:
            conn.close()
    
    except Exception as e:
        print(f"エラー: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python execute_sql.py <sql_file_path>", file=sys.stderr)
        sys.exit(1)
    
    sql_file_path = sys.argv[1]
    if not os.path.exists(sql_file_path):
        print(f"エラー: SQLファイルが見つかりません: {sql_file_path}", file=sys.stderr)
        sys.exit(1)
    
    asyncio.run(execute_sql_file(sql_file_path))



