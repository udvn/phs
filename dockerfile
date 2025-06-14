FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gfortran \
    libatlas-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование только requirements.txt сначала для лучшего использования кэша
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файл с моделью
COPY best_model.pkl /app/best_model.pkl

# Устанавливаем переменную окружения для пути к модели
ENV ML_MODEL_PATH=/app/best_model.pkl

# Копирование только необходимых файлов приложения
COPY app/ app/
COPY .env .

# Открытие портов для API и Streamlit
EXPOSE 8000 8501

# Запуск приложения (будет переопределено в docker-compose.yml)
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 