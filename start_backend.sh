#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🌾 Stitch Tamil Finance Backend - Flask & MySQL Server"
echo "=========================================================="

if [ -f "$DIR/venv/bin/python3" ]; then
    PYTHON="$DIR/venv/bin/python3"
    echo "📦 Using virtualenv Python: $PYTHON"
else
    PYTHON="python3"
    echo "📦 Using system Python: $PYTHON"
fi

# Check for required packages
$PYTHON -c "import flask, flask_cors, pymysql, dotenv" 2>/dev/null || {
    echo "⚠️  Missing dependencies. Installing requirements..."
    $PYTHON -m pip install -r requirements.txt
}

echo "🚀 Starting Flask API on http://0.0.0.0:5000..."
exec $PYTHON app.py
