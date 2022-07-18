<p align="center">
    <img src="https://raw.githubusercontent.com/freemocap/freemocap/main/logo/freemocap-logo-black-border.svg" height="64" alt="Project Logo">
</p>
<h3 align="center">freemocap</h3>
<p align="center">📝 The FreeMoCap Project: A free-and-open-source, hardware-and-software-agnostic, minimal-cost, research-grade, motion capture system and platform for decentralized scientific research, education, and training</p>
<p align="center">
    <a href="https://github.com/freemocap/freemocap/releases">
        <img src="https://img.shields.io/github/downloads/freemocap/freemocap/total.svg" alt="GitHub Downloads">
    </a>
    <a href="https://github.com/freemocap/freemocap/releases/latest">
        <img src="https://img.shields.io/github/release/freemocap/freemocap.svg" alt="Latest Release">
    </a>
    <a href="https://github.com/freemocap/freemocap/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/license-AGPL-blue.svg" alt="MIT License">
    </a>
    <a href="https://github.com/freemocap/freemocap/issues">
        <img src="https://img.shields.io/badge/contributions-welcome-ff69b4.svg" alt="Contributions Welcome">
    </a>
</p>

## Pardon our dust as we transtion to the `alpha` phase of this project!

We are currently in the process of transitioning from the  `pre-alpha` code base into the fully refactored `alpha` code base. Some things might be a bit clunky while we make the transition, but I promise it will be worth it!

If you would like to access the `pre-alpha` code, you can find it here under the release tag `v0.0.54` [here](https://github.com/freemocap/freemocap/releases/tag/v0.0.54)

## Pre-requisites

### General
- [Python 3.9](https://www.python.org/downloads/release/python-390/)
- [Git](https://www.atlassian.com/git/tutorials/install-git)
- [Blender](https://www.blender.org/download/)
- At least 2 simple webcameras (more cameras, better quality)
    - [$10 camera here](https://www.amazon.com/1080P-Full-Webcam-Microphone-Conferencing/dp/B09JFPFVY4/ref=asc_df_B09JFPFVY4/?tag=hyprod-20&linkCode=df0&hvadid=563548498710&hvpos=&hvnetw=g&hvrand=17033983634274965573&hvpone=&hvptwo=&hvqmt=&hvdev=c&hvdvcmdl=&hvlocint=&hvlocphy=9028321&hvtargid=pla-1629009316502&psc=1)
- Each Camera must have a clean, unobstructed view of a Charuco board during initialization.
    

### Easy MacOSX Install Instructions
1. Install the Homebrew Package manager (Skip this step if you already have it)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
2. Install Git (Skip this step if you already have it)
```bash
brew install git
```
3. Get the source code.
```bash
git clone https://github.com/freemocap/freemocap.git
```
4. Install the dependencies
```bash
brew install blender ffmpeg
```
5. Skip to our Getting Started section of the README below.

### Easy Windows Install Instructions
1. Install Chocolatey. Open Powershell, and run the below command
```commandline
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```
2. Install Git
```commandline
choco install git
```
3. Get the source code.
```bash
git clone https://github.com/freemocap/freemocap.git
```
4. Install the dependencies
```commandline
choco install blender ffmpeg
```
5. Skip to our Getting Started section of the README below.

## Getting Started

Navigate into the newly cloned freemocap folder
```bash
cd freemocap
```

Install the Python Dependencies (into a virtual environment)
```bash
python3 -m venv env
/env/Scripts/activate
pip install -r requirements.txt
```

That's it! You're ready to run the freemocap application, and create your own digital skeletons.

## Usage

## For Developers

### Contribution Guidelines

COMING SOON

### Creating a new binary

Create a new binary on your local system by running the below comand
```bash
task installer
```

Navigate to the `/dist/` directory and you'll see the new Freemocap Binary there.

## Related

[//]: # (* [project-name]&#40;#&#41; - Project description)

## Maintainers

* [Jon Matthis](https://github.com/jonmatthis)
* [Endurance Idehen](https://github.com/endurance)

## License
This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.
