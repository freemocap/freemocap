# Check system information
systeminfo || Write-Host "Unable to fetch system information"

# Ensure Python 3.11 is installed and added to your PATH.
Write-Host "Ensure Python 3.11 is installed and added to your PATH."

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -e .

# Freeze dependencies to requirements.txt
pip freeze > requirements.txt

# Remove opencv-python dependency
(Get-Content requirements.txt) -notmatch 'opencv-python' | Set-Content requirements.txt

# Download PyApp
Invoke-WebRequest -Uri "https://github.com/ofek/pyapp/releases/download/v0.22.0/source.zip" -OutFile "pyapp.zip"

# Unzip PyApp
Expand-Archive -Path "pyapp.zip" -DestinationPath "."

# List directory contents
Get-ChildItem -Path "."

# Set environment variables for PyApp
$env:PYAPP_PROJECT_NAME = "freemocap"
$env:PYAPP_PROJECT_VERSION = "v1.4.7"
$env:PYAPP_PYTHON_VERSION = "3.11"
$env:PYAPP_PROJECT_DEPENDENCY_FILE = (Resolve-Path "requirements.txt").Path
$env:PYAPP_EXEC_SCRIPT = (Resolve-Path "freemocap\__main__.py").Path
$env:PYAPP_PIP_EXTRA_ARGS = "--no-deps"
$env:PYAPP_EXPOSE_ALL_COMMANDS = "true"

# Build and install PyApp (requires Rust and Cargo)
# Install Rust from https://rustup.rs/ if not installed
cd pyapp-v0.22.0
cargo build --release
cargo install pyapp --force --root (Get-Location).Path
cd ..

# Rename the executable
Rename-Item -Path ".\bin\pyapp.exe" -NewName "freemocap_app.exe"

# Install Rcedit with Chocolatey
# Ensure Chocolatey is installed on your system
choco install rcedit -y

# Set executable icon
rcedit "freemocap_app.exe" --set-icon "freemocap/assets/logo/freemocap_skelly_logo.ico"

Write-Host "freemocap_app.exe has been created with the specified icon."