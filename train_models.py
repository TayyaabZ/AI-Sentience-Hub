import os
import json
import time
import numpy as np
import joblib
from sklearn.datasets import fetch_openml
from sklearn.preprocessing import StandardScaler
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix

if __name__ == "__main__":
    print("Fetching MNIST dataset...")
    mnist = fetch_openml("mnist_784", version=1, as_frame=False, parser="liac-arff")
    X = mnist.data.astype(np.float32)
    y = mnist.target.astype(int)

    X_train, X_test = X[:60000], X[60000:]
    y_train, y_test = y[:60000], y[60000:]

    print("Fitting scaler...")
    scaler = StandardScaler()
    scaler.fit(X_train)
    X_train = scaler.transform(X_train)
    X_test = scaler.transform(X_test)

    os.makedirs("models", exist_ok=True)
    joblib.dump(scaler, "models/scaler.pkl")
    print("Scaler saved to models/scaler.pkl")

    results = {}

    print("[1/3] Training Naive Bayes...")
    nb = GaussianNB()
    t0 = time.time()
    nb.fit(X_train, y_train)
    t1 = time.time()
    print("[1/3] Done.")
    joblib.dump(nb, "models/naive_bayes.pkl")
    y_pred = nb.predict(X_test)
    results["naive_bayes"] = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": [round(float(v), 4) for v in precision_score(y_test, y_pred, average=None, zero_division=0)],
        "recall": [round(float(v), 4) for v in recall_score(y_test, y_pred, average=None, zero_division=0)],
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "train_time_s": round(t1 - t0, 2),
    }

    print("[2/3] Training Decision Tree...")
    dt = DecisionTreeClassifier(max_depth=20, random_state=42)
    t0 = time.time()
    dt.fit(X_train, y_train)
    t1 = time.time()
    print("[2/3] Done.")
    joblib.dump(dt, "models/decision_tree.pkl")
    y_pred = dt.predict(X_test)
    results["decision_tree"] = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": [round(float(v), 4) for v in precision_score(y_test, y_pred, average=None, zero_division=0)],
        "recall": [round(float(v), 4) for v in recall_score(y_test, y_pred, average=None, zero_division=0)],
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "train_time_s": round(t1 - t0, 2),
    }

    print("[3/3] Training KNN (20k subset)...")
    knn = KNeighborsClassifier(n_neighbors=5, algorithm="ball_tree", n_jobs=-1)
    t0 = time.time()
    knn.fit(X_train[:20000], y_train[:20000])
    t1 = time.time()
    print("[3/3] Done.")
    joblib.dump(knn, "models/knn.pkl")
    y_pred = knn.predict(X_test)
    results["knn"] = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": [round(float(v), 4) for v in precision_score(y_test, y_pred, average=None, zero_division=0)],
        "recall": [round(float(v), 4) for v in recall_score(y_test, y_pred, average=None, zero_division=0)],
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "train_time_s": round(t1 - t0, 2),
    }

    with open("models/accuracy.json", "w") as f:
        json.dump(results, f, indent=2)

    joblib.dump((X_test, y_test), "models/knn_train_data.pkl")

    print()
    print("=== MODEL ACCURACY SUMMARY ===")
    print(f"Naive Bayes:    {results['naive_bayes']['accuracy'] * 100:.2f}%")
    print(f"Decision Tree:  {results['decision_tree']['accuracy'] * 100:.2f}%")
    print(f"KNN (20k):      {results['knn']['accuracy'] * 100:.2f}%")
    print("Models saved to models/")
