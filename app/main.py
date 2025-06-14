from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import json
import ast

from . import models, schemas, database
from .ml_service import MLService

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
ml_service = MLService()

# Зависимость для получения сессии БД
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = schemas.decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not schemas.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = schemas.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
    hashed_password = schemas.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/predictions/", response_model=schemas.Prediction)
def create_prediction(
    prediction: schemas.PredictionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        print("Полученные данные:", prediction.input_data)
        
        # Проверка и преобразование входных данных
        input_data = prediction.input_data
        if not isinstance(input_data, dict):
            raise ValueError("Входные данные должны быть словарем")
            
        # Получаем модель по умолчанию
        default_model = db.query(models.MLModel).first()
        if not default_model:
            default_model = models.MLModel(
                name="default_model",
                version="1.0"
            )
            db.add(default_model)
            db.commit()
            db.refresh(default_model)
        
        # Обрабатываем предсказание
        try:
            result = ml_service.process_prediction(input_data)
            print("Результат обработки:", result)
        except Exception as e:
            print("Ошибка MLService:", str(e))
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка обработки данных: {str(e)}"
            )
        
        # Создаем запись в базе данных
        db_prediction = models.Prediction(
            user_id=current_user.id,
            model_id=default_model.id,
            input_data=input_data,
            result=result,
            status="completed"
        )
        db.add(db_prediction)
        db.commit()
        db.refresh(db_prediction)
        
        # Преобразуем результат в JSON для ответа
        response_data = {
            "id": db_prediction.id,
            "user_id": db_prediction.user_id,
            "model_id": db_prediction.model_id,
            "input_data": db_prediction.input_data,
            "result": result,
            "status": db_prediction.status,
            "created_at": db_prediction.created_at,
            "updated_at": db_prediction.updated_at
        }
        
        print("Отправляем ответ:", response_data)
        return response_data
    except Exception as e:
        print("Ошибка:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/predictions/", response_model=List[schemas.Prediction])
def get_predictions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    predictions = db.query(models.Prediction).filter(
        models.Prediction.user_id == current_user.id
    ).all()
    return predictions

@app.get("/users/me/", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user 