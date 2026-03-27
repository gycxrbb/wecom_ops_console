#!/usr/bin/env bash
set -e
python -m venv .venv || true
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
