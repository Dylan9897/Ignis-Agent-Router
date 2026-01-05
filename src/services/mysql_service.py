# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 17:32
# -*- coding: utf-8 -*-
"""
MySQL 基础数据库操作类（基于 PyMySQL）
作者: 冬瓜
邮箱: dylan_han@126.com
时间: 2026/1/4
"""

import pymysql
from pymysql import MySQLError
from typing import Optional, Dict, Any, List, Tuple, Union
import logging

# 可选：配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseDB:
    """
    MySQL 数据库操作基类，封装连接、查询、事务等通用逻辑。
    使用示例：
        db = BaseDB(host="...", user="...", password="...", database="...")
        with db as cursor:
            cursor.execute("SELECT ...")
            print(cursor.fetchall())
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: Optional[str] = None,
        charset: str = "utf8mb4",
        autocommit: bool = False,
        connect_timeout: int = 10,
        read_timeout: int = 30,
        write_timeout: int = 30,
    ):
        self._config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": charset,
            "autocommit": autocommit,
            "connect_timeout": connect_timeout,
            "read_timeout": read_timeout,
            "write_timeout": write_timeout,
            "cursorclass": pymysql.cursors.DictCursor,  # 返回字典格式
        }
        self._connection: Optional[pymysql.Connection] = None

    def _connect(self) -> pymysql.Connection:
        """建立数据库连接"""
        try:
            conn = pymysql.connect(**self._config)
            logger.info(f"✅ 成功连接到 MySQL: {self._config['host']}:{self._config['port']}/{self._config['database']}")
            return conn
        except Exception as e:
            logger.error(f"❌ 连接 MySQL 失败: {e}")
            raise

    def get_connection(self) -> pymysql.Connection:
        """获取连接（懒加载 + 自动重连）"""
        if self._connection is None or not self._connection.open:
            self._connection = self._connect()
        return self._connection

    def close(self):
        """关闭连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            logger.info("🔌 MySQL 连接已关闭")

    def __enter__(self):
        """支持 with 语句：返回游标"""
        conn = self.get_connection()
        self._cursor = conn.cursor()
        return self._cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 时自动提交/回滚并关闭游标"""
        conn = self.get_connection()
        try:
            if exc_type is not None:
                conn.rollback()
                logger.warning("⚠️ 事务已回滚")
            else:
                if not self._config["autocommit"]:
                    conn.commit()
                    logger.debug("✅ 事务已提交")
        finally:
            if hasattr(self, '_cursor') and self._cursor:
                self._cursor.close()
        # 注意：不在此处 close connection，以便复用

    # ------------------ 高级便捷方法（可选）------------------

    def execute(self, sql: str, args: Union[Tuple, Dict, List] = None) -> int:
        """执行 INSERT/UPDATE/DELETE，返回影响行数"""
        with self as cursor:
            cursor.execute(sql, args)
            return cursor.rowcount

    def fetch_one(self, sql: str, args: Union[Tuple, Dict, List] = None) -> Optional[Dict[str, Any]]:
        """查询单条记录"""
        with self as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()

    def fetch_all(self, sql: str, args: Union[Tuple, Dict, List] = None) -> List[Dict[str, Any]]:
        """查询多条记录"""
        with self as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """插入单条记录，返回自增 ID（如有）"""
        keys = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["%s"] * len(keys))
        columns = ", ".join(keys)
        sql = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})"
        with self as cursor:
            cursor.execute(sql, values)
            return cursor.lastrowid

    def begin(self):
        """手动开始事务（配合 commit/rollback 使用）"""
        conn = self.get_connection()
        conn.begin()

    def commit(self):
        """手动提交事务"""
        if self._connection and self._connection.open:
            self._connection.commit()

    def rollback(self):
        """手动回滚事务"""
        if self._connection and self._connection.open:
            self._connection.rollback()


# ================== 使用示例 ==================
if __name__ == '__main__':
    # 初始化数据库连接
    db = BaseDB(
        host="192.168.1.56",
        port=3306,
        user="root",
        password="123456",
        database="information_schema"
    )

    # 方式1：使用 with 自动管理事务
    try:
        with db as cur:
            cur.execute("SELECT VERSION() as version")
            result = cur.fetchone()
            print("MySQL 版本:", result["version"])
    except Exception as e:
        print("查询出错:", e)

    # 方式2：使用便捷方法
    version = db.fetch_one("SELECT VERSION() as version")
    print("版本（便捷方法）:", version["version"])

    # 关闭连接（可选，程序结束会自动释放）
    db.close()