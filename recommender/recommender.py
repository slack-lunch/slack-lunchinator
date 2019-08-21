from datetime import date

import majka
import re

from django.db.models import Count
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from imblearn.under_sampling import RandomUnderSampler

import numpy as np

from lunchinator.models import Restaurant, Meal, User

import os

NLP_DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'nlp_data')


class Recommender:
    REGEX_WORDS = r'\b\w+\b'

    def __init__(self, user: User):
        self.user = user
        self._morph = self._get_morph()
        self._stopwords = self._get_stopwords()

    def get_recommendations(self, n=10):
        """
        :param n: number of suggestions
        :return: list of tuples (meal, relevance)
        """

        selecttions_q = self.user.selections.filter(recommended=False)
        selected_meals = Meal.objects.filter(id__in=selecttions_q.values_list('meal', flat=True)).all()

        not_selected_meals = Meal.objects \
            .filter(date__in=selecttions_q.values_list('meal__date', flat=True)) \
            .exclude(id__in=selecttions_q.values_list('meal__id', flat=True)) \
            .all()

        if not selected_meals or len(selected_meals) < 10:
            # Recommend based on others' selections
            selected_meals_q = Meal.objects.annotate(selected=Count('selections')).filter(selected__gt=0)
            selected_meals = selected_meals_q.all()

            if len(selected_meals) < 10:
                return []

            not_selected_meals = Meal.objects \
                .filter(date__in=selected_meals_q.values_list('date', flat=True)) \
                .exclude(id__in=selected_meals_q.values_list('id', flat=True)) \
                .all()

        words = list(set((w for m in Meal.objects.all() for w in self._process_meal_name(m.name))))
        restaurants = Restaurant.objects.values_list('id', flat=True)

        words_indecies = {w: i for i, w in enumerate(words)}
        restaurants_indecies = {r: i for i, r in enumerate(restaurants, len(words))}

        selected_meals_df = self._transform_to_dataset(selected_meals, words_indecies, restaurants_indecies, 1)
        not_selected_meals_df = self._transform_to_dataset(not_selected_meals, words_indecies, restaurants_indecies, 0)
        train_meals_df = np.concatenate((selected_meals_df, not_selected_meals_df))

        todays_meals = Meal.objects.filter(date=date.today())
        todays_meals_df = self._transform_to_dataset(todays_meals, words_indecies, restaurants_indecies)

        X, y = train_meals_df[:, :-1], train_meals_df[:, -1]
        clf = self._get_trained_model(X, y)

        predictions = self._get_predictions(todays_meals_df, clf)

        return sorted(zip(todays_meals, predictions), key=lambda m: m[1], reverse=True)[:n]

    def _process_meal_name(self, meal):
        words = re.findall(self.REGEX_WORDS, meal)
        words_clean = set()

        for word in words:
            mf = self._morph.find(word)
            if len(mf) > 0 and 'lemma' in mf[0]:
                word_lemma = mf[0]['lemma']
                if word_lemma.lower() not in self._stopwords:
                    words_clean.add(word_lemma.lower())

        return words_clean

    def _transform_to_dataset(self, meals, words_indecies, restaurants_indecies, label=None):
        X = np.zeros((len(meals), len(words_indecies) + len(restaurants_indecies) + (1 if label is not None else 0)))

        for i, m in enumerate(meals):
            r_idx = restaurants_indecies[m.restaurant.id]
            X[i, r_idx] = 1
            for w in self._process_meal_name(m.name):
                w_idx = words_indecies[w]
                X[i, w_idx] = 1

        if label is not None:
            X[:, -1] = label

        return X

    @staticmethod
    def _get_morph():
        morph = majka.Majka(os.path.join(NLP_DATA_PATH, 'majka.w-lt'))
        morph.tags = False
        morph.first_only = True
        morph.negative = "ne"
        morph.flags |= majka.IGNORE_CASE  # ignore the word case whatsoever
        return morph

    @staticmethod
    def _get_stopwords():
        with open(os.path.join(NLP_DATA_PATH, 'stopwords-cs.txt'), 'r', -1, 'utf-8') as infile:
            return list(map(str.strip, infile))

    @staticmethod
    def _get_trained_model(X, y):
        rus = RandomUnderSampler(random_state=0)
        X_resampled, y_resampled = rus.fit_sample(X, y)

        model = LinearSVC()
        clf = CalibratedClassifierCV(model, cv=5)
        clf.fit(X_resampled, y_resampled)
        return clf

    @staticmethod
    def _get_predictions(X, clf):
        return [clf.predict_proba(X[(i,), :])[0][1] for i, meal in enumerate(X)]
