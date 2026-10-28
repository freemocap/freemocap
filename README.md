
# SPECIAL INSTRUCTIONS FOR THE `/development` BRANCH 

## Installation
### Python server
0. Install `uv` 
   - https://github.com/astral-sh/uv?tab=readme-ov-file#installation
1. clone the repo 
   - `git clone https://github.com/freemocap/freemocap`
2. Change directory to the repo: 
   - `cd freemocap`
3. **Change to the `development` branch:**
   - `git switch development`
4. Create virtual environment: 
   - `uv venv` 
5. Activate virtual environment
   - Windows: `.venv/bin/activate`
   - Mac/Linux: `source .venv/bin/activate`
6. Install dependencies
  - `uv sync` — installs skellytracker with NVIDIA GPU acceleration on Windows/Linux, or CPU-only on macOS, automatically
  - No supported GPU on Windows/Linux? Force the CPU-only build instead: `uv sync --no-default-groups --group cpu`
### React GUI
0. Install Node.js
   - https://nodejs.org/en/download/
1. Change directory to the `freemocap-ui` folder 
   - `cd freemocap-ui`
2. Install dependencies
   - `npm install`

## Run the FreeMoCap application in development mode 
1. Start the Python Server:
   - `python freemocap/__main__.py`
   - The server should start on `http://localhost:8005`
2. Start the React GUI:
   - `npm run dev`
   - An Electron window should pop up with the FreeMoCap GUI


## Build the FreeMoCap application 
(NOTE - This is not necessary for development, and does not handle the Python server yet)
1. Change directory to the `freemocap/freemocap-ui` folder
   - `npm run build`
   - The build will be in the `freemocap/freemocap-ui/releases` folder
---
---
# STANDARD README CONTINUES BELOW
___
___
___
<p align="center">
    <img src="https://github.com/freemocap/freemocap/assets/15314521/da1af7fe-f808-43dc-8f59-c579715d6593" height="240" alt="Project Logo">
</p> 


<h3 align="center">The FreeMoCap Project</h3>
<h4 align="center"> A free-and-open-source, hardware-and-software-agnostic, minimal-cost, research-grade, motion capture
system and platform for decentralized scientific research, education, and training</h2>


<p align="center">

<a href="https://doi.org/10.5281/zenodo.7233714">
    <img src="https://zenodo.org/badge/DOI/10.5281/zenodo.7233714.svg" alt=DOI-via-Zenodo.org>
  </a>

<a href="https://github.com/psf/black">
    <img alt="https://img.shields.io/badge/code%20style-black-000000.svg" src="https://img.shields.io/badge/code%20style-black-000000.svg">
  </a>

<a href="https://github.com/freemocap/freemocap/releases/latest">
        <img src="https://img.shields.io/github/release/freemocap/freemocap.svg" alt="Latest Release">
    </a>

<a href="https://github.com/freemocap/freemocap/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/license-AGPL-blue.svg" alt="AGPLv3">
    </a>

<a href="https://github.com/freemocap/freemocap/issues">
        <img src="https://img.shields.io/badge/contributions-welcome-ff69b4.svg" alt="Contributions Welcome">
    </a>

<a href="https://discord.gg/SgdnzbHDTG">
    <img src="https://img.shields.io/badge/join_us-on_discord-5865F2?logo=discord&logoColor=white" alt="Discord server"/>
  </a>


</p>


https://user-images.githubusercontent.com/15314521/192062522-2a8d9305-f181-4869-a4b9-1aa068e094c9.mp4



___
## QUICKSTART

#### 0. Create a a Python 3.9 through 3.11 environment (python3.11 recommended)¶
#### 1. Install software via [pip](https://pypi.org/project/freemocap/#description):

`freemocap` requires the `cuda` or `cpu` extra to be specified — plain `pip install freemocap` will install without its tracker. Pick one:

```
pip install freemocap[cuda]   # Windows/Linux with an NVIDIA GPU
```

```
pip install freemocap[cpu]    # macOS, or Windows/Linux without a supported GPU
```

#### 2. Launch the GUI by entering the command:

```
freemocap
``` 

####  3. A GUI should pop up that looks like this: 

   <img width="1457" alt="image" src="https://github.com/freemocap/freemocap/assets/15314521/90ef7e7b-48f3-4f46-8d4a-5b5bcc3254b3">

#### 4. Have fun! It might break!  Work in Progress lol

#### 5. [Join the Discord and let us know how it went!](https://discord.gg/nxv5dNTfKT)



___
## Install/run from source code (i.e. the code in this repo)

This repo's dependencies (`skellytracker`, `skellycam`, etc.) are pulled from
private git repos via [`uv`](https://github.com/astral-sh/uv), so `conda` +
`pip install -e .` will not work here — use `uv` instead:

1) Install `uv`
   - https://github.com/astral-sh/uv?tab=readme-ov-file#installation

2) Clone the repository

```bash
git clone https://github.com/freemocap/freemocap
```

3) Navigate into the newly cloned/downloaded `freemocap` folder

```bash
cd freemocap
```

4) Create a virtual environment

```bash
uv venv
```

5) Install dependencies

```bash
uv sync
```

This installs `skellytracker` with NVIDIA GPU acceleration on Windows/Linux, or
CPU-only on macOS, automatically. If you're on Windows/Linux without a
supported GPU, force the CPU-only build instead:

```bash
uv sync --no-default-groups --group cpu
```

6) Launch the Python server

```bash
uv run python freemocap/__main__.py
```

The server starts on `http://localhost:8005`.

7) In a separate terminal, launch the React/Electron GUI (requires
   [Node.js](https://nodejs.org/en/download/)):

```bash
cd freemocap-ui
npm install
npm run dev
```

An Electron window should pop up with the FreeMoCap GUI!

___

## Documentation 

Our documenation is hosted at: https://freemocap.github.io/documentation/index_md.html

That site is built using `writerside` from this repository: https://github.com/freemocap/documentation

___



### Contribution Guidelines

Please read our contribution doc: [CONTRIBUTING.md](CONTRIBUTING.md)


## Related

[//]: # (* [project-name]&#40;#&#41; - Project description)

## Maintainers

* [Jon Matthis](https://github.com/jonmatthis)
* [Endurance Idehen](https://github.com/endurance)

## License

This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.

If the AGPL does not work for your needs, we are happy to discuss terms to license this software to you with a different
agreement at a price point that increases exponentially as you
move [spiritually](https://www.gnu.org/philosophy/open-source-misses-the-point.en.html) away from the `AGPL`
