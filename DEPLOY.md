# Deployment

## Current architecture limitation

This project can be deployed as a Flask web app, but the live recognition feature is not cloud-ready yet.

The current implementation uses `cv2.VideoCapture(0)` in the server process. In a cloud deployment, that reads the server's local camera, not the browser user's webcam. On a normal hosted service, `video_feed` will therefore stay unavailable unless the host has a directly attached camera and the required ML packages are installed.

The deployed app still works as:

- a hosted Flask site
- signup/login demo
- dashboard shell
- health-check endpoint at `/health`

## Files added for deployment

- `Dockerfile`
- `.dockerignore`
- `wsgi.py`
- `Procfile`
- `requirements.deploy.txt`

## Local container build

```bash
docker build -t sign-language-app .
docker run --rm -p 5000:5000 -e PORT=5000 -e SECRET_KEY=change-me sign-language-app
```

Open:

```text
http://127.0.0.1:5000
```

## Generic cloud deploy

Use either:

- a Docker-based web service
- a Python web service that supports `Procfile`

### Required environment variables

- `PORT`
- `SECRET_KEY`

### Start command

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 wsgi:app
```

## Health check

Use:

```text
/health
```

## To make live recognition cloud-ready

The webcam pipeline needs to move from server-side OpenCV capture to browser-side capture. The usual path is:

1. Capture frames from the browser using WebRTC or `getUserMedia`.
2. Send frames to the backend over HTTP/WebSocket.
3. Run inference on uploaded frames instead of `VideoCapture(0)`.
4. Return predictions to the browser.

Until that refactor is done, a cloud deployment is only a hosted web shell, not a full remote sign-recognition app.
