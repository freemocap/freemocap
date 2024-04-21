#!/bin/bash

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
python3 -m pip install --upgrade pip

# Install Python requirements
pip install -r requirements.txt

# (Optional) Build with PyInstaller
pyinstaller --onefile main.py

echo "Installation and setup complete!"