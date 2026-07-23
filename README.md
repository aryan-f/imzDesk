# imzDesk: WSI-MSI Workbench

![Build Status](https://img.shields.io/github/actions/workflow/status/aryan-f/imzDesk/build.yml)
[![codecov](https://codecov.io/gh/aryan-f/imzDesk/graph/badge.svg)](https://codecov.io/gh/aryan-f/imzDesk)
![PyPI Python Version](https://img.shields.io/pypi/pyversions/imzdesk)
[![PyPI Version](https://img.shields.io/pypi/v/imzdesk)](https://pypi.org/project/imzdesk/)
[![GitHub Repo](https://img.shields.io/badge/github-repo-blue?logo=github)](https://github.com/aryan-f/imzDesk/)
[![Documentation](https://img.shields.io/badge/gitbook-docs-3884FF?logo=gitbook&logoColor=white)](https://med-i-lab.gitbook.io/imzdesk)

<p align="center">
  <img
    src="https://raw.githubusercontent.com/aryan-f/imzDesk/master/assets/imzdesk-demo.webp"
    alt="imzDesk software demo showing MSI and WSI visualization and co-registration"
    width="1000"
  />
</p>

**imzDesk** is an open-source web-based workbench and Python library that enables multi-modal analysis and modeling of Whole Slide Images (WSIs) and Mass Spectrometry Images (MSIs).

## Prerequisites

[`libopenslide`](https://openslide.org/download/)

## Installation

```shell
pip install "imzdesk[extras]"
```

## Usage

```shell
python -m imzdesk <dirpath>
```
