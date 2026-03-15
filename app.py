import os
import sys
import time
import pickle
import sqlite3
import threading
import webbrowser
from collections import deque

from flask import Flask, Response, flash, redirect, render_template, request, session, stream_with_context, url_for

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
mp_drawing = None
cap = None

current_prediction = "Live recognition unavailable"
current_confidence = 0.0
prediction_history = deque(maxlen=5)


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
    global current_prediction, current_confidence

    RUNTIME["available"] = False
    RUNTIME["message"] = message
    current_prediction = message
    current_confidence = 0.0


def init_runtime():
    global cap, hands, model, mp_hands, mp_drawing

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
        hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.5)
        mp_drawing = mp.solutions.drawing_utils
    except Exception as exc:
        set_runtime_unavailable(f"Mediapipe failed to initialize: {exc}")
        return

    try:
        cap = cv2.VideoCapture(0)
    except Exception as exc:
        set_runtime_unavailable(f"Camera initialization failed: {exc}")
        return

    if cap is None or not cap.isOpened():
        set_runtime_unavailable("Camera not detected or unavailable on this machine.")
        return

    RUNTIME["available"] = True
    RUNTIME["message"] = "Live recognition is ready."


def extract_features(hand_landmarks):
    features = []
    for landmark in hand_landmarks.landmark:
        features.extend([landmark.x, landmark.y, landmark.z])
    return np.array(features).reshape(1, -1)


def generate_frames():
    global current_prediction, current_confidence

    while True:
        if not RUNTIME["available"] or cap is None:
            time.sleep(0.5)
            continue

        success, frame = cap.read()
        if not success:
            current_prediction = "Waiting for camera frame"
            current_confidence = 0.0
            time.sleep(0.1)
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        if results.multi_hand_landmarks:
            try:
                hand_landmarks = results.multi_hand_landmarks[0]
                features = extract_features(hand_landmarks)
                probabilities = model.predict_proba(features)[0]
                prediction_index = np.argmax(probabilities)
                predicted_label = model.classes_[prediction_index]
                predicted_confidence = float(probabilities[prediction_index])

                prediction_history.append((predicted_label, predicted_confidence))

                labels = [item[0] for item in prediction_history]
                confidences = [item[1] for item in prediction_history]

                current_prediction = max(set(labels), key=labels.count)
                current_confidence = sum(confidences) / len(confidences)

                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            except Exception as exc:
                current_prediction = f"Prediction error: {exc}"
                current_confidence = 0.0
        else:
            current_prediction = "Waiting for hand gesture"
            current_confidence = 0.0

        frame_ok, buffer = cv2.imencode(".jpg", frame)
        if not frame_ok:
            time.sleep(0.1)
            continue

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


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
        prediction=current_prediction,
    )


@app.route("/video_feed")
def video_feed():
    if not RUNTIME["available"]:
        return Response(RUNTIME["message"], status=503, mimetype="text/plain")

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/prediction_feed")
def prediction_feed():
    def generate():
        global current_prediction, current_confidence

        while True:
            data = f"{current_prediction}|{current_confidence:.2f}"
            yield f"data:{data}\n\n"
            time.sleep(0.5)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


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
