import pika
import json
import os
from dotenv import load_dotenv
import logging
import time

load_dotenv()

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
PREDICTION_QUEUE = 'prediction_queue'

logger = logging.getLogger(__name__)

def connect_to_rabbitmq(max_retries=10, retry_interval=5):
    """Establishes a connection to RabbitMQ with retry logic."""
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url:
        # Если переменная RABBITMQ_URL не установлена, выбрасываем ошибку
        raise ValueError("Переменная окружения RABBITMQ_URL не установлена.")
    
    logger.info(f"Попытка подключения к RabbitMQ по URL: {rabbitmq_url}") # Добавлено для отладки
    
    connection = None
    for i in range(max_retries):
        try:
            params = pika.URLParameters(rabbitmq_url)
            connection = pika.BlockingConnection(params)
            logger.info("Успешно подключено к RabbitMQ.")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"Ошибка подключения к RabbitMQ (попытка {i+1}/{max_retries}): {e}")
            time.sleep(retry_interval)
        except Exception as e:
            logger.error(f"Неожиданная ошибка при подключении к RabbitMQ: {e}")
            time.sleep(retry_interval)
    logger.error("Не удалось подключиться к RabbitMQ после нескольких попыток.")
    raise pika.exceptions.AMQPConnectionError("Не удалось подключиться к RabbitMQ.")

def get_connection():
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url:
        raise ValueError("Переменная окружения RABBITMQ_URL не установлена.")
    params = pika.URLParameters(rabbitmq_url)
    return pika.BlockingConnection(params)

def publish_prediction_task(prediction_id: int, model_id: int, input_data: dict):
    connection = get_connection()
    channel = connection.channel()
    
    # Объявляем очередь
    channel.queue_declare(queue=PREDICTION_QUEUE, durable=True)
    
    # Формируем сообщение
    message = {
        'prediction_id': prediction_id,
        'model_id': model_id,
        'input_data': input_data
    }
    
    # Отправляем сообщение
    channel.basic_publish(
        exchange='',
        routing_key=PREDICTION_QUEUE,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # делаем сообщение persistent
        )
    )
    
    connection.close()

def consume_prediction_tasks(callback):
    connection = get_connection()
    channel = connection.channel()
    
    # Объявляем очередь
    channel.queue_declare(queue=PREDICTION_QUEUE, durable=True)
    
    # Устанавливаем prefetch_count=1 для равномерного распределения задач
    channel.basic_qos(prefetch_count=1)
    
    # Начинаем слушать очередь
    channel.basic_consume(
        queue=PREDICTION_QUEUE,
        on_message_callback=callback
    )
    
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming() 