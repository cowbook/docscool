import sqlite3
conn = sqlite3.connect('instance/contracts.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("数据库中的表:", tables)

for table in tables:
    print(f"\n表 {table[0]} 的列:")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(col)

conn.close()
