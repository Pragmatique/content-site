
from sqlalchemy import create_engine, text

connection_string = "postgresql+psycopg2://postgres:1234@localhost:5432/mydb"

try:
    engine = create_engine(connection_string)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        version = result.fetchone()[0]
        print("✅ Подключение успешно!")
        print(f"PostgreSQL версия: {version}")
        
        # Проверка существования базы данных
        result = connection.execute(text("SELECT current_database();"))
        db_name = result.fetchone()[0]
        print(f"Текущая БД: {db_name}")
        
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
