#!/usr/bin/env python3
"""初始化数据库脚本"""

import sqlite3
import os
from pathlib import Path

def init_database(db_path: str = "data/analyzer.db"):
    """初始化SQLite数据库"""
    # 创建目录
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            error TEXT,
            report_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            content TEXT NOT NULL,
            file_path TEXT,
            minio_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"数据库初始化成功: {db_path}")

if __name__ == "__main__":
    init_database()
