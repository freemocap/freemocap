@echo off

REM Create virtual environment
python -m venv venv

REM Activate virtual environment
CALL venv\Scripts\activate.bat

REM Install Python requirements
pip install -r requirements.txt

REM (Optional) Build with PyInstaller
pyinstaller --onefile src-python/main.py

echo Installation and setup complete!
pause
