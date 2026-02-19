#!/usr/bin/env bash
set -e

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🗄️  Initializing database..."
python init_db.py

echo "✅ Build complete."
