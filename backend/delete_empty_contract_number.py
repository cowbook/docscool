import sqlite3
conn = sqlite3.connect('instance/contracts.db')
cursor = conn.cursor()

# 查询合同编号为空的记录数量
cursor.execute("SELECT COUNT(*) FROM contracts WHERE contract_number IS NULL OR contract_number = ''")
count = cursor.fetchone()[0]
print(f"合同编号为空的记录数量: {count}")

if count > 0:
    # 删除合同编号为空的记录
    cursor.execute("DELETE FROM contracts WHERE contract_number IS NULL OR contract_number = ''")
    conn.commit()
    print(f"已删除 {count} 条合同编号为空的记录")
else:
    print("没有需要删除的记录")

conn.close()
