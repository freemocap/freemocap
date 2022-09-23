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


https://user-images.githubusercontent.com/15314521/192062522-2a8d9305-f181-4869-a4b9-1aa068e094c9.mp4


___
# How to use the `pre-alpha` code


We're in the process of switching over to the `alpha` phase of this project (`v0.1.0` and on) , which use full refactor code written with help from a professional experienced software architect. 

Until the new code stabilizes, you may have more luck using the `pre-alpha` code (e.g. `v0.0.54`)

---
## INSTALLATION 

Note: This will install the latest/last version from the `pre-alpha` phase of this project, frozen at release tag `v0.0.54` [here](https://github.com/freemocap/freemocap/releases/tag/v0.0.54)

Open an Anaconda-enabled command prompt or powershell window and enter the following commands:

1) Create a Python3.7 Anaconda environment
```bash 
conda create -n freemocap-env python=3.7
``` 

2) Activate that newly created environment
```bash
conda activate freemocap-env
```
3) Install freemocap (version `0.0.54`)  from PyPi using `pip`
```bash
pip install freemocap==0.0.54
```

BUG FIX - Update `mediapipe` with: `pip install mediapipe --upgrade`

That should be it!
___
##  How to create a *NEW* `freemocap` recording session

tl;dr- **Activate the freemocap Python environment** and run the following lines of code (either in a script or in a console)

```python
import freemocap
freemocap.RunMe()
```

But COOL KIDS will install Blender ([blender.org](https://blender.org) and generate an awesome `.blend` file animation by setting `useBlender=True`: 

```python
import freemocap
freemocap.RunMe(useBlender=True)
```

:point_right: **For additional, more detailed instructions (including methods to re-process recorded sessions), [refer to the `OLD_README.md` document](https://github.com/freemocap/freemocap/blob/main/OLD_README.md))** :point_left: 

___

#  HOW TO RUN THE `alpha` GUI

NOTES
- no promises here, friends. Work in progress lol :joy:    
- Personally, I run the gui through PyCharm, but its easier to write instructions on how to run from an anaconda prompt
 
## Pre-requisites:
1. Install Anaconda
    - https://anaconda.org
2. Install git 
     - https://git-scm.com/book/en/v2/Getting-Started-Installing-Git (just use the defaults)  
3. (OPTIONAL) Install Blender - https://blender.org

## Installation instructions

1. Open anaconda enabled terminal

2. Create a `python=3.9` environment
```bash
conda create -n freemocap-gui python=3.9
```

3. Activate that environment:
```
conda activate freemocap-gui
```

4. Clone the repository (i.e. download the code from github. It'll show up in the current working directory of your terminal session)
```
git clone https://github.com/freemocap/freemocap
```

5. Navigate into that newly cloned/downloaded `freemocap` folder with:
```
cd freemocap
```

6. Install the dependencies listed in the `requirements.txt` file:
```
pip install -r requirements.txt
```
7. Run the GUI by running the `src/gui/main/main.py` file by entering this command into the terminal:

```bash
python src/gui/main/main.py
```

8. Hopefully a GUI popped up! There are no docs on usage yet, so just click and see what you can figure out :joy:


___


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

### Creating a new binary (may or may not work lol)

Create a new binary on your local system by running the below comand
```bash
task installer
```

Navigate to the `/dist/` directory and you'll see the new FreeMoCap Binary there.

## Related

[//]: # (* [project-name]&#40;#&#41; - Project description)

## Maintainers

* [Jon Matthis](https://github.com/jonmatthis)
* [Endurance Idehen](https://github.com/endurance)

## License
This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.

If the AGPL does not work for your needs, we are happy to discuss terms to license this software to you with a different license at a price point that will increase exponentially as you move from AGPL towards fully closed source software. 
