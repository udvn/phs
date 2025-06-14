import numpy as np
from typing import Dict, List, Union, Any
import pickle
import os
import pandas as pd

class MedicalRiskModel:
    def __init__(self):
        # Путь к сохранённой модели (best_model.pkl должен быть доступен)
        model_path = os.getenv('ML_MODEL_PATH', 'best_model.pkl')
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель не найдена по пути: {model_path}.")
        # Загрузка словаря моделей (Pipeline для каждого таргета)
        with open(model_path, 'rb') as f:
            self.models = pickle.load(f)
        # Списки признаков и целевых переменных, как в обучении
        self.FEATURES_NUM = ["Age", "BMI", "SexAge"]
        self.FEATURES_CAT = ["Sex", "Race", "AgeGroup", "BMIClass"]
        self.TARGETS = ["HbA1c", "LDL", "SBP"]
        # Классы риска и рекомендации
        self.risk_classes = {
            'very_low': {
                'description': 'Очень низкий риск',
                'recommendation': 'Продолжайте вести здоровый образ жизни'
            },
            'low': {
                'description': 'Низкий риск',
                'recommendation': 'Рекомендуется регулярное медицинское обследование'
            },
            'medium': {
                'description': 'Средний риск',
                'recommendation': 'Необходима консультация врача'
            },
            'high': {
                'description': 'Высокий риск',
                'recommendation': 'Требуется немедленная медицинская помощь'
            }
        }
        # Нормальные диапазоны и веса факторов риска
        self.normal_ranges = {
            'age': {
                'M': {'min': 0, 'max': 120, 'weight': 0.15},
                'F': {'min': 0, 'max': 120, 'weight': 0.15}
            },
            'systolic_bp': { 
                'M': {'min': 100, 'max': 130, 'weight': 0.4},
                'F': {'min': 95, 'max': 125, 'weight': 0.4}
            },
            'diastolic_bp': {
                'M': {'min': 65, 'max': 85, 'weight': 0.35},
                'F': {'min': 60, 'max': 80, 'weight': 0.35}
            },
            'heart_rate': {
                'M': {'min': 55, 'max': 90, 'weight': 0.3},
                'F': {'min': 55, 'max': 90, 'weight': 0.3}
            },
            'temperature': {
                'M': {'min': 36.2, 'max': 36.9, 'weight': 0.3},
                'F': {'min': 36.2, 'max': 36.9, 'weight': 0.3}
            },
            'blood_sugar': { 
                'M': {'min': 3.9, 'max': 5.6, 'weight': 0.4},
                'F': {'min': 3.9, 'max': 5.6, 'weight': 0.4}
            },
            'BMI': { 
                'M': {'min': 19.0, 'max': 25.0, 'weight': 0.4},
                'F': {'min': 19.0, 'max': 25.0, 'weight': 0.4}
            },
            'LDL': {
                'M': {'min': 0, 'max': 100, 'weight': 0.4},
                'F': {'min': 0, 'max': 100, 'weight': 0.4}
            },
        }

    def calculate_age_factor(self, age):
        """Фактор риска по возрасту"""
        if age < 18:
            return 0.1
        elif age < 30:
            return 0.2
        elif age < 50:
            return 0.3
        elif age < 70:
            return 0.5
        else:
            return 0.7

    def calculate_deviation(self, value, min_val, max_val, indicator):
        """Отклонение показателя от нормы"""
        if value < min_val:
            if indicator == 'blood_sugar':
                return min(1.0, (min_val - value) / min_val * 2)
            elif indicator in ['systolic_bp', 'diastolic_bp']:
                return min(1.0, (min_val - value) / min_val * 1.5)
            else:
                return min(1.0, (min_val - value) / min_val)
        elif value > max_val:
            if indicator == 'blood_sugar':
                return min(1.0, (value - max_val) / max_val * 3)
            elif indicator in ['systolic_bp', 'diastolic_bp']:
                return min(1.0, (value - max_val) / max_val * 2)
            elif indicator == 'temperature':
                return min(1.0, (value - max_val) / max_val * 2.5)
            else:
                return min(1.0, (value - max_val) / max_val)
        else:
            return 0

    def _generate_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация производных признаков"""
        processed_data = data.copy()
        if 'Sex' in processed_data and 'Age' in processed_data:
            numeric_sex_for_sex_age = 1 if processed_data['Sex'] == 'M' else 0
            processed_data['SexAge'] = numeric_sex_for_sex_age * processed_data['Age']
        else:
            processed_data['SexAge'] = np.nan
        if 'Age' in processed_data:
            age = processed_data['Age']
            if age < 18:
                processed_data['AgeGroup'] = 'child'
            elif age < 30:
                processed_data['AgeGroup'] = 'young_adult'
            elif age < 50:
                processed_data['AgeGroup'] = 'middle_aged'
            elif age < 70:
                processed_data['AgeGroup'] = 'senior'
            else:
                processed_data['AgeGroup'] = 'elderly'
        else:
            processed_data['AgeGroup'] = 'unknown'
        if 'BMI' in processed_data:
            bmi = processed_data['BMI']
            if bmi < 18.5:
                processed_data['BMIClass'] = 'underweight'
            elif bmi < 25:
                processed_data['BMIClass'] = 'normal_weight'
            elif bmi < 30:
                processed_data['BMIClass'] = 'overweight'
            else:
                processed_data['BMIClass'] = 'obese'
        else:
            processed_data['BMIClass'] = 'unknown'
        return processed_data

    def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("[DEBUG] Входные данные для расчёта риска:", input_data)
        processed_input_data = self._generate_features(input_data)
        print("[DEBUG] После генерации признаков:", processed_input_data)
        all_features_needed = self.FEATURES_NUM + self.FEATURES_CAT
        input_df = pd.DataFrame([processed_input_data], columns=all_features_needed)
        predictions = {}
        for tgt in self.TARGETS:
            if tgt in self.models:
                model_pipeline = self.models[tgt]
                pred_value = model_pipeline.predict(input_df)[0]
                predictions[tgt] = float(pred_value)
            else:
                predictions[tgt] = None
        print("[DEBUG] Предсказания ML-модели:", predictions)
        total_weighted_deviation = 0
        total_weight = 0
        risk_factors_details = {}
        age_from_input = input_data.get('Age', 0)
        gender_from_input = input_data.get('Sex', 'M')
        age_factor = self.calculate_age_factor(age_from_input)
        total_weighted_deviation += age_factor * self.normal_ranges['age'][gender_from_input]['weight']
        total_weight += self.normal_ranges['age'][gender_from_input]['weight']
        risk_factors_details['age_factor'] = age_factor
        if 'HbA1c' in predictions and 'blood_sugar' in self.normal_ranges:
            value = predictions['HbA1c']
            min_val = self.normal_ranges['blood_sugar'][gender_from_input]['min']
            max_val = self.normal_ranges['blood_sugar'][gender_from_input]['max']
            weight = self.normal_ranges['blood_sugar'][gender_from_input]['weight']
            deviation = self.calculate_deviation(value, min_val, max_val, 'blood_sugar')
            total_weighted_deviation += deviation * weight
            total_weight += weight
            risk_factors_details['HbA1c_predicted'] = predictions['HbA1c']
            risk_factors_details['HbA1c_deviation'] = deviation
        if 'SBP' in predictions and 'systolic_bp' in self.normal_ranges:
            value = predictions['SBP']
            min_val = self.normal_ranges['systolic_bp'][gender_from_input]['min']
            max_val = self.normal_ranges['systolic_bp'][gender_from_input]['max']
            weight = self.normal_ranges['systolic_bp'][gender_from_input]['weight']
            deviation = self.calculate_deviation(value, min_val, max_val, 'systolic_bp')
            total_weighted_deviation += deviation * weight
            total_weight += weight
            risk_factors_details['SBP_predicted'] = predictions['SBP']
            risk_factors_details['SBP_deviation'] = deviation
        if 'LDL' in predictions and 'LDL' in self.normal_ranges:
            value = predictions['LDL']
            min_val = self.normal_ranges['LDL'][gender_from_input]['min']
            max_val = self.normal_ranges['LDL'][gender_from_input]['max']
            weight = self.normal_ranges['LDL'][gender_from_input]['weight']
            deviation = self.calculate_deviation(value, min_val, max_val, 'LDL')
            total_weighted_deviation += deviation * weight
            total_weight += weight
            risk_factors_details['LDL_predicted'] = predictions['LDL']
            risk_factors_details['LDL_deviation'] = deviation
        elif 'LDL' in predictions:
            risk_factors_details['LDL_predicted'] = predictions['LDL']
        indicators_from_input = ['BMI', 'diastolic_bp', 'heart_rate', 'temperature']
        for indicator in indicators_from_input:
            if indicator in input_data and indicator in self.normal_ranges:
                value = input_data[indicator]
                gender = input_data.get('Sex', 'M')
                min_val = self.normal_ranges[indicator][gender]['min']
                max_val = self.normal_ranges[indicator][gender]['max']
                weight = self.normal_ranges[indicator][gender]['weight']
                deviation = self.calculate_deviation(value, min_val, max_val, indicator)
                total_weighted_deviation += deviation * weight
                total_weight += weight
                risk_factors_details[f'{indicator}_input'] = input_data[indicator]
                risk_factors_details[f'{indicator}_deviation'] = deviation
        total_deviation = total_weighted_deviation / total_weight if total_weight > 0 else 0
        print("[DEBUG] Итоговое взвешенное отклонение:", total_deviation)
        if total_deviation < 0.1:
            risk_level = 'very_low'
        elif total_deviation < 0.3:
            risk_level = 'low'
        elif total_deviation < 0.6:
            risk_level = 'medium'
        else:
            risk_level = 'high'
        result = {
            'risk_level': risk_level,
            'risk_score': round(total_deviation * 100, 2),
            'description': self.risk_classes[risk_level]['description'],
            'recommendations': self.risk_classes[risk_level]['recommendation'],
            'predictions_from_model': predictions,
            'risk_calculation_details': risk_factors_details
        }
        print("[DEBUG] Финальный результат риска:", result)
        return result 