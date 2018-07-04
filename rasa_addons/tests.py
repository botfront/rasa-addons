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


class TestDispatcher(Dispatcher):

    def retrieve_template(self, template_key, filled_slots=None, lang='en', **kwargs):
        return {"text": template_key}


class TestInputChannel(InputChannel):
    """Input channel that reads the user messages from the command line."""
    def __init__(self):
        self.on_message = None

    def start_sync_listening(self, message_handler):
        self.on_message = message_handler


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


def main_test(model, domain, test_cases, shuffle, distinct, rules):

    interpreter = RegexInterpreter()
    domain = TemplateDomain.load(domain)
    input_channel = TestInputChannel()
    agent = create_agent(input_channel, interpreter, model, rules)

    stories = _build_stories_from_path(test_cases)
    if shuffle:
        random.shuffle(stories)
    _run_test_cases(agent, domain, input_channel, stories, distinct)


def create_agent(input_channel, interpreter, model, rules):
    agent = SuperAgent.load(model,
                            interpreter=interpreter,
                            create_dispatcher=lambda sender_id, output_channel, domain: TestDispatcher(sender_id, output_channel, domain),
                            rules_file=rules
    )
    agent.handle_channel(input_channel)
    return agent


def _run_test_cases(agent, domain, input_channel, stories, distinct):
    sender_id = str(uuid.uuid4())
    for story in stories:
        agent.processor._get_tracker(sender_id)._reset()
        if distinct:
            sender_id = str(uuid.uuid4())
        run_story_test(agent, domain, input_channel, sender_id, story)
    return True


failed = False


def run_story_test(agent, domain, input_channel, sender_id, story):
    global failed
    utils.print_color('\n## ' + story['title'].upper(), utils.bcolors.OKBLUE)
    failed = False
    for index, step in enumerate(story['steps']):
        if failed is True:
            return failed
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
                    _restart_tracker(proc, recipient_id)

                    failed = True

            else:
                utils.print_color("  - {} (not in case)".format(response), utils.bcolors.BOLD)

        utils.print_color(utterance, utils.bcolors.OKGREEN)

        input_channel.on_message(
            UserMessage(utterance, TestOutputChannel(on_response, domain, agent.processor), sender_id))

    return failed


def _concatenate_storyfiles(folder_path, prefix='test', output='aggregated_test_cases.md'):
    path_pattern = u'{}/{}*.md'.format(folder_path, prefix)
    filenames = glob.glob(path_pattern)
    with open(output, 'w') as outfile:
        for fname in filenames:
            with open(fname, 'r') as infile:
                for line in infile:
                    outfile.write(line)
                outfile.write("\n")


def _restart_tracker(proc, sender_id):
    proc._get_tracker(sender_id)._reset()
    proc._get_tracker(sender_id).follow_up_action = ActionListen()


def _print_slot_values(proc, recipient_id):
    slot_values = "\n".join(["\t{}: {}".format(s.name, s.value)
                             for s in proc._get_tracker(recipient_id).slots.values()])
    print("Current slot values: \n{}".format(slot_values))


def _build_stories_from_path(test_cases_path):

    root = os.path.dirname(sys.argv[0])
    test_cases_path = os.path.join(test_cases_path)
    if os.path.isdir(test_cases_path):
        output_path= os.path.join(test_cases_path, 'aggregated_tests_cases.md')
        _concatenate_storyfiles(test_cases_path, 'test', output_path)
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


if __name__ == "__main__":
    parser = create_argparser()
    args = parser.parse_args()

    main_test(args.model, args.domain, args.tests, args.shuffle, args.distinct, args.rules)