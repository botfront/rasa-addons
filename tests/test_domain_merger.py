import yaml
from dm.utils.domains_merger import DomainsMerger

def test_merge():
    DomainsMerger('domains', 'test_domain').merge().dump()
    with open('domains/merged_domains.yaml', 'r') as stream:
        source = yaml.load(stream)

    with open('domains/aggregated_domains.yaml', 'r') as stream:
        test = yaml.load(stream)

    assert test == source
