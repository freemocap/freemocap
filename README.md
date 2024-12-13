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

#### 0. Create a a Python 3.10 through 3.12 environment (python3.11 recommended)¶
#### 1. Install software via [pip](https://pypi.org/project/freemocap/#description):

```
pip install freemocap
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

Open an [Anaconda-enabled command prompt](https://www.anaconda.org) (or your preferred method of environmnet management) and enter the following commands:

1) Create a `Python` environment (Recommended version  is `python3.11`)

```bash
conda create -n freemocap-env python=3.11
```

2) Activate that newly created environment

```bash
conda activate freemocap-env
```

3) Clone the repository

```bash
git clone https://github.com/freemocap/freemocap
```

4) Navigate into the newly cloned/downloaded `freemocap` folder

```bash
cd freemocap
```

5) Install the package via the `pyproject.toml` file

```bash
pip install -e .
```

6) Launch the GUI (via the `freemocap.__main__.py` entry point)

```bash
python -m freemocap
```

A GUI should pop up!

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

