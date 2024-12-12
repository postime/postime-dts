# PosTime API

API required for the [frontend](https://github.com/max-ionov/postil-time-machine-viewer)

## Project Setup

It is recommended to use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To deactivate the virtual environment:
```bash
deactivate
```

## Starting the API for development

```bash
python app.py
```

## Starting the API for production

A recommended way to use the API in production is via gunicorn, a WSGI server, ideally in combination with nginx.
Specific deployment details will vary on the system and the toolchain used to deploy services, but in a nutshell the command that starts the server will be similar to

```bash
gunicorn wsgi:app --bind 0.0.0.0:8080 --workers 4
```

