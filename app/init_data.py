from werkzeug.security import generate_password_hash
from .models import User, MLModel
from .database import SessionLocal

def init_demo_data():
    db = SessionLocal()
    try:
        # Создание админской учетной записи
        admin = db.query(User).filter(User.username == 'admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),  # Простой пароль для демо
                email='admin@example.com',
                is_admin=True,
                balance=1000.0  # Начальный баланс для админа
            )
            db.add(admin)
            print("Создана админская учетная запись (логин: admin, пароль: admin)")
        
        # Создание демо-пользователя
        demo_user = db.query(User).filter(User.username == 'demo').first()
        if not demo_user:
            demo_user = User(
                username='demo',
                password_hash=generate_password_hash('demo'),
                email='demo@example.com',
                is_admin=False,
                balance=100.0
            )
            db.add(demo_user)
            print("Создан демо-пользователь (логин: demo, пароль: demo)")
        
        # Создаем демо-модели
        models = [
            MLModel(
                name='Medical Diagnosis Model',
                description='Модель для предсказания медицинских диагнозов',
                version='1.0.0',
                cost_per_prediction=1.0,
                is_active=True
            ),
            MLModel(
                name='Disease Risk Assessment',
                description='Модель для оценки риска заболеваний',
                version='1.0.0',
                cost_per_prediction=2.0,
                is_active=True
            )
        ]
        
        for model in models:
            existing_model = db.query(MLModel).filter(
                MLModel.name == model.name,
                MLModel.version == model.version
            ).first()
            if not existing_model:
                db.add(model)
                print(f"Добавлена модель: {model.name}")
        
        db.commit()
        print("Инициализация демо-данных завершена")
    finally:
        db.close() 