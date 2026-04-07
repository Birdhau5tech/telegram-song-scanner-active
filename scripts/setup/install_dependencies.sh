#!/bin/bash
# Install all dependencies for WhatsApp Song Scanner

set -e

echo "Installing WhatsApp Song Scanner dependencies..."

# CHECK PYTHON VERSION
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

# CREATE VIRTUAL ENVIRONMENT
echo "Creating virtual environment..."
python3 -m venv venv

# ACTIVATE VIRTUAL ENVIRONMENT
source venv/bin/activate

# UPGRADE PIP
echo "Upgrading pip..."
pip install --upgrade pip

# INSTALL REQUIREMENTS
echo "Installing Python packages..."
pip install -r requirements.txt
pip install -r requirements-dev.txt

# CREATE DATA DIRECTORIES
echo "Creating data directories..."
mkdir -p data/logs
mkdir -p data/cache
mkdir -p data/temp
mkdir -p data/exports

echo ""
echo "✅ Dependencies installed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure"
echo "2. Run './scripts/setup/setup_database.sh' to initialize database"
echo "3. Run 'source venv/bin/activate' to activate virtual environment"
echo "4. Run 'python -m src.main' to start the application"
