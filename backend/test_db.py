from database import engine

try:
    connection = engine.connect()
    print("MySQL connection successful!")
    connection.close()
except Exception as e:
    print("MySQL connection failed!")
    print(e)