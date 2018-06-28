import json
import difflib
import yaml
from rasa_addons.domains import DomainsMerger

def test_merge():
    DomainsMerger('domains', 'test_domain').merge().dump()
    with open('domains/merged_domains.yaml', 'r') as stream:
        source = yaml.load(stream)

    with open('domains/aggregated_domains.yaml', 'r') as stream:
        test = yaml.load(stream)

    # comparing strings instead
    source_dump = json.dumps(source, sort_keys=True)
    test_dump = json.dumps(test, sort_keys=True)

    assert source_dump == test_dump
