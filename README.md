# SignLanguage

A real-time sign language recognition web app built with Flask, OpenCV, MediaPipe, TensorFlow, and scikit-learn.

## Features

- User signup and login
- Live hand gesture recognition
- Real-time prediction updates
- Local SQLite user storage
- Flask-based web interface
- Ready-to-run local setup
- Basic deployment files included

## Tech Stack

- Python 3.11
- Flask
- OpenCV
- MediaPipe
- TensorFlow
- scikit-learn
- SQLite

## Project Structure

```text
SignLanguage/
├── app.py
├── wsgi.py
├── requirements.txt
├── requirements.deploy.txt
├── start_local.cmd
├── rebuild_venv.cmd
├── users.db
├── models/
│   └── sign_model.pkl
├── templates/
│   ├── dashboard.html
│   ├── index.html
│   ├── login.html
│   └── signup.html
├── Dockerfile
├── Procfile
└── DEPLOY.md
