from setuptools import setup, find_packages
import os
import io

with io.open(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "README.md"),
    encoding="utf-8",
) as f:
    long_description = f.read()
setup(
    name="rasa_addons",
    version="0.9.14",
    author="Botfront",
    description="Rasa Addons - Components for Rasa and Botfront",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "requests",
        "requests_futures",
        "fuzzy_matcher",
        "fbmessenger",
        "sgqlc",
    ],
    packages=find_packages(exclude=["tests"]),
    licence="Apache 2.0",
    url="https://botfront.io",
    author_email="hi@botfront.io",
)
