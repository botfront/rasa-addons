# Rasa Addons


![PyPI](https://img.shields.io/pypi/v/rasa-addons.svg)
![Travis](https://img.shields.io/travis/mrbot-ai/rasa-addons.svg)

A set of power tools to 🚀🚀🚀 your productivity with Rasa

- Input validation: if you expect Yes or No, make sure your users answer Yes or No
- Disambiguation and fallback: automatically display dismabiguation options to users based on custom triggers
- Intent Substitution: avoid random intents when users enter data without semantic consistency (names, brands, time,...)
- Filter entities: define entities allowed for each intent


## Contents

- [Installation](#installation)
- [Usage](#usage)
	- [Validate user input](#validate-user-input)
	- [Disambiguate user input and fallback](#disambiguate-user-input-and-fallback)
		- [Disambiguation policy](#disambiguation-policy)
		    - [Suggestions](#suggestions)
		    - [Rephrasing](#rephrasing)
		- [Fallback policy](#fallback-policy)
		- [Using both disambiguation and fallback policies](#using-both-disambiguation-and-fallback-policies)
	- [Substitute intents](#substitute-intents)
	- [Filter entities](#filter-entities)
	- [Bonus - Create a FAQ bot with only ONE action and ONE story](#bonus-create-a-faq-bot-with-only-one-action-and-one-story)
	- [Where are automated tests ?](#where-are-automated-tests-)


## Installation

Rasa core < 0.11.x

```bash
pip install rasa-addons==0.4.3
```

Rasa core >= 0.11.x

```bash
pip install rasa-addons
```

## Usage

You can set rules in a declarative way using a YAML file or a remote endpoint. To do that you must start Rasa Core from a
[python script](https://rasa.com/docs/core/connectors/#id18) and include the following snippet

To load rules from a YAML file:
```python
from rasa_addons.superagent import SuperAgent
agent = SuperAgent.load(...,rules='rules.yml')
```

To load rules from a remote endpoint:
```python
from rasa_addons.superagent import SuperAgent
agent = SuperAgent.load(...,rules=EndpointConfig(url="https://my.rules.endpoint/path", ...))
```

In the rest of this document we'll assume you are reading from a YAML file

### Validate user input


```python
from rasa_addons.superagent import SuperAgent
agent = SuperAgent.load(...,rules='rules.yml')
```
In `rules.yml` you can add input validation rules

```yaml
input_validation:
  - after: utter_when_do_you_want_a_wake_up_call
    # !!WARNING!! If regex is set true then the validation will trigger for
    #             all actions which includes the above text. It is encouraged
    #             to set regex to false for matching the validation to a
    #             specific action.
    regex: false # optional (default: True)
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
The following rule will utter the `error_template` if the user does not reply to `utter_when_do_you_want_a_wake_up_call` with either `/cancel` OR `/speak_to_human` OR `/enter_time{"time":"..."}`
Rules are enforced at the tracker level, so there is no need to retrain when changing them.

### Disambiguate user input and fallback

#### Disambiguation policy

Help your users when your NLU struggles to identify the right intent. Instead of just going with the highest scoring intent or just going with a fallback
you can ask the user to confirm the question or to pick from a list of likely intents.

##### Suggestions

One way to disambiguate is to provide the user with buttons, each button corresponding to one intent. 
In the example below, the disambiguation is triggered when the score of the highest scoring intent is below twice the score of the second highest scoring intent.

The bot will utter:
1. An intro message (if the optional field `intro_template` is present)
2. A text with buttons (or quick replies) message where:
 - the text is the template defined as `text_template`,
 - the button titles will be the concatenation of "utter_disamb" and the intent name. For example, `utter_disamb_greet`."
 - the buttons payloads will be the corresponding intents (e.g. `/greet`). Entities found in `parse_data` are passed on.
3. A fallback button to go along with disambiguation buttons (if the optional field `fallback_button` is present)

It's also possible to exclude certain intents from being displayed as a disambiguation option by using optional `exclude` list field. In the example below, all intents that match regex `chitchat\..*` and `basics\..*`, as well as intent `cancel` will not be displayed as an option. The next highest scoring intents will be displayed in place of excluded ones.

```yaml
disambiguation_policy:
  trigger: $0 < 2 * $1
  type: suggest
  max_suggestions: 2
  slot_name: parse_data # optional slot name to store the parse data originating a disambiguation
  display:
    intro_template: utter_disamb_intro # optional: will not be rendered if not set
    text_template: utter_disamb_text
    button_title_template_prefix: utter_disamb
    fallback_button:
      title: utter_fallback_yes
      payload: /fallback
    exclude:
      - chitchat\..*
      - basics\..*
      - cancel
```

**Notes:**
- `trigger`: `$0` corresponds to `parse_data['intent_ranking'][0]["confidence"]`. You can set any rule based on intent ranking. Intent scores are checked against the trigger before any intent is excluded with `exclude`.
- `slot_name`: you need to set the slot in the Core domain to get it from the tracker. E.g. `tracker.get_slot(slot_name)`You may want to make the bot go straight to suggesting fallback (e.g when the top intent ranking is low).

The bot will utter:
1. An intro message `utter_fallback_intro`
2. Optional buttons (if `buttons` list with at least one item - a pair of `title` and `payload` - is defined).

#### Rephrasing
Another way to disambiguate is to rephrase. When triggered, the bot asks "Did you mean [something related to the intent]"? followed by two buttons (titles in `yes_template` and `no_template`).
`no_payload` is the payload to trigger when the user clicks the no button.

```yaml
disambiguation_policy:
  trigger: $0 < 2 * $1
  type: rephrase
  display:
    rephrase_template: utter_rephrase
    yes_template: utter_yes
    no_template: utter_no
    no_payload: /fallback
    exclude:
      - chitchat\..*
      - basics\..*
      - cancel
```
      
#### Fallback policy
In the example below, fallback is triggered when the top scoring intent's confidence is below 0.5.

```yaml
fallback_policy:
  trigger: $0 < 0.5
  slot_name: parse_data # optional slot name to store the parse data originating a disambiguation
  display:
    text: utter_fallback_intro
    buttons:
      - title: utter_fallback_yes
        payload: /fallback
      - title: utter_fallback_no
        payload: /restart
```

There is no limit on the number of buttons you can define for fallback. If no buttons are defined, this
policy will simply make the bot utter some default message (e.g `utter_fallback_intro`) when the top intent confidence is lower than the trigger.


#### Using both disambiguation and fallback policies

It's easy to combine both disambiguation and fallback policies. It can be done by filling in policy definitions from two previous examples as follows:

```yaml
disambiguation_policy:
      (...disambiguation policy definition...)

fallback_policy:
      (...fallback policy definition...)
```

In cases when intent confidence scores in parsed data are such that would cause both policies to trigger, only fallback policy is trigerred. In other words, **fallback policy has precedence over disambiguation policy**.

### Substitute intents
Some intents are hard to catch. For example when the user is asked to fill arbitrary data such as a date or a proper noun.
The following rule swaps any intent caught after `utter_when_do_you_want_a_wake_up_call` with `enter_data` unless...

```yaml
intent_substitutions:
  - after: utter_when_do_you_want_a_wake_up_call
    intent: enter_data
    unless: frustration|cancel|speak_to_human
```

### Filter entities

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

Then load your agent
```python
agent = SuperAgent.load(POLICY_PATH,
                        interpreter=interpreter,
                        create_dispatcher=lambda sender_id, output_channel, domain: MyDispatcher(sender_id, output_channel, domain))

```

### Bonus - Create a FAQ bot with only ONE action and ONE story


You create an intent substitution rule like this:

```yaml
intent_substitutions:

  - intent: (faq.*)
    with: faq
    entities:
      add:
      - name: intent
        value: '{intent}'
```

This rule will match all intents starting with `faq` (e.g.: `faq.how_do_i_create_a_faq`)
This will change the dialog act to `{intent: "faq", entities: [{intent: "faq.how_do_i_create_a_faq"}]}`

In Core, add this story:
```md
## FAQ
* faq{"intent":"original_intent"}
  - action_faq
```

And this action

```python
class ActionFAQ(Action):

    def name(self):
        return "action_faq"

    def run(self, dispatcher, tracker, domain):
         # get the original intent from tracker.latest_message and retrieve the correct answer
```

The benefit of this approach is you have only ONE story for all your questions, so if your Q&A are stored externally you don't have to retrain your bot when adding/changing questions. Since you have only one story for potentially 100's of questions, this means you can better handle side questions in more complex dialogs. 

## Run automated tests (experimental)
You can write test cases as you would write stories, except you should only have `utter_...` actions. 

```markdown
## chitchat.greet
* chitchat.greet
  - utter_reply_to_greet

## chitchat.how_are_you
* chitchat.how_are_you
  - utter_reply_to_how_are_you

## chitchat.are_you_a_robot
* chitchat.are_you_a_robot
  - utter_reply_to_are_you_a_robot

```

The test session sends the user utterances via http POST requests to the rasa_core server endpoint specified
in the `host` parameter. For this to work, make sure that your rasa core instance is running and has `rest:`
written in the `config/credentials.yml` file (this tells rasa_core to accept REST api requests).

You can run the tests with the command

```bash
python -m rasa_addons.tests --host localhost:5005 -t test_cases/ # -s(--shuffle) -u(--distinct) -v(--verbose)
```

You can put your test cases in different files starting with `test` (e.g. `test_chitchat.md`)in a directory.  
At this time, it only runs the test and outputs dialogues in the console (errors in red). There is no report (Help wanted).
You can also use `--distinct` to change the `sender_id` at every test case and `--shuffle` to shuffle test cases before running the tests.

