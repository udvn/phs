import streamlit as st
import requests
import json
from datetime import datetime
import os

# Конфигурация
API_URL = os.getenv("API_URL", "http://localhost:8000")

def login(username: str, password: str) -> dict:
    response = requests.post(
        f"{API_URL}/token",
        data={"username": username, "password": password}
    )
    if response.status_code == 200:
        return response.json()
    return None

def register(email: str, username: str, password: str) -> dict:
    response = requests.post(
        f"{API_URL}/users/",
        json={"email": email, "username": username, "password": password}
    )
    if response.status_code == 200:
        return response.json()
    return None

def create_prediction(token: str, input_data: dict) -> dict:
    print("Отправляемые данные:", input_data)  # Отладочный вывод
    try:
        response = requests.post(
            f"{API_URL}/predictions/",
            headers={"Authorization": f"Bearer {token}"},
            json={"input_data": input_data}
        )
        print("Статус ответа:", response.status_code)  # Отладочный вывод
        print("Текст ответа:", response.text)  # Отладочный вывод
        
        if response.status_code == 200:
            result = response.json()
            # Проверяем, является ли result строкой (JSON)
            if isinstance(result.get('result'), str):
                try:
                    result['result'] = json.loads(result['result'])
                except json.JSONDecodeError:
                    print("Ошибка декодирования JSON результата")
                    return None
            return result
        else:
            print(f"Ошибка API: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Ошибка при создании предсказания: {str(e)}")
        return None

def get_predictions(token: str) -> list:
    response = requests.get(
        f"{API_URL}/predictions/",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    return []

def get_current_user(token: str) -> dict:
    response = requests.get(
        f"{API_URL}/users/me/",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    return None

def display_risk_assessment(risk_data):
    """Отображение оценки риска"""
    if not risk_data:
        st.error("Нет данных для отображения")
        return
        
    st.markdown("### Результаты анализа")
    
    # Отображение общего риска и оценки
    risk_level = risk_data.get("risk_level", "Неизвестно")
    risk_score = risk_data.get("risk_score", 0)
    max_deviation = risk_data.get("max_deviation", 0)
    
    risk_color = {
        "Низкий": "green",
        "Средний": "orange",
        "Высокий": "red"
    }.get(risk_level, "gray")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Уровень риска:** :{risk_color}[{risk_level}]")
    with col2:
        st.markdown(f"**Оценка риска:** {risk_score}%")
    
    # Прогресс-бар для визуализации риска
    st.progress(risk_score / 100)
    
    # Отображение максимального отклонения
    st.markdown(f"**Максимальное отклонение от нормы:** {max_deviation}%")
    
    # Отображение факторов риска
    if risk_data.get("risk_factors"):
        st.markdown("#### Факторы риска:")
        for factor in risk_data["risk_factors"]:
            st.write(f"- {factor}")
    
    # Отображение деталей
    st.markdown("#### Детали анализа")
    for key, value in risk_data.get("details", {}).items():
        st.write(f"**{key}:** {value}")
    
    # Отображение рекомендаций
    st.markdown("#### Рекомендации")
    recs = risk_data.get("recommendations", [])
    if isinstance(recs, str):
        st.write(recs)
    elif isinstance(recs, list):
        for rec in recs:
            st.write(f"- {rec}")

def main():
    st.title("Система оценки медицинских рисков")
    
    # Инициализация состояния сессии
    if "token" not in st.session_state:
        st.session_state.token = None
    if "username" not in st.session_state:
        st.session_state.username = None

    # Проверка авторизации
    if st.session_state.token is None:
        tab1, tab2 = st.tabs(["Вход", "Регистрация"])
        
        with tab1:
            st.header("Вход в систему")
            username = st.text_input("Имя пользователя", key="login_username")
            password = st.text_input("Пароль", type="password", key="login_password")
            if st.button("Войти", key="login_button"):
                token_data = login(username, password)
                if token_data:
                    st.session_state.token = token_data["access_token"]
                    st.session_state.username = username
                    st.success("Успешный вход!")
                    st.experimental_rerun()
                else:
                    st.error("Неверное имя пользователя или пароль")

        with tab2:
            st.header("Регистрация")
            email = st.text_input("Email", key="register_email")
            username = st.text_input("Имя пользователя", key="register_username")
            password = st.text_input("Пароль", type="password", key="register_password")
            if st.button("Зарегистрироваться", key="register_button"):
                user = register(email, username, password)
                if user:
                    st.success("Регистрация успешна! Теперь вы можете войти.")
                else:
                    st.error("Ошибка при регистрации")
        return

    # Отображение информации о текущем пользователе и кнопка выхода
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**Текущий пользователь:** {st.session_state.username}")
    with col2:
        if st.button("Выйти", key="logout_button"):
            st.session_state.token = None
            st.session_state.username = None
            st.experimental_rerun()
    
    # Форма для ввода данных
    with st.form("prediction_form"):
        st.header("Введите медицинские показатели")
        
        col1, col2 = st.columns(2)
        
        with col1:
            age = st.number_input("Возраст", min_value=0, max_value=120, value=30)
            sex = st.selectbox("Пол", ["M", "F"])
            bmi = st.number_input("ИМТ (BMI)", min_value=10.0, max_value=60.0, value=25.0, step=0.1)
            systolic_bp = st.number_input("Систолическое давление", min_value=60, max_value=200, value=120)
            
        with col2:
            diastolic_bp = st.number_input("Диастолическое давление", min_value=40, max_value=120, value=80)
            heart_rate = st.number_input("Пульс", min_value=40, max_value=200, value=75)
            temperature = st.number_input("Температура", min_value=35.0, max_value=42.0, value=36.6, step=0.1)
        
        race = st.selectbox("Раса", ["White", "Black", "Asian", "Other"])
        
        submitted = st.form_submit_button("Оценить риски")
        
        if submitted:
            data = {
                "age": age,
                "sex": sex,
                "bmi": bmi,
                "race": race,
                "systolic_bp": systolic_bp,
                "diastolic_bp": diastolic_bp,
                "heart_rate": heart_rate,
                "temperature": temperature,
            }
            print("Отправляемые данные:", data)  # Отладочный вывод
            prediction = create_prediction(st.session_state.token, data)
            if prediction and prediction.get("result"):
                st.success("Предсказание создано!")
                display_risk_assessment(prediction["result"])
            else:
                st.error("Ошибка при создании предсказания")
                if prediction:
                    st.error(f"Детали ошибки: {prediction.get('detail', 'Неизвестная ошибка')}")

if __name__ == "__main__":
    main() 