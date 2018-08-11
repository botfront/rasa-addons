from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import glob
import random
import uuid

import os
import logging

from rasa_addons.superagent import SuperAgent
from rasa_core.actions.action import ActionListen
from rasa_core.domain import TemplateDomain
from typing import Text
import re
from rasa_core.channels.channel import UserMessage
from rasa_core.dispatcher import Dispatcher
from rasa_core.channels.channel import InputChannel, OutputChannel
from rasa_core import utils
from rasa_core.interpreter import RegexInterpreter
from rasa_core.nlg import TemplatedNaturalLanguageGenerator

import sys
logger = logging.getLogger()
R_TITLE = re.compile('##\s*(.+)')
R_USER = re.compile('\*\s*(.+)')
R_ACTION = re.compile('\s+- (utter_.+)')


class TestOutputChannel(OutputChannel):
    """Simple bot that outputs the bots messages to the command line."""

    def __init__(self, on_response, domain, processor):
        self.on_response = on_response
        self.domain = domain
        self.processor = processor

    def send_text_message(self, recipient_id, message):
        # type: (Text, Text) -> None
        self.on_response(message, recipient_id, self.processor)


class TestNLG(TemplatedNaturalLanguageGenerator):
    def generate(self, template_name, tracker, output_channel, **kwargs):
        return {"text": template_name}


class TestInputChannel(InputChannel):
    """Input channel that reads the user messages from the command line."""
    def __init__(self):
        self.on_message = None

    def start_sync_listening(self, message_handler):
        self.on_message = message_handler


class TestSession(object):
    def __init__(self,
                 model=None,
                 domain=None,
                 test_cases=None,
                 shuffle=False,
                 distinct=True,
                 rules=None,
                 interpreter=RegexInterpreter(),
                 create_output_channel=lambda on_response, domain, processor: TestOutputChannel(on_response, domain, processor),

                 ):
        self.model = model
        self.distinct = distinct
        self.interpreter = interpreter
        self.domain = TemplateDomain.load(domain)
        self.input_channel = TestInputChannel()
        self.create_output_channel = create_output_channel
        self.agent = self._create_agent(self.input_channel, self.interpreter, model, rules)

        self.stories = self._build_stories_from_path(test_cases)
        if shuffle:
            random.shuffle(stories)
        self._run_test_cases()
        self.failed = False

    def _run_test_cases(self):
        sender_id = "default"
        for story in self.stories:
            # self.agent.processor._get_tracker(sender_id)._reset()
            if self.distinct:
                sender_id = str(uuid.uuid4())
            self._run_story_test(sender_id, story)
        return True

    def _run_story_test(self, sender_id, story):
        utils.print_color('\n## ' + story['title'].upper(), utils.bcolors.OKBLUE)
        self.failed = False
        for index, step in enumerate(story['steps']):
            if self.failed is True:
                return
            utterance = step.pop(0)

            def on_response(response, recipient_id, proc):
                global failed
                if len(step) > 0:
                    expected = step.pop(0)
                    if response == expected:
                        utils.print_color("  - {}".format(response), utils.bcolors.OKGREEN)
                    else:
                        utils.print_color("  - {} (exp: {})".format(response, expected), utils.bcolors.FAIL)
                        utils.print_color("TEST CASE INTERRUPTED)".format(response, expected), utils.bcolors.FAIL)
                        # _print_slot_values(proc, recipient_id)
                        TestSession._restart_tracker(proc, recipient_id)

                        self.failed = True

                else:
                    utils.print_color("  - {} (not in case)".format(response), utils.bcolors.BOLD)

            utils.print_color(utterance, utils.bcolors.OKGREEN)

            self.input_channel.on_message(
                UserMessage(utterance, self.create_output_channel(on_response, self.domain, self.agent.processor), sender_id))

    @staticmethod
    def _concatenate_storyfiles(folder_path, prefix='test', output='aggregated_test_cases.md'):
        path_pattern = u'{}/{}*.md'.format(folder_path, prefix)
        filenames = glob.glob(path_pattern)
        with open(output, 'w') as outfile:
            for fname in filenames:
                with open(fname, 'r') as infile:
                    for line in infile:
                        outfile.write(line)
                    outfile.write("\n")

    @staticmethod
    def _restart_tracker(proc, sender_id):
        proc._get_tracker(sender_id)._reset()
        proc._get_tracker(sender_id).follow_up_action = ActionListen()

    @staticmethod
    def _print_slot_values(proc, recipient_id):
        slot_values = "\n".join(["\t{}: {}".format(s.name, s.value)
                                 for s in proc._get_tracker(recipient_id).slots.values()])
        print("Current slot values: \n{}".format(slot_values))

    @staticmethod
    def _build_stories_from_path(test_cases_path):

        test_cases_path = os.path.join(test_cases_path)
        if os.path.isdir(test_cases_path):
            output_path= os.path.join(test_cases_path, 'aggregated_tests_cases.md')
            TestSession._concatenate_storyfiles(test_cases_path, 'test', output_path)
            test_cases_path = output_path
        stories = []

        with open(test_cases_path, 'r') as test_file:
            lines = test_file.readlines()
        story = None
        for line in lines:
            m_story = R_TITLE.match(line)
            m_user = R_USER.match(line)
            m_action = R_ACTION.match(line)
            if m_story is not None:
                if story is not None:
                    stories.append(story)

                story = {
                    'title': m_story.group(1),
                    'steps': []
                }
            elif m_user is not None:
                story['steps'].append(['/' + m_user.group(1)])
            elif m_action is not None:
                story['steps'][-1].append(m_action.group(1))
        if story is not None:
            stories.append(story)
        return stories

    @staticmethod
    def _create_agent(input_channel, interpreter, model, rules):
        agent = SuperAgent.load(model,
                                interpreter=interpreter,
                                generator=TestNLG(None),
                                rules_file=rules
                                )
        agent.handle_channel(input_channel)
        return agent


def create_argparser():
    parser = argparse.ArgumentParser(
            description='runs the bot.')

    parser.add_argument('-m',
                        '--model',
                        help="Policy path",
                        required=True)
    parser.add_argument('-d', '--domain',
                        help="Domain path",
                        required=True)
    parser.add_argument('-t', '--tests',
                        help="Test cases/stories",
                        required=True)
    parser.add_argument('-s', '--shuffle',
                        help="Shuffle",
                        action="store_true",
                        default=False)
    parser.add_argument('-r', '--rules',
                        help="Rules",
                        default=None)
    parser.add_argument('-u', '--distinct',
                        help="Unique id for each case",
                        action="store_true",
                        default=False)
    return parser


if __name__ == "__main__":
    parser = create_argparser()
    args = parser.parse_args()

    TestSession(args.model, args.domain, args.tests, args.shuffle, args.distinct, args.rules)