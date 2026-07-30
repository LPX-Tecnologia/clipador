#!/usr/bin/env bash
set -e
exec uvicorn app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
