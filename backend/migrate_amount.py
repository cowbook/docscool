import sqlite3
conn = sqlite3.connect('instance/contracts.db')
cursor = conn.cursor()

# 将现有金额数据放大10000倍
cursor.execute("UPDATE contracts SET amount = amount * 10000")

conn.commit()
print(f'已更新 {cursor.rowcount} 条记录的金额')

# 验证更新结果
cursor.execute("SELECT id, contract_name, amount FROM contracts LIMIT 5")
rows = cursor.fetchall()
print("\n更新后的前5条记录:")
for row in rows:
    print(f"  ID: {row[0]}, 名称: {row[1]}, 金额: {row[2]}")

conn.close()
