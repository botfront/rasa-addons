# Rasa Addons


![PyPI](https://img.shields.io/pypi/v/rasa-addons.svg)
![Travis](https://img.shields.io/travis/mrbot-ai/rasa-addons.svg)


A set of power tools to 🚀🚀🚀 your productivity with Rasa

- Input validation: if you expect Yes or No, just specify it in a YAML file and Rasa Core will just handle that for you
- Intent Substitution: avoid random intents when users enter data without semantic consistency (names, brands, time,...)
- Webchat: a channel to use with our open source web chat widget
- Custom dispatchers: need to store your Rasa Core templates out of domain file? We've got you covered




## Installation
```bash
pip install rasa-addons
```

## Rasa channel for the [Web chat widget](https://github.com/mrbot-ai/webchat)

### Usage

```python
from rasa_addons.webchat import WebChatInput, SocketInputChannel

agent = Agent.load(...)
input_channel = WebChatInput(static_assets_path=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'))
agent.handle_channel(SocketInputChannel(5500, "/bot", input_channel))

```

In `static` you could have an `index.html` containing the widget snippet that you could access to `http://localhost:5500/bot`

## Rules

Enforcing some rules on top of the ML can be sometimes be useful. Those rules are defined in a `rules.yml` file that is referenced as follows:

```python
from rasa_addons.superagent import SuperAgent
agent = SuperAgent.load(...,rules_file='rules.yml')
```

Rules are enforced at the tracker level, so there is no need to retrain when changing them.

### Input validation
The following rule will utter the `error_template` if the user does not reply to `utter_when_do_you_want_a_wake_up_call` with either `/cancel` OR `/speak_to_human` OR `/enter_time{"time":"..."}`

```yaml
input_validation:
  - after: utter_when_do_you_want_a_wake_up_call
    expected:
      - intents:
        - cancel
      - intents:
        - skeak_to_human
      - intents:
        - enter_time
        entities:
        - time
    error_template: utter_please_provide_time
```


### Intent substitution:
Some intents are hard to catch. For example when the user is asked to fill arbitrary data such as a date or a proper noun. The following will substitute any intent caught after `utter_when_do_you_want_a_wake_up_call` with `enter_data` unless...

```yaml
intent_substitutions:
  - after: utter_when_do_you_want_a_wake_up_call
    intent: enter_data
    unless: frustration|cancel|speak_to_human
```  

### Entity filtering

Sometimes Rasa NLU CRF extractor will return unexpected entities and those can perturbate your Rasa Core dialogue model
because it has never seen this particular combination of intent and entity.

This helper lets you define precisely the entities allowed for every intent in a yaml file. Entities not in the list for a given intent will be cleared. It will only remove entities for intents specifically listed in this section:

```yaml
allowed_entities:
  book: # intent
    - origin # entity
    - destination
  buy:
    - color
    - product
```

## Custom dispatcher

If you want to get your templates from another source than the domain, you can do it like this:

Create your dispatcher
```python
class MyDispatcher(Dispatcher):
    def retrieve_template(self, template_name, filled_slots=None, **kwargs):
        """Retrieve a named template from the domain."""

        response = requests.get('api/{template_key}/'.format(...))
        if response.status_code == 200:
            r = response.json()
            if r is not None:
                return self._fill_template_text(r, filled_slots, **kwargs)
            
        else:
            print("error")

```

Then load your agent
```python
agent = SuperAgent.load(POLICY_PATH,
                        interpreter=interpreter,
                        create_dispatcher=lambda sender_id, output_channel, domain: MyDispatcher(sender_id, output_channel, domain))

```


