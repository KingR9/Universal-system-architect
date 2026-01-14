#!/bin/bash
# Setup script for Universal Workflow Intelligence Engine

set -e  # Exit on error

echo "Setting up Universal Workflow Intelligence Engine..."
echo

# Check Python version
echo "Checking Python version..."
python3 --version || {
    echo "Python 3 is required but not installed."
    exit 1
}

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Setup complete!"
echo
echo "To get started:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Validate a workflow: python3 tools/workflow_validator.py workflow_map.json"
echo "  3. Run dry-run test: python3 tools/dry_run_executor.py workflow_map.json"
echo
echo "Read README.md for full documentation"
echo
