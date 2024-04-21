#!/bin/bash

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
python3 -m pip install --upgrade pip

echo "Installing Python requirements..."
pip install -r requirements.txt

echo "Building with PyInstaller..."
pyinstaller --onefile src-python/main.py

echo "Installation and setup complete!"