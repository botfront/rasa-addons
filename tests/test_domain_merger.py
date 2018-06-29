import json

import os
import yaml
from rasa_addons.domains import DomainsMerger

ROOT_PATH = os.path.join(os.getcwd(), 'tests')


def test_merge():
    DomainsMerger(os.path.join(ROOT_PATH, 'domains'), 'test_domain').merge().dump()
    with open(os.path.join(ROOT_PATH, 'domains/merged_domains.yaml'), 'r') as stream:
        source = yaml.load(stream)

    with open(os.path.join(ROOT_PATH, 'domains/aggregated_domains.yaml'), 'r') as stream:
        test = yaml.load(stream)

    # comparing strings instead
    source_dump = json.dumps(source, sort_keys=True)
    test_dump = json.dumps(test, sort_keys=True)

    assert source_dump == test_dump
