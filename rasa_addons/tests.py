from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import re
import uuid
import glob
import random
import logging
import argparse

import requests

from rasa_core import utils
from rasa_core.nlg import TemplatedNaturalLanguageGenerator

logger = logging.getLogger(__name__)
R_TITLE = re.compile('##\s*(.+)')
R_USER = re.compile('\*\s*([^\[]+)(?:\s+(\[.+\]$))?')
R_ACTION = re.compile('\s+- (utter_\S+)(?:\s+(\[.+\]$))?')

class TestNLG(TemplatedNaturalLanguageGenerator):
    def generate(self, template_name, tracker, output_channel, **kwargs):
        return {"text": template_name}


class TestSession(object):
    def __init__(self,
                 host=None,
                 test_cases=None,
                 shuffle=False,
                 distinct=True,
                 ):

        self.endpoint = '{host}/webhooks/rest/webhook'.format(host=(host if host.startswith('http://') else 'http://' + host))
        self.distinct = distinct
        self.shuffle = shuffle
        self.stories = self._build_stories_from_path(test_cases)
        if shuffle:
            random.shuffle(self.stories)

    def _get_response(self, sender_id, message):
        response = requests.post(self.endpoint, json={
            "sender": sender_id,
            "message": message,
        })

        logger.debug('Response incoming with status code {}'.format(response.status_code))
        payload = response.json()

        if isinstance(payload, list):
            return list(map(lambda obj: obj['text'], payload))
        elif isinstance(payload, dict):
            return payload['text']
        else:
            raise TypeError('Rasa Core response in an unrecognized type: {type}\npayload = {payload}'.format(
                type=type(payload),
                payload=payload,
            ))

    def _run_story_test(self, sender_id, story):
        utils.print_color('\n## ' + story['title'].upper(), utils.bcolors.OKBLUE)
        self.failed = False
        logger.debug('Starting story: {story}'.format(story=story))
        for index, step in enumerate(story['steps']):
            if self.failed is True:
                return

            utterance = step.pop(0)

            logger.debug('Starting step {index}: {utterance}'.format(index=index, utterance=utterance))
            messages = self._get_response(sender_id, utterance)
            logger.debug('messages = {}'.format(messages))
            logger.debug('expected = {}'.format(step))
            utils.print_color('* {}'.format(utterance), utils.bcolors.OKBLUE)
            for message in messages:
                expected = step.pop(0) if len(step) > 0 else None
                if message == expected:
                    utils.print_color("  - {}".format(message), utils.bcolors.OKGREEN)
                else:
                    utils.print_color("  - {} (exp: {})".format(message, expected), utils.bcolors.FAIL)
                    utils.print_color("TEST CASE INTERRUPTED)".format(message, expected), utils.bcolors.FAIL)
                    self.failed = True

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

    def _should_append_line(self, query):
        logger.debug('Flags for this line: {}'.format(query))
        # check if there are flags at all
        if query is None:
            return True
        extract_flag = re.compile(r'^\[--(\w+)\]$')
        flags = [extract_flag.match(x).group(1) for x in query.split(' ')]
        if None in flags:
            logger.warning('Could not parse flags: {}\nThey should be in the format [--distinct] or [--shuffle]')

        distinct = 'distinct' in flags
        shuffle = 'shuffle' in flags

        logger.debug('Flags: {}'.format(flags))
        # Return false if either conditions not met
        if distinct:
            if not self.distinct:
                return False
        if shuffle:
            if not self.shuffle:
                return False

        # Otherwise return true
        return True

    def _build_stories_from_path(self, test_cases_path):
        logger.debug('BUILDING STORIES')

        test_cases_path = os.path.join(test_cases_path)
        if os.path.isdir(test_cases_path):
            output_path = os.path.join(test_cases_path, 'aggregated_tests_cases.md')
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
                if self._should_append_line(m_user.group(2)):
                    story['steps'].append(['/' + m_user.group(1)])
            elif m_action is not None:
                if self._should_append_line(m_action.group(2)):
                    story['steps'][-1].append(m_action.group(1))
        if story is not None:
            stories.append(story)
        return stories

    def run_test_cases(self):
        sender_id = str(uuid.uuid4())
        for story in self.stories:
            # self.agent.processor._get_tracker(sender_id)._reset()
            if self.distinct:
                sender_id = str(uuid.uuid4())
            self._run_story_test(sender_id, story)
        return True


def create_argparser():
    parser = argparse.ArgumentParser(
            description='runs the bot.')

    parser.add_argument('--host',
                        help="URL of the running rasa core instance",
                        required=True)
    parser.add_argument('-t', '--tests',
                        help="Test cases/stories",
                        required=True)
    parser.add_argument('-s', '--shuffle',
                        help="Shuffle",
                        action='store_true',
                        default=False)
    parser.add_argument('-u', '--distinct',
                        help="Unique id for each case",
                        action='store_true',
                        default=False)
    parser.add_argument('-v', '--verbose',
                        help="Show debug logs",
                        action='store_true',
                        default=False)
    return parser


if __name__ == "__main__":
    parser = create_argparser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format='%(message)s')

    runner = TestSession(args.host, args.tests, args.shuffle, args.distinct)
    runner.run_test_cases()
