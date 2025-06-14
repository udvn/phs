from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

# JWT настройки
SECRET_KEY = "your-secret-key-here"  # В продакшене использовать безопасный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class MLModelBase(BaseModel):
    name: str
    description: str
    cost_per_prediction: float

class MLModelCreate(MLModelBase):
    pass

class MLModel(MLModelBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class PredictionInput(BaseModel):
    age: float
    bmi: float
    sex: str # Например, "M" или "F"
    race: str # Например, "White", "Black" и т.д. - должны совпадать с категориями обучения
    # Добавьте эти поля, если вы планируете использовать их в расчете risk_score,
    # даже если они не идут напрямую в ML модель.
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    heart_rate: Optional[float] = None
    temperature: Optional[float] = None
    # 'blood_sugar' не нужен как вход, т.к. его предсказывает модель (HbA1c)

class PredictionCreate(BaseModel):
    input_data: PredictionInput # Теперь input_data будет объектом Pydantic модели PredictionInput

class Prediction(BaseModel):
    id: int
    user_id: int
    model_id: int
    input_data: Dict[str, Any] # Здесь можно оставить Dict[str, Any] или сделать PredictionInput
    result: Dict[str, Any] # Результат теперь будет содержать predictions_from_model и risk_calculation_details
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True # Или orm_mode = True для Pydantic v1

class TransactionBase(BaseModel):
    amount: float = Field(..., gt=0)
    transaction_type: str
    description: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    prediction_id: Optional[int] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class BalanceUpdate(BaseModel):
    amount: float = Field(..., gt=0)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None 