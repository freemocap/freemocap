@echo off

echo Create virtual environment
CALL python -m venv venv

echo Activate virtual environment
CALL venv\Scripts\activate.bat

echo Upgrade pip
CALL python -m pip install --upgrade pip

echo Install Python requirements
CALL pip install -r requirements.txt

echo  Build with PyInstaller
CALL pyinstaller --onefile src-python/main.py

echo Installation and setup complete!

