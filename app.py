import base64
import os
import pickle
import sqlite3
import sys
import threading
import time
import webbrowser
from collections import Counter, deque

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mediapipe as mp
except ImportError:
    mp = None

try:
    import numpy as np
except ImportError:
    np = None


APP_HOST = os.environ.get("HOST", os.environ.get("SIGN_APP_HOST", "127.0.0.1"))
APP_PORT = int(os.environ.get("PORT", os.environ.get("SIGN_APP_PORT", "5000")))

if getattr(sys, "frozen", False):
    RESOURCE_ROOT = sys._MEIPASS
    APP_ROOT = os.path.dirname(sys.executable)
    app = Flask(
        __name__,
        template_folder=os.path.join(RESOURCE_ROOT, "templates"),
        static_folder=os.path.join(RESOURCE_ROOT, "static"),
    )
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_ROOT = APP_ROOT
    app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "sign_secret_key")

DB_NAME = os.path.join(APP_ROOT, "users.db")
MODEL_PATH = os.path.join(RESOURCE_ROOT, "models", "sign_model.pkl")

RUNTIME = {
    "available": False,
    "message": "Live recognition is unavailable.",
}

model = None
hands = None
mp_hands = None
runtime_lock = threading.Lock()


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT,
            password TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def set_runtime_unavailable(message):
    RUNTIME["available"] = False
    RUNTIME["message"] = message


def init_runtime():
    global model, hands, mp_hands

    missing_packages = [
        name
        for name, module in (
            ("opencv-python", cv2),
            ("mediapipe", mp),
            ("numpy", np),
        )
        if module is None
    ]
    if missing_packages:
        set_runtime_unavailable(
            "Live recognition is unavailable because these packages are missing: "
            + ", ".join(missing_packages)
        )
        return

    if not os.path.exists(MODEL_PATH):
        set_runtime_unavailable(f"Model file not found at {MODEL_PATH}.")
        return

    try:
        with open(MODEL_PATH, "rb") as model_file:
            model = pickle.load(model_file)
    except Exception as exc:
        set_runtime_unavailable(f"Model failed to load: {exc}")
        return

    try:
        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    except Exception as exc:
        set_runtime_unavailable(f"Mediapipe failed to initialize: {exc}")
        return

    RUNTIME["available"] = True
    RUNTIME["message"] = "Live recognition is ready."


def extract_features(hand_landmarks):
    features = []
    for landmark in hand_landmarks.landmark:
        features.extend([landmark.x, landmark.y, landmark.z])
    return np.array(features).reshape(1, -1)


def decode_frame(frame_data):
    if not frame_data:
        raise ValueError("No frame data received.")

    if "," in frame_data:
        frame_data = frame_data.split(",", 1)[1]

    image_bytes = base64.b64decode(frame_data)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Frame could not be decoded.")

    return frame


def predict_frame(frame):
    if not RUNTIME["available"]:
        return {
            "ok": False,
            "prediction": RUNTIME["message"],
            "confidence": 0.0,
            "message": RUNTIME["message"],
        }

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    with runtime_lock:
        results = hands.process(frame_rgb)

    if not results.multi_hand_landmarks:
        return {
            "ok": True,
            "prediction": "No hand detected",
            "confidence": 0.0,
            "message": "Show one clear hand to the camera.",
        }

    try:
        hand_landmarks = results.multi_hand_landmarks[0]
        features = extract_features(hand_landmarks)
        probabilities = model.predict_proba(features)[0]
        prediction_index = int(np.argmax(probabilities))
        predicted_label = str(model.classes_[prediction_index])
        predicted_confidence = float(probabilities[prediction_index])
    except Exception as exc:
        return {
            "ok": False,
            "prediction": "Prediction error",
            "confidence": 0.0,
            "message": f"Prediction failed: {exc}",
        }

    return {
        "ok": True,
        "prediction": predicted_label,
        "confidence": round(predicted_confidence, 4),
        "message": "Prediction successful.",
    }


@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html", runtime=RUNTIME)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("signup"))

        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password),
            )
            conn.commit()
            conn.close()

            flash("Account created successfully.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user"] = username
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        user=session["user"],
        runtime=RUNTIME,
    )


@app.route("/predict_frame", methods=["POST"])
def predict_frame_route():
    if "user" not in session:
        return jsonify({"ok": False, "message": "Unauthorized."}), 401

    if not RUNTIME["available"]:
        return jsonify(
            {
                "ok": False,
                "prediction": RUNTIME["message"],
                "confidence": 0.0,
                "message": RUNTIME["message"],
            }
        ), 503

    payload = request.get_json(silent=True) or {}
    frame_data = payload.get("frame")
    history = payload.get("history", [])

    try:
        frame = decode_frame(frame_data)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    result = predict_frame(frame)

    if result["ok"] and result["confidence"] > 0:
        history = [item for item in history if isinstance(item, str)][-4:]
        history.append(result["prediction"])
        most_common = Counter(history).most_common(1)[0][0]
        result["prediction"] = most_common
        result["history"] = history
    else:
        result["history"] = []

    return jsonify(result)


@app.route("/health")
def health():
    return {
        "status": "ok",
        "runtime_available": RUNTIME["available"],
        "message": RUNTIME["message"],
    }


def open_browser():
    webbrowser.open(f"http://{APP_HOST}:{APP_PORT}")


init_db()
init_runtime()


if __name__ == "__main__":
    if os.environ.get("SIGN_APP_OPEN_BROWSER", "0") == "1":
        threading.Timer(1.5, open_browser).start()

    app.run(host=APP_HOST, port=APP_PORT, debug=False)
