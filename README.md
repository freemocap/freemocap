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

<a href="https://github.com/psf/black">
    <img alt="https://img.shields.io/badge/code%20style-black-000000.svg" src="https://img.shields.io/badge/code%20style-black-000000.svg">
  </a>

<a href="https://discord.gg/SgdnzbHDTG">
    <img alt="Discord Community Server" src="https://dcbadge.vercel.app/api/server/SgdnzbHDTG?style=flat">
  </a>


</p>


https://user-images.githubusercontent.com/15314521/192062522-2a8d9305-f181-4869-a4b9-1aa068e094c9.mp4





--
## QUICKSTART

> [!NOTE]
> For detailed installation instructions, see our [official documentation's Installation page](https://freemocap.github.io/documentation/installation.html#detailed-pip-installation-instructions)

### Option A — uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager that handles environments automatically.

Install uv ([full instructions](https://docs.astral.sh/uv/getting-started/installation/)):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install and run FreeMoCap:

```bash
uv tool install freemocap
freemocap
```

<details>
<summary><strong>Option B — pip + venv</strong></summary>

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install freemocap
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install freemocap
```

Launch the GUI:

```bash
freemocap
```

</details>

<details>
<summary><strong>Option C — Anaconda</strong></summary>

```bash
conda create -n freemocap-env python=3.12
conda activate freemocap-env
pip install freemocap
```

Launch the GUI:

```bash
freemocap
```

</details>

> **Python version:** FreeMoCap supports Python 3.10 – 3.12 (3.12 recommended).

#### A GUI should pop up that looks like this:

   <img width="1457" alt="image" src="https://github.com/freemocap/freemocap/assets/15314521/90ef7e7b-48f3-4f46-8d4a-5b5bcc3254b3">

#### Have fun! See the [Beginner Tutorials](https://freemocap.github.io/documentation/your-first-recording.html) on our official docs for detailed instructions.

#### [Join the Discord and let us know how it went!](https://discord.gg/nxv5dNTfKT)



___
## Install/run from source code (i.e. the code in this repo)

Choose your preferred method below. All methods require [Git](https://git-scm.com/).

### Option A — uv (Recommended)

[uv](https://docs.astral.sh/uv/) manages Python versions and virtual environments for you.
If you don't have uv yet, see the [installation guide](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/freemocap/freemocap
cd freemocap
uv sync
```

Launch the GUI:

```bash
uv run freemocap
```

<details>
<summary><strong>Option B — pip + venv</strong></summary>

#### Windows

```bash
git clone https://github.com/freemocap/freemocap
cd freemocap
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m freemocap
```

#### macOS / Linux

```bash
git clone https://github.com/freemocap/freemocap
cd freemocap
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m freemocap
```

</details>

<details>
<summary><strong>Option C — Anaconda</strong></summary>

Open an [Anaconda-enabled command prompt](https://www.anaconda.org) and enter the following commands:

```bash
conda create -n freemocap-env python=3.12
conda activate freemocap-env
git clone https://github.com/freemocap/freemocap
cd freemocap
pip install -e .
python -m freemocap
```

</details>

A GUI should pop up!

___

## Documentation 

Our documentation is hosted at: https://freemocap.github.io/documentation

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

