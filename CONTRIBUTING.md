# Contributing to Freemocap
We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## We Develop with Github
We use github to host code, to track issues and feature requests, as well as accept pull requests.

## We Use [Github Flow](https://docs.github.com/en/get-started/quickstart/github-flow), So All Code Changes Happen Through Pull Requests
Pull requests are the best way to propose changes to the codebase (we use [Github Flow](https://docs.github.com/en/get-started/quickstart/github-flow)). We actively welcome your pull requests:

1. Fork the repo and create your branch from `main`.
2. Download the development dependencies with `pip install -e '.[dev]'`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes by running `pytest freemocap/tests`.
5. Make sure your code lints.
6. Issue that pull request!

## Any contributions you make will be under the AGPL Software License
In short, when you submit code changes, your submissions are understood to be under the same [AGPL](LICENSE) that covers the project. Feel free to contact the maintainers to understand what that means.

## Report bugs using Github's [issues](https://github.com/freemocap/freemocap/issues)
We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/freemocap/freemocap/issues/new); it's that easy!

## Write bug reports with detail, background, and sample code
[This is an example](http://stackoverflow.com/q/12488905/180626) of a "great" bug report.

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Include an uploaded ZIP of the freemocap data session you ran that produced the issue.
  - Give sample code if you can. [This stackoverflow question](http://stackoverflow.com/q/12488905/180626) demonstrates the user giving as much information as possible.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports. The likelihood that the community and/or maintainers will help you with your issues stems from how well you can help them understand you. :)

## Pull Request (PR) Guidelines

> **DISCLAIMER:** These are the guidelines we expect all pull requests from contibuters to follow. If your PR does not follow these guidelines, we may ask you to make some changes before we can review it.

- Any code that comes through a PR should be covered with tests
- Make sure the tests pass locally by running `pytest freemcap/tests`
- Those test must pass our Github Actions workflow before they may be merged
- Any UI changes should include a small video of the working application with the change included

## Use a Consistent Coding Style
We use the [Black](https://black.readthedocs.io/en/stable/) autoformatter as the de-facto syntax style guide of choice.

### PyQT Style Guide
COMING SOON

### API Style Guide
COMING SOON

## License
By contributing, you agree that your contributions will be licensed under its [AGPL](LICENSE) License.

## References
This document was adapted from the open-source contribution guidelines for [Facebook's Draft](https://github.com/facebook/draft-js/blob/main/CONTRIBUTING.md)
