from setuptools import setup

setup(
    name='mrbot_rasa_addons',
    description='Rasa Add-ons',
    version='0.1',
    author='Nathan Zylbersztejn',
    install_requires=['flask', 'flask_socketio', 'flask_cors'],
    licence='Apache 2.0',
    url='http://mrbot.ai',
    author_email='human@mrbot.ai',
    packages=['rasa_addons', 'rasa_addons.webchat']
)
