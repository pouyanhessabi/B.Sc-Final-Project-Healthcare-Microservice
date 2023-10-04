import os
import pickle

import Levenshtein
import numpy as np
import pandas as pd
import xgboost as xgb


class DiseaseDetection:
    def __init__(self):
        self.default_params = {
            "max_depth": 5,
            "n_estimators": 100,
            "learning_rate": 0.2,
            "gamma": 0.1,
            "max_delta_step": 1,
            "min_child_weight": 5,
            "objective": "multi:softprob",
            "eval_metric": ["auc", "mlogloss"],
            "early_stopping_rounds": 5,
        }
        self.model = None
        self.symptoms_encoder = None
        self.diseases_encoder = None
        self.symptoms_list = None
        self.diseases_list = None

    def train(self, filepath, params=None):
        if params is None:
            params = self.default_params

        self.data = pd.read_csv('./data/dataset.csv')
        self.data[pd.isna(self.data)] = 'n/a'
        processing_data = np.array(self.data)
        diseases, symptoms = processing_data[:, 0], processing_data[:, 1:]
        symptoms = np.unique(symptoms)
        diseases = np.unique(diseases)
        symptoms = symptoms[symptoms != 'n/a']
        diseases = diseases[diseases != 'n/a']
        self.symptoms_list = symptoms
        self.diseases_list = diseases
        symptoms = np.vectorize(self.cleaner)(symptoms)
        self.symptoms_encoder = dict(zip(symptoms, np.arange(symptoms.shape[0])))
        self.diseases_encoder = dict(zip(diseases, np.arange(diseases.shape[0])))
        x = []
        for row in processing_data[:, 1:]:
            x.append(self.encode_symptoms(row))
        x = np.array(x)
        y = self.get_indexes(self.diseases_encoder, processing_data[:, 0])
        self.model = xgb.XGBClassifier(**params)
        self.model.fit(x, y, eval_set=[(x, y)], verbose=False)

    def predict(self, symptoms: list, min_matching_ratio=1):
        processed_symptoms = []
        for s in symptoms:
            cleaned = self.cleaner(s)
            if cleaned not in self.symptoms_encoder:
                print('warning:', s, 'is not a known symptom')
                if min_matching_ratio < 1:
                    closest_symptom, similarity = self.closest_match(cleaned)
                    if similarity > min_matching_ratio:
                        print('\t', 'matched to', closest_symptom,
                              'with word similarity:', np.round(similarity, 3))
                        print()
                        cleaned = closest_symptom
            processed_symptoms.append(cleaned)

        predictions = self.model.predict_proba([self.encode_symptoms(processed_symptoms)])
        predictions_dict = dict(zip(
            self.diseases_list,
            predictions[0]
        ))
        return dict(sorted(predictions_dict.items(), key=lambda x: x[1], reverse=True))

    def closest_match(self, query):
        similarities = np.vectorize(lambda x: Levenshtein.ratio(x, query))(list(self.symptoms_encoder.keys()))
        most_similar_ind = np.argmax(similarities)
        return self.symptoms_list[most_similar_ind], similarities[most_similar_ind]

    def encode_symptoms(self, symptoms):
        cleaned = np.vectorize(self.cleaner)(symptoms)
        one_hot = np.zeros(len(self.symptoms_encoder) + 1)
        indexed_arr = self.get_indexes(self.symptoms_encoder, np.array(cleaned), default_value=-1) + 1
        one_hot[indexed_arr] = 1
        return one_hot[1:]

    def save_model(self, savepath=None):
        if savepath is None:
            current_path = os.getcwd()
            models_path = os.path.join(current_path, 'models')
            if not os.path.exists(models_path):
                os.mkdir(models_path)
            savepath = models_path
        self.model.save_model(os.path.join(savepath, 'classifier.xgb'))
        pickle.dump(self.symptoms_encoder, open(os.path.join(savepath, 'symptoms.dict'), 'wb'))
        pickle.dump(self.symptoms_list, open(os.path.join(savepath, 'symptoms.list'), 'wb'))
        pickle.dump(self.diseases_encoder, open(os.path.join(savepath, 'diseases.dict'), 'wb'))
        pickle.dump(self.diseases_list, open(os.path.join(savepath, 'diseases.list'), 'wb'))

    def load_model(self, load_path=None):
        if load_path is None:
            current_path = os.getcwd()
            models_path = os.path.join(current_path, 'models')
            if not os.path.exists(models_path):
                os.mkdir(models_path)
            load_path = models_path
        self.model = xgb.XGBClassifier()
        self.model.load_model(os.path.join(load_path, 'classifier.xgb'))
        self.symptoms_encoder = pickle.load(open(os.path.join(load_path, 'symptoms.dict'), 'rb'))
        self.symptoms_list = pickle.load(open(os.path.join(load_path, 'symptoms.list'), 'rb'))
        self.diseases_encoder = pickle.load(open(os.path.join(load_path, 'diseases.dict'), 'rb'))
        self.diseases_list = pickle.load(open(os.path.join(load_path, 'diseases.list'), 'rb'))

    @staticmethod
    def cleaner(word):
        stop_words = [' ', '_', '-', "'", '"']
        new_word = word
        for st in stop_words:
            new_word = new_word.replace(st, '')
        return new_word.lower()

    @staticmethod
    def get_indexes(encoder, arr, default_value=-1):
        return np.vectorize(lambda x: encoder.get(x, default_value))(arr)


def detect_disease(symptoms: list):
    disease_detection = DiseaseDetection()
    # disease_detection.train('./data/dataset.csv')
    # disease_detection.save_model()
    disease_detection.load_model("services\\ai\\models\\")
    return disease_detection.predict(symptoms, min_matching_ratio=0)
    # EXAMPLE:
    # symptoms_list = ['Cough', 'chest pain', 'breath issues', 'anxiety', 'throat pain', 'mucoid_putum']
    # print(detect_disease(symptoms_list))
