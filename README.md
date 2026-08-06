# imzDesk

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

imzDesk is an open-source workbench and Python library for working with whole-slide imaging (WSI) and mass
spectrometry imaging (MSI) data. Its browser-based workspace supports image inspection, MSI visualization, pixel-level
spectrum comparison, WSI-MSI registration, annotation, and dataset curation. The Python API provides the same image
types and preprocessing tools for building reproducible analysis and model-training pipelines.

## Requirements

- Python 3.12 or newer
- The native [OpenSlide](https://openslide.org/download/) library

OpenSlide must be installed through your operating system before installing imzDesk. For example:

```shell
# Ubuntu or Debian
sudo apt install libopenslide0

# macOS with Homebrew
brew install openslide
```

See the [OpenSlide installation instructions](https://openslide.org/download/) for other platforms.

## Installation

Install imzDesk from PyPI:

```shell
python -m pip install imzdesk
```

Optional dependency groups add model-based spectral embeddings or the Jupyter environment used by the example
notebooks:

```shell
# Model-based embeddings with PyTorch
python -m pip install "imzdesk[embeddings]"

# Jupyter example notebooks
python -m pip install "imzdesk[examples]"

# Both optional groups
python -m pip install "imzdesk[embeddings,examples]"
```

## Start the Workbench

Point imzDesk at a directory containing the images you want to work with:

```shell
imzdesk /path/to/workspace
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. imzDesk scans the workspace recursively for
supported WSI files and imzML datasets. Each `.imzML` file must have its corresponding `.ibd` file beside it.
Application metadata, annotations, cached data, registrations, and dataset manifests are stored in hidden `.imzDesk`
directories alongside the source data.

Run `imzdesk --help` to see server options such as the host, port, inference device, and logging level.

## Documentation

The [imzDesk documentation](https://med-i-lab.gitbook.io/imzdesk) contains manuals for the web workbench and the Python
API reference. The [`examples`](examples) directory also contains executable notebooks covering image transforms,
registration, and PyTorch dataset preparation.

## License

imzDesk is distributed under the [Apache License 2.0](LICENSE).
