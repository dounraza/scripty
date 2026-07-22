import mysql.connector
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'cpp_trans_prod'
}
try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE dashboard_stats ADD COLUMN objectIdCompanyReservation TEXT, ADD COLUMN objectIdTransaction TEXT;")
    conn.commit()
    cursor.close()
    conn.close()
    print("Table updated successfully.")
except Exception as e:
    print(f"Error: {e}")
