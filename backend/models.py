from database import get_connection


def insert_customer(data):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO customers
            (customer_id, customer_name, gender, age, some_number, submitted_at)
        VALUES
            (%s, %s, %s, %s, %s, %s)
    """
    values = (
        data["customer_id"],
        data["customer_name"],
        data["gender"],
        data["age"],
        data["some_number"],
        data["submitted_at"],
    )
    cursor.execute(sql, values)
    conn.commit()
    row_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return row_id


def get_all_customers():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM customers ORDER BY submitted_at DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for row in rows:
        if row.get("submitted_at"):
            row["submitted_at"] = row["submitted_at"].strftime("%Y-%m-%d %H:%M:%S")
    return rows
