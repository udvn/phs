import os
print("DEBUG: RABBITMQ_URL =", os.environ.get("RABBITMQ_URL"))
print("DEBUG: HOSTNAME =", os.uname().nodename)
print("DEBUG: ALL ENV =", dict(os.environ))
import json
import time
import pika
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Prediction, User, MLModel
from app.ml_model.model import MedicalRiskModel

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация модели
predictor = MedicalRiskModel()

def process_prediction_async(prediction_id: int):
    """Асинхронная обработка предсказания из очереди."""
    db = SessionLocal()
    prediction = None
    try:
        prediction = db.query(Prediction).get(prediction_id)
        if not prediction:
            logger.warning(f"Prediction with ID {prediction_id} not found in DB for async processing.")
            return
        
        input_data = prediction.input_data # Данные из поля JSONB в БД
        
        # --- Подготовка входных данных для MedicalRiskModel.predict ---
        # MedicalRiskModel.predict ожидает ключи 'Age', 'BMI', 'Sex', 'Race' (CamelCase)
        # Входные данные из API/БД используют snake_case.
        model_input = {
            'Age': input_data.get('age'),
            'BMI': input_data.get('bmi'),
            'Sex': input_data.get('sex'), 
            'Race': input_data.get('race'),
            'systolic_bp': input_data.get('systolic_bp'),
            'diastolic_bp': input_data.get('diastolic_bp'),
            'heart_rate': input_data.get('heart_rate'),
            'temperature': input_data.get('temperature'),
        }
        model_input = {k: v for k, v in model_input.items() if v is not None}

        required_model_fields = ['Age', 'BMI', 'Sex', 'Race'] 
        for field in required_model_fields:
            if field not in model_input or model_input[field] is None:
                error_msg = f"Отсутствует или некорректное значение обязательного поля для модели в worker: {field}. Полученные данные: {input_data}"
                logger.error(error_msg)
                prediction.status = "failed"
                prediction.result = {"error": error_msg}
                db.commit()
                return 
        
        # Делаем предсказание
        ml_model_result = predictor.predict(model_input)
        
        prediction.status = "completed"
        prediction.result = ml_model_result
        logger.info(f"Prediction {prediction_id} completed successfully by worker.")
        
        db.commit()
        
    except Exception as e:
        error_msg = f"Ошибка в worker при обработке предсказания {prediction_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if prediction: 
            prediction.status = "failed"
            prediction.result = {"error": error_msg}
            db.commit()
    finally:
        db.close()

def callback(ch, method, properties, body):
    """Обработчик сообщений из очереди"""
    try:
        data = json.loads(body)
        prediction_id = data.get("prediction_id")
        if prediction_id:
            process_prediction_async(prediction_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Worker: Ошибка при обработке сообщения из очереди: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag)

def connect_to_rabbitmq(max_retries=120, retry_interval=2):
    """Подключение к RabbitMQ с повтором."""
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    print("DEBUG: RABBITMQ_URL =", rabbitmq_url)
    if not rabbitmq_url:
        raise ValueError("Переменная окружения RABBITMQ_URL не установлена!")
    for attempt in range(max_retries):
        try:
            print(f"Попытка подключения к RabbitMQ ({rabbitmq_url}), попытка {attempt+1}/{max_retries}")
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            print("Успешно подключились к RabbitMQ!")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Failed to connect to RabbitMQ: {e}, retrying in {retry_interval} seconds... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_interval)
        except Exception as e:
            print(f"Другая ошибка при подключении к RabbitMQ: {e}")
            time.sleep(retry_interval)
    raise RuntimeError("Не удалось подключиться к RabbitMQ после всех попыток")

def main():
    """Запуск воркера."""
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue="predictions")
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="predictions", on_message_callback=callback)
    print("Worker started. Waiting for messages...")
    channel.start_consuming()

if __name__ == "__main__":
    main() 