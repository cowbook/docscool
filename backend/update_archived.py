import sqlite3
conn = sqlite3.connect('instance/contracts.db')
cursor = conn.cursor()
cursor.execute("UPDATE contracts SET is_archived = '未归档'")
conn.commit()
print(f'已更新 {cursor.rowcount} 条记录')
conn.close()
