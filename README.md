# Rasa Addons

![PyPI](https://img.shields.io/pypi/v/rasa-addons.svg)
![Travis](https://img.shields.io/travis/mrbot-ai/rasa-addons.svg)

A set of 🚀🚀🚀 components to be used with Botfront and/or Rasa.

[Botfront](https://github.com/botfront/botfront) is an open source chatbot platform built with Rasa.

## Disambiguation Policy

This policy implements fallback and suggestion-based disambiguation.

It works with the actions in ``rasa_addons.custom_actions``.

## Example usage

```
policies:
...
  - name: rasa_addons.core.policies.DisambiguationPolicy
    fallback_trigger: 0.30
    disambiguation_trigger: '$0 < 2 * $1'
    n_suggestions: 3
    excluded_intents:
      - ^chitchat\..*
    disambiguation_title:
      en: "Sorry, I'm not sure I understood. Did you mean..."
      fr: "J'ai mal compris. Voulez-vous dire..."
    intent_mappings:
      basics.yes:
        en: "Yes"
        fr: "Oui"
      basics.no:
        en: "No"
        fr: "Non"
      I_need_help:
        en: "Help me"
        fr: "Aidez-moi"
      I_come_from:
        en: "I come from {from}"
        fr: "Je viens de {from}"
      want_shirt:
        en: "I want a {color} shirt"
        fr: "Je veux un chandail {color}"
      deny_suggestions:
        en: "Something else"
        fr: "Autre chose"
...
```

### fallback_trigger

Float (default ``0.30``): if confidence of top-ranking intent is below this threshold, fallback is triggered. Fallback is an action that utters the template ``utter_fallback`` and returns to the previous conversation state.

### disambiguation_trigger

String (default ``'$0 < 2 * $1'``): if this expression holds, disambiguation is triggered. (If it has already been triggered on the previous turn, fallback is triggered instead.) Here this expression resolves to "the score of the top-ranking intent is below twice the score of the second-ranking intent". Disambiguation is an action that lets the user to choose from the top-ranking intents using a button prompt.

In addition, an 'Other' option is shown with payload ``/deny_suggestions`` is shown. When this option is chosen, an action is triggered that utters the template ``utter_ask_rephrase`` and returns to the previous conversation state.

### n_suggestions

Int (default 3): the maximum number of suggestions to display (excluding the 'Other' option).

### excluded_intents

List (regex string): any intent (exactly) matching one of these regular expressions will not be shown as a suggestion.

### disambiguation_title

Dict (language string -> string): localized disambiguation message title.

### intent_mappings

Dict (intent string -> language string -> string): localized representative button title for intents. If no title is defined for a given intent, the intent name is rendered instead. These titles support entity substitution: any entity name enclosed in curly brackets (``{entity}``) will be filled with entity information from the user utterance.

_Important:_ The title for the 'Other' option is also defined here.
