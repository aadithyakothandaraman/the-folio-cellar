
from app import get_db_connection

connection = None

try:
    connection = get_db_connection()

    if connection.is_connected():
        print("SUCCESS: Connected to MySQL!")
        print("Database:", connection.database)

except Exception as error:
    print("CONNECTION FAILED:", error)

finally:
    if connection is not None and connection.is_connected():
        connection.close()
        print("Database connection closed.")
