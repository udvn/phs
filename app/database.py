from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from contextlib import contextmanager
from dotenv import load_dotenv
import time
from typing import Generator

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://medical_user:medical_password@db:5432/medical_db"
)

def get_database_url():
    """Получение URL для подключения к базе данных"""
    return SQLALCHEMY_DATABASE_URL

def connect_to_database(max_retries=30, retry_interval=1):
    """Подключение к базе данных с повторными попытками"""
    for attempt in range(max_retries):
        try:
            engine = create_engine(get_database_url())
            # Проверяем подключение
            with engine.connect() as conn:
                pass
            return engine
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Failed to connect to database, retrying in {retry_interval} seconds... Error: {e}")
                time.sleep(retry_interval)
            else:
                raise

# Создаем движок базы данных с повторными попытками
engine = connect_to_database()

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем базовый класс для моделей
Base = declarative_base()

def get_db() -> Generator:
    """Получение сессии базы данных для FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Инициализация базы данных"""
    from .models import Base
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully") 