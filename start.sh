#!/bin/bash

# Exit immediately if any command fails
set -e

# Project root directory
PROJECT_ROOT="/Users/fhyfhy/Desktop/ifrs9-ecl-analytics"

echo "============================================="
echo "Starting IFRS 9 ECL Calculator & Dashboard Setup"
echo "============================================="

# 1. Navigate to project root
cd "$PROJECT_ROOT"

# 2. Setup Virtual Environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment 'venv'..."
    python3 -m venv venv
else
    echo "Virtual environment 'venv' already exists."
fi

# 3. Activate Virtual Environment
echo "Activating virtual environment..."
source venv/bin/activate

# 4. Install Dependencies
echo "Installing dependencies..."
# Use python -m pip to ensure the correct pip is used
python3 -m pip install --upgrade pip
python3 -m pip install fastapi uvicorn pandas numpy scikit-learn scipy

# 5. Start Backend Server
echo ""
echo "--------------------------------------------------------"
echo "Backend Server starting on http://127.0.0.1:8000"
echo "--------------------------------------------------------"
echo "To view the dashboard, open the following file in your browser:"
echo "file://${PROJECT_ROOT}/frontend/index.html"
echo "--------------------------------------------------------"
echo ""

python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
