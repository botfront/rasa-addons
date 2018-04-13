## Rasa channel for the [Web chat widget](https://github.com/mrbot-ai/webchat)

To use with https://github.com/mrbot-ai/webchat

### Usage

```python
from rasa_addons.webchat import WebChatInput, SocketInputChannel

agent = Agent.load(...)
input_channel = WebChatInput(static_assets_path=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'))
agent.handle_channel(SocketInputChannel(5500, "/bot", input_channel))

```

In `static` you could have an `index.html` containing the widget snippet that you could access to `http://localhost:5500/bot` 
 
 
 
## Entity filtering

Sometimes Rasa NLU CRF extractor will return unexpected entities and those can perturbate your Rasa Core dialogue model 
because it has never seen this particular combination of intent and entity.

This helper lets you define precisely the entities allowed for every intent in a yaml file:

```yaml
book: # intent
  - origin # entity
  - destination
buy:
  - color
  - product
```

Then load your agent as follows:

```python
agent = SuperAgent.load(POLICY_PATH, allowed_entities_filename='allowed_entities.yml')
```