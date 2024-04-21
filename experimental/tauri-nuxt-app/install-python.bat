@echo off

REM Create virtual environment
CALL python -m venv venv

REM Activate virtual environment
CALL venv\Scripts\activate.bat

REM Upgrade pip
CALL python -m pip install --upgrade pip

REM Install Python requirements
CALL pip install -r requirements.txt

REM (Optional) Build with PyInstaller
CALL pyinstaller  --onefile src-python/main.py

echo Installation and setup complete!

