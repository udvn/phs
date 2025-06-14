from datetime import timedelta, datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, schemas, auth
from .database import engine, get_db
import logging
from .ml_service import MLService
import pprint

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Medical Diagnosis API")

logger = logging.getLogger(__name__)

ml_service = MLService()

def to_str(dt):
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = auth.get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@app.post("/predictions/", response_model=schemas.Prediction)
async def create_prediction(
    prediction: schemas.PredictionCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        print("API получил данные:", prediction.input_data)
        logger.info(f"API получил данные: {prediction.input_data}")
        
        # Создаем запись в базе данных
        db_prediction = models.Prediction(
            user_id=current_user.id,
            input_data=prediction.input_data.dict(),
            status="processing"
        )
        db.add(db_prediction)
        db.commit()
        db.refresh(db_prediction)
        
        try:
            # Передаём в ML сервис словарь, а не Pydantic-объект!
            print("Передаём в ML сервис:", prediction.input_data.dict())
            logger.info(f"Передаём в ML сервис: {prediction.input_data.dict()}")
            result = ml_service.process_prediction(prediction.input_data.dict())
            print("ML сервис вернул результат:", result)
            logger.info(f"ML сервис вернул результат: {result}")
            
            # Обновляем запись в базе данных
            db_prediction.result = result
            db_prediction.status = "completed"
            db.commit()
            db.refresh(db_prediction)
            
            print("DEBUG: db_prediction =", db_prediction)
            print("DEBUG: db_prediction.__dict__ =", db_prediction.__dict__)
            pprint.pprint(db_prediction.__dict__)
            
            result = db_prediction.__dict__.copy()
            result["created_at"] = to_str(result.get("created_at"))
            result["updated_at"] = to_str(result.get("updated_at"))
            result["model_id"] = result.get("model_id") or 0
            print("DEBUG: result for response:", result)
            return result
            
        except Exception as e:
            error_msg = f"Ошибка ML сервиса: {str(e)}"
            logger.error(error_msg)
            # Обновляем статус в базе данных
            db_prediction.status = "failed"
            db.commit()
            raise HTTPException(status_code=500, detail=error_msg)
            
    except Exception as e:
        error_msg = f"Ошибка при создании предсказания: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/predictions/", response_model=list[schemas.Prediction])
def read_predictions(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    predictions = db.query(models.Prediction).filter(
        models.Prediction.user_id == current_user.id
    ).all()
    return predictions 