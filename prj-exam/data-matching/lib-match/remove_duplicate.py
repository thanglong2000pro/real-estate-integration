from sklearn.feature_extraction.text import TfidfVectorizer
import re
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from joblib import dump
from datetime import datetime
from datetime import date


class remove_duplicate:
    def __init__(self, max_area_diff=0.03, max_price_diff=0.03, max_time_diff=1728000, min_thres=0.8):
        self.max_area_diff = max_area_diff
        self.max_price_diff = max_price_diff
        self.max_time_diff = max_time_diff
        self.min_thres = min_thres
        self.feature_extractor: TfidfVectorizer = None

    def get_data_to_train(self):
        path_data = '/home/darkknight/real-estate-integration/prj-exam/schema-matching/data.csv'
        df = pd.read_csv(path_data, encoding='utf-8')
        df = df.drop(["Unnamed: 0"], axis=1)
        return df

    def preprocess(self, text):
        text = re.sub("\d+[\.-]\d+[\.-]\d+", " dien_thoai ", text)
        text = re.sub("[mM]\s*2", " met_vuong ", text)
        text = re.sub("\d+([\.,]\d+)?", " gia_tri_so ", text)
        return text

    def train_feature_extractor(self):
        self.feature_extractor = TfidfVectorizer(lowercase=True, preprocessor=self.preprocess, ngram_range=(1, 1), max_df=1.0,
                                                 min_df=5)

        df = self.get_data_to_train()
        df["description"].fillna('None', inplace=True)
        self.feature_extractor.fit(df["description"])

    def check_constrain(self, item1, item2):
        # if abs(item1["date"] - item2["date"]) > self.max_time_diff:
        #     return False
        if abs((datetime.strptime(item1["date"], '%d/%m/%Y').date() - datetime.strptime(item2["date"], '%d/%m/%Y').date()).days*24*60*60) > self.max_time_diff:
            return False
        if abs(item1["square"] - item2["square"])/min(item1["square"], item2["square"]) > self.max_area_diff:
            return False
        if abs(item1["price"] - item2["price"])/min(item1["price"], item2["price"]) > self.max_price_diff:
            return False
        return True

    def remove_inside(self, df):
        X_vectors = self.feature_extractor.transform(df["description"])
        similarity_scores = cosine_similarity(X_vectors)
        size = len(df)
        drop_set = set()
        for i in range(size):
            for j in range(i+1, size):
                if similarity_scores[i, j] >= self.min_thres:
                    item1 = df.iloc[i]
                    item2 = df.iloc[j]
                    if self.check_constrain(item1, item2):
                        if i not in drop_set and j not in drop_set:
                            drop_set.add(j)
                        if i not in drop_set:
                            drop_set.add(i)
                        elif j not in drop_set:
                            drop_set.add(j)
        all = set(range(size))
        keep = all.difference(drop_set)
        keep = list(keep)
        return df.iloc[keep]

    def get_old_data(self, ward, district, province, type, min_time, max_time):
        path_data = '/home/darkknight/real-estate-integration/prj-exam/schema-matching/data.csv'
        df = pd.read_csv(path_data, encoding='utf-8')
        df = df.drop(["Unnamed: 0"], axis=1)
        return df

    def remove_outside(self, old_df, new_df):
        old_size = len(old_df)
        new_size = len(new_df)
        df = pd.concat([old_df, new_df], ignore_index=True)
        X_vectors = self.feature_extractor.transform(df["description"])
        similarity_scores = cosine_similarity(X_vectors)
        drop_set = set()
        for i in range(new_size):
            for j in range(old_size):
                if similarity_scores[j, old_size+i] >= self.min_thres:
                    item1 = old_df.iloc[j]
                    item2 = new_df.iloc[i]
                    if self.check_constrain(item1, item2):
                        drop_set.add(i)
                        break
        all = set(range(new_size))
        keep = all.difference(drop_set)
        keep = list(keep)
        df = new_df.iloc[keep]
        return df

    def remove_subset(self, new_df: pd.DataFrame, ward, district, province, type):
        try:
            new_df.reset_index(inplace=True)
            if len(new_df) > 1:
                new_df = self.remove_inside(new_df)
            min_time = np.min(new_df["date"])
            max_time = np.max(new_df["date"])
            min_time -= self.max_time_diff
            max_time += self.max_time_diff
            old_df = self.get_old_data(
                ward, district, province, type, min_time, max_time)
            if old_df is not None:
                new_df = self.remove_outside(old_df, new_df)
            return new_df
        except Exception as ex:
            print("Exception occurs in remove_subset", ex)

    def remove_duplicate(self, df: pd.DataFrame):
        if len(df) > 0:
            df.set_index(["property_ward", "property_district",
                         "property_province", "property_type"], inplace=True)
            df.sort_index(inplace=True)
            result = []
            for ward, district, province, type in set(df.index):
                df_sub = df.loc[[(ward, district, province, type)]]
                df_sub = self.remove_subset(
                    df_sub, ward, district, province, type)
                result.append(df_sub)
            df = pd.concat(result, ignore_index=True)
            return df
        else:
            return None

    def save(self):
        dump(self, "RemoveDuplicate.lib")
