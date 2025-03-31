#!/usr/bin/env python3

"""
Setup script.

Use this script to install the core of the retico simulation framework. Usage:
    $ python3 setup.py install

Author: Thilo Michael (uhlomuhlo@gmail.com)
"""

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

exec(open("retico_core/version.py").read())

import os
import pathlib
import platform
import subprocess

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / "README.md").read_text(encoding="utf-8")


install_requires = [
    "pyaudio",
    "structlog",
    "colorama",
    "matplotlib",
    "keyboard",
]

# Determine the operating system
print(f"System OS : {platform.system()}")
is_linux = platform.system().lower() == "linux"
if is_linux:
    # If Linux, attempt to install pyaudio via apt
    try:
        print(
            "Detected Linux OS. Installing portaudio via apt to make it possible to install pyaudio with pip afterwards"
        )
        # subprocess.run(["apt", "install", "-y", "portaudio19-dev"], check=True)
        subprocess.run(["conda", "install", "pyaudio"], check=True)
    except Exception as e:
        print(f"Failed to install portaudio via apt: {e}")

config = {
    "description": "A framework for real time incremental dialogue processing.",
    "long_description": long_description,
    "long_description_content_type": "text/markdown",
    "author": "Thilo Michael",
    "author_email": "uhlomuhlo@gmail.com",
    "url": "https://github.com/retico-team/retico-core",
    "download_url": "https://github.com/retico-team/retico-core",
    "version": __version__,
    "python_requires": ">=3.6, <4",
    "keywords": "retico, framework, incremental, dialogue, dialog",
    "install_requires": install_requires,
    "extras_require": {"pyaudio": "pyaudio"},
    "packages": find_packages(),
    "name": "retico-core",
    "classifiers": [
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
    ],
}

setup(**config)
