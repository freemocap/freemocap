<p align="center">
    <img src="https://raw.githubusercontent.com/freemocap/freemocap/main/assets/logo/freemocap-logo-black-border.svg" height="64" alt="Project Logo">
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
  <a href="https://github.com/psf/black">
    <img alt="https://img.shields.io/badge/code%20style-black-000000.svg" src="https://img.shields.io/badge/code%20style-black-000000.svg">
  </a>
</p>

## Pardon our dust as we transtion to the `alpha` phase of this project!

We are currently in the process of transitioning from the  `pre-alpha` code base into the fully refactored `alpha` code base. Some things might be a bit clunky while we make the transition, but I promise it will be worth it!

If you would like to access the `pre-alpha` code, you can find it here under the release tag `v0.0.54` [here](https://github.com/freemocap/freemocap/releases/tag/v0.0.54)

(2022-07-19) [If you are interested in this project, please fill out this quick (<1min) survey to let use know who you are :D ](https://forms.gle/CPnMe3LvrRPn5cis6)

## Pre-requisites

### General
- [Python 3.9](https://www.python.org/downloads/release/python-390/)
- [Git](https://www.atlassian.com/git/tutorials/install-git)
- [Blender](https://www.blender.org/download/)
- At least 2 simple webcameras (but we recommend using at least 3 for better results)
    - Any USB webcam should work [here's an example of a camera we have used successfully](https://www.amazon.com/Microphone-110-Degree-Widescreen-Streaming-Conferencing/dp/B084ZJFNKN)
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

### Dev Setup

After you've done the easy install instructions, you'll be able to run our repo commands

1. Run the "setup" command to set up your environment
```bash
task setup
```
2. Run the tests to ensure that everything works appropriate
```bash
task test
```

### Contribution Guidelines

Please read our contribution doc: [CONTRIBUTING.md](CONTRIBUTING.md)

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
