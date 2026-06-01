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
