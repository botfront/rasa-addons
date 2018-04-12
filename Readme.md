## Rasa channel for the [Web chat widget](https://github.com/mrbot-ai/webchat)

To use with https://github.com/mrbot-ai/webchat

### Usage

```python
agent = Agent.load(...)
input_channel = WebChatInput(static_assets_path=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'))
agent.handle_channel(SocketInputChannel(5500, "/bot", input_channel))

```

In `static` you could have an `index.html` containing the widget snippet that you could access to `http://localhost:5500/bot` 
 