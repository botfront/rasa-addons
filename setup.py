from setuptools import setup
import os
import io

with io.open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
setup(
    name='rasa_addons',
    version='0.5.9',
    author='Nathan Zylbersztejn',
    description="Rasa Addons - Productivity tools for Rasa Core",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=['jsonmerge', 'pyyaml', 'schema', 'rasa_core>=0.11.0', 'requests'],
    licence='Apache 2.0',
    url='https://mrbot.ai',
    author_email='human@mrbot.ai',
    packages=['rasa_addons']
)
