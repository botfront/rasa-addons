from setuptools import setup

setup(
    name='rasa_addons',
    description='Rasa Add-ons',
    version='0.3.0',
    author='Nathan Zylbersztejn',
    install_requires=['flask', 'flask_socketio', 'flask_cors', 'jsonmerge', 'pyyaml', 'schema'],
    licence='Apache 2.0',
    url='http://mrbot.ai',
    author_email='human@mrbot.ai',
    packages=['rasa_addons', 'rasa_addons.webchat', 'rasa_addons.superagent', 'rasa_addons.domains']
)
