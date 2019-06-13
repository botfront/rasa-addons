from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_addons.nlu.components import BingSpellCheck
from rasa.nlu.training_data.message import Message


def _get_instance(config=None):
    return BingSpellCheck(config)


def _setup_example(config=None):
    instance = _get_instance(config=config)
    message = Message(text='This is a tst message')
    flagged_tokens = [
        {
          "offset": 10,
          "token": "tst",
          "type": "UnknownToken",
          "suggestions": [
            {
              "suggestion": "test",
              "score": 0.95155325585711
            },
            {
              "suggestion": "text",
              "score": 0.805342621979041
            }
          ]
        }
    ]

    return instance, message, flagged_tokens


def test_get_replacements():
    instance, message, flagged_tokens = _setup_example()

    tokens = instance._get_replacements(flagged_tokens)
    assert len(tokens) == 1
    token = tokens[0]
    assert 'offset' in token and 'token' in token and 'replacement' in token
    assert token['offset'] == 10 and token['token'] == 'tst' and token['replacement'] == 'test'


def test_replace():
    instance, message, flagged_tokens = _setup_example()
    tokens = instance._get_replacements(flagged_tokens)

    new_text = instance._replace(message.text, tokens)
    assert new_text == 'This is a test message'


def test_min_score():
    instance, message, flagged_tokens = _setup_example({'min_score':0.99})
    assert len(flagged_tokens) == 1

    tokens = instance._get_replacements(flagged_tokens)
    assert len(tokens) == 0

    text = instance._replace(message.text, tokens)
    assert text == 'This is a tst message'

def test_multiple_errors():
    instance = _get_instance()
    message = Message(text='Ths i a tst mesae')
    flagged_tokens = [
      {
        "offset": 0,
        "token": "Ths",
        "type": "UnknownToken",
        "suggestions": [
          {
            "suggestion": "This",
            "score": 0.825389307284585
          }
        ]
      },
      {
        "offset": 4,
        "token": "i",
        "type": "UnknownToken",
        "suggestions": [
          {
            "suggestion": "is",
            "score": 0.825389307284585
          }
        ]
      },
      {
        "offset": 8,
        "token": "tst",
        "type": "UnknownToken",
        "suggestions": [
          {
            "suggestion": "test",
            "score": 0.825389307284585
          },
          {
            "suggestion": "text",
            "score": 0.646529276890009
          }
        ]
      },
      {
        "offset": 12,
        "token": "mesae",
        "type": "UnknownToken",
        "suggestions": [
          {
            "suggestion": "message",
            "score": 0.825389307284585
          },
          {
            "suggestion": "mesa",
            "score": 0.761621385590906
          }
        ]
      }
    ]

    tokens = instance._get_replacements(flagged_tokens)
    assert len(tokens) == len(flagged_tokens)

    text = instance._replace(message.text, tokens)
    assert text == 'This is a test message'
