import json
import pika
import logging
from typing import Dict, Any
from app.ml_model.model import MedicalRiskModel
from app.schemas import PredictionInput

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.model = MedicalRiskModel()
        self.connect()

    def connect(self):
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('rabbitmq')
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue='prediction_queue')
            logger.info("Успешное подключение к RabbitMQ")
        except Exception as e:
            logger.error(f"Ошибка подключения к RabbitMQ: {e}. Убедитесь, что RabbitMQ запущен и доступен.")
            raise

    def process_prediction(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            print("MLService получил данные:", input_data)
            logger.info(f"MLService получил данные: {input_data}")
            
            # --- Подготовка входных данных для MedicalRiskModel.predict ---
            # MedicalRiskModel.predict ожидает ключи 'Age', 'BMI', 'Sex', 'Race',
            # и опционально 'systolic_bp', 'diastolic_bp', 'heart_rate', 'temperature'.
            # Важно преобразовать ключи из lower_case (как в PredictionInput) в CamelCase,
            # как ожидает класс MedicalRiskModel, а также учесть, что 'gender' стал 'sex' в схеме.
            
            model_input = {
                'Age': input_data.get('age'),
                'BMI': input_data.get('bmi'),
                'Sex': input_data.get('sex'), # Ключ 'sex' из PredictionInput
                'Race': input_data.get('race'),
                # Дополнительные поля, которые могут использоваться для расчета риска в MedicalRiskModel
                'systolic_bp': input_data.get('systolic_bp'),
                'diastolic_bp': input_data.get('diastolic_bp'),
                'heart_rate': input_data.get('heart_rate'),
                'temperature': input_data.get('temperature'),
            }
            # Удаляем None значения, чтобы не передавать их в модель, если они не были предоставлены
            model_input = {k: v for k, v in model_input.items() if v is not None}

            # Валидация необходимых полей для модели
            # Эти поля необходимы для _generate_features в MedicalRiskModel
            required_model_fields = ['Age', 'BMI', 'Sex', 'Race'] 
            for field in required_model_fields:
                if field not in model_input or model_input[field] is None:
                    error_msg = f"Отсутствует или некорректное значение обязательного поля для модели: {field}. Полученные данные: {input_data}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

            # Вызываем метод predict на загруженной модели MedicalRiskModel
            # MedicalRiskModel.predict теперь возвращает структурированный результат,
            # который включает предсказания ML модели и детали расчета риска
            ml_model_result = self.model.predict(model_input)
            
            # Логирование результата от модели
            logger.info(f"MedicalRiskModel вернула результат: {ml_model_result}")
            
            # Возвращаем результат, полученный от модели, напрямую
            # Этот результат уже соответствует структуре Dict[str, Any], ожидаемой в schemas.Prediction.result
            return ml_model_result

        except Exception as e:
            error_msg = f"MLService ошибка при обработке предсказания: {str(e)}"
            logger.error(error_msg, exc_info=True) # Добавляем exc_info=True для полного стектрейса
            raise ValueError(error_msg)

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Соединение с RabbitMQ закрыто")

if __name__ == "__main__":
    service = MLService()
    try:
        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                prediction_id = data['prediction_id']
                # input_data из очереди приходит как JSON строка, нужно распарсить
                input_data_from_queue = json.loads(data['input_data']) 
                
                # Теперь передаем этот распакованный словарь в process_prediction
                result = service.process_prediction(input_data_from_queue)
                
                # Отправка результата обратно в API
                # 'result' (от ml_model_result) - это уже Dict, который нужно запаковать в JSON
                # для отправки по RabbitMQ. Если API ожидает строку в поле 'result',
                # то это 'json.dumps(result)' будет верным.
                ch.basic_publish(
                    exchange='',
                    routing_key='prediction_results',
                    body=json.dumps({
                        'prediction_id': prediction_id,
                        'result': json.dumps(result) # Дважды JSON-кодируем, если API ожидает строку
                    })
                )
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"Предсказание {prediction_id} обработано успешно")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения из очереди для prediction_id {prediction_id}: {e}", exc_info=True)
                ch.basic_nack(delivery_tag=method.delivery_tag) # Nack, чтобы сообщение вернулось в очередь или Dead Letter Queue

        service.channel.basic_consume(
            queue='prediction_queue',
            on_message_callback=callback
        )
        
        logger.info("MLService запущен и ожидает сообщений...")
        service.channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения работы MLService.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске MLService: {e}", exc_info=True)
    finally:
        service.close() 