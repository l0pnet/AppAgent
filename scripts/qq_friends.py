# 这个模块定义了与MariaDB数据库交互的类
# 以及一些与数据库交互的函数
# 数据库的结构如下：
# +-----------------+------------------+------+-----+---------+---------------
'''
# QQFriends 表
CREATE TABLE QQFriends (
    QQNumber BIGINT PRIMARY KEY,
    Nickname VARCHAR(100),
    Gender CHAR(1),
    Age INT,
    Location VARCHAR(100),
    FromLocation VARCHAR(100),
    RemarkName VARCHAR(100),
    ExploreCondition VARCHAR(255),
    CreatedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ModifiedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4;

# QQFriendsDetails 表
CREATE TABLE QQFriendsDetails (
    QQNumber BIGINT PRIMARY KEY,
    Description TEXT,
    PhotoPath VARCHAR(255),
    CreatedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ModifiedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (QQNumber) REFERENCES QQFriends(QQNumber)
) DEFAULT CHARSET=utf8mb4;

'''
# 数据库的连接信息在 config.py 中定义configs["DB_CONN"]

import pymysql
pymysql.install_as_MySQLdb()
from config import load_config
from utils import print_with_color
from sqlalchemy import create_engine
import pymysql.cursors

configs = load_config()
class QQFriends:
    def __init__(self):
        self.engine = create_engine(configs["DB_CONN"], encoding='utf-8', echo=False, pool_recycle=3600)

    def add_friend(self, friend_data):
        with self.engine.connect() as conn:
            columns = ', '.join(f"`{col}`" for col in friend_data)
            placeholders = ', '.join(f"%({col})s" for col in friend_data)
            sql = f"INSERT INTO `QQFriends` ({columns}) VALUES ({placeholders})"
            conn.execute(sql, friend_data)

    def add_friends(self, friends_data):
        with self.engine.connect() as conn:
            for friend_data in friends_data:
                self.add_friend(friend_data)

    def add_friend_detail(self, qq_number, detail_data):
        with self.engine.connect() as conn:
            columns = ', '.join(f"`{col}`" for col in detail_data)
            placeholders = ', '.join(['%s'] * len(detail_data))  # 不再加 1，因为不包括 qq_number
            sql = f"INSERT INTO `QQFriendsDetails` (`QQNumber`, {columns}) VALUES (%s, {placeholders})"
            values = [qq_number] + list(detail_data.values())
            conn.execute(sql, values)


    def qq_number_exists(self, qq_number):
        with self.engine.connect() as conn:
            sql = "SELECT COUNT(1) FROM `QQFriends` WHERE `QQNumber` = %s"
            result = conn.execute(sql, (qq_number,)).fetchone()
            return result[0] > 0

    def get_friend(self, qq_number):
        with self.engine.connect() as conn:
            sql = "SELECT * FROM `QQFriends` WHERE `QQNumber` = %s"
            return conn.execute(sql, (qq_number,)).fetchone()

    def get_friend_detail(self, qq_number):
        with self.engine.connect() as conn:
            sql = """
                SELECT f.*, d.Description, d.PhotoPath 
                FROM `QQFriends` f 
                JOIN `QQFriendsDetails` d ON f.QQNumber = d.QQNumber 
                WHERE f.QQNumber = %s
            """
            return conn.execute(sql, (qq_number,)).fetchone()

    def get_friend_with_detail(self, qq_number):
        # `get_friend_with_detail` 方法通过 `LEFT JOIN` 操作将 `QQFriends` 表和 `QQFriendsDetails` 表结合起来，
        #    以便为给定的 QQ 号提供完整的信息，包括好友的基本信息和详细信息。
        # 这样，您就可以方便地获取一个好友的所有相关信息，包括基本信息和详细描述、照片路径等。
        # 使用这个方法的前提是您已经正确地将数据插入到这两个表中。
        with self.engine.connect() as conn:
            sql = """
                SELECT f.*, d.Description, d.PhotoPath 
                FROM `QQFriends` f 
                LEFT JOIN `QQFriendsDetails` d ON f.QQNumber = d.QQNumber 
                WHERE f.QQNumber = %s
            """
            return conn.execute(sql, (qq_number,)).fetchone()   
        
    def update_friend(self, qq_number, update_data):
        with self.engine.connect() as conn:
            update_clauses = ', '.join(f"`{key}` = %({key})s" for key in update_data)
            sql = f"UPDATE `QQFriends` SET {update_clauses} WHERE `QQNumber` = %s"
            update_data['QQNumber'] = qq_number
            conn.execute(sql, update_data)

    def update_friend_detail(self, qq_number, update_data):
        with self.engine.connect() as conn:
            update_clauses = ', '.join(f"`{key}` = %({key})s" for key in update_data)
            sql = f"UPDATE `QQFriendsDetails` SET {update_clauses} WHERE `QQNumber` = %s"
            update_data['QQNumber'] = qq_number
            conn.execute(sql, update_data)

    def search_friends(self, **kwargs):
        with self.engine.connect() as conn:
            base_query = "SELECT * FROM `QQFriends` WHERE "
            conditions = []
            values = []
            for key, value in kwargs.items():
                conditions.append(f"`{key}` = %s")
                values.append(value)
            final_query = base_query + " AND ".join(conditions)
            return conn.execute(final_query, tuple(values)).fetchall()


    
