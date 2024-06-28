#!/usr/bin/env python
"""pysma library setup."""
from pathlib import Path

from setuptools import setup

VERSION = "0.3.5"
URL = "https://github.com/littleyoda/pysma"

setup(
    name="pysma-plus",
    version=VERSION,
    description="Library to interface SMA Devices via WebConnect, EnnexOS and Energy Meter Devices",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url=URL,
    download_url="{}/tarball/{}".format(URL, VERSION),
    author="Sven Bursch-Osewold, Johann Kellerman and other",
    author_email="sb_pysma@bursch.com",
    license="MIT",
    packages=["pysma-plus"],
    python_requires=">=3.9",
    install_requires=[
        "aiohttp>3.3,<4",
        "attrs>18",
        "jmespath<2",
        "dataclasses-struct>0.8",
        "untangle>=1.2.1",
        "pymodbus>=3.6.9",
    ],
    zip_safe=True,
)
