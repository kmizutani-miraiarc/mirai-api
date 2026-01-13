#!/usr/bin/env python3
"""
コンタクトフェーズ集計テーブルのbuy_phaseとsell_phaseをNULL許可に変更するスクリプト
"""

import asyncio
import sys
import os
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import get_db_pool
import aiomysql

async def apply_schema_change():
    """スキーマ変更を適用"""
    db_pool = await get_db_pool()
    if not db_pool:
        print("エラー: データベース接続プールの取得に失敗しました。")
        return False
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                print("スキーマ変更を開始します...")
                
                # 既存のユニーク制約を削除
                print("1. 既存のユニーク制約を削除中...")
                try:
                    await cursor.execute("ALTER TABLE contact_phase_summary DROP INDEX uk_aggregation_owner_phases")
                    print("   ✓ ユニーク制約を削除しました")
                except Exception as e:
                    if "Unknown key name" in str(e):
                        print("   ⚠ ユニーク制約が存在しません（スキップ）")
                    else:
                        raise
                
                # buy_phaseをNULL許可に変更
                print("2. buy_phaseをNULL許可に変更中...")
                await cursor.execute("""
                    ALTER TABLE contact_phase_summary
                    MODIFY COLUMN buy_phase ENUM('S', 'A', 'B', 'C', 'D', 'Z') NULL 
                    COMMENT '仕入フェーズ（NULL=空欄）'
                """)
                print("   ✓ buy_phaseをNULL許可に変更しました")
                
                # sell_phaseをNULL許可に変更
                print("3. sell_phaseをNULL許可に変更中...")
                await cursor.execute("""
                    ALTER TABLE contact_phase_summary
                    MODIFY COLUMN sell_phase ENUM('S', 'A', 'B', 'C', 'D', 'Z') NULL 
                    COMMENT '販売フェーズ（NULL=空欄）'
                """)
                print("   ✓ sell_phaseをNULL許可に変更しました")
                
                # 新しいユニーク制約を追加
                print("4. 新しいユニーク制約を追加中...")
                await cursor.execute("""
                    ALTER TABLE contact_phase_summary
                    ADD UNIQUE KEY uk_aggregation_owner_phases 
                    (aggregation_date, owner_id, buy_phase, sell_phase)
                """)
                print("   ✓ ユニーク制約を追加しました")
                
                await conn.commit()
                print("\n✓ スキーマ変更が完了しました！")
                return True
                
    except Exception as e:
        print(f"\n✗ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if db_pool:
            db_pool.close()
            await db_pool.wait_closed()

async def main():
    """メイン関数"""
    print("=" * 60)
    print("コンタクトフェーズ集計テーブルのスキーマ変更")
    print("=" * 60)
    print()
    
    success = await apply_schema_change()
    
    if success:
        print("\nスキーマ変更が正常に完了しました。")
        print("これで、空欄のフェーズはNULLとして保存され、")
        print("実際の'Z'フェーズと区別できるようになりました。")
    else:
        print("\nスキーマ変更に失敗しました。")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())





