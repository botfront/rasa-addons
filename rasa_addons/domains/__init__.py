import glob
from jsonmerge import Merger
import yaml
import os
import io
from collections import OrderedDict


class DomainsMerger(object):
    def __init__(self, folder_path, prefix='domain', output='aggregated_domains.yaml'):
        self.output = os.path.join(folder_path, output)
        self.schema = {
            "properties": {
                "actions": {
                    "mergeStrategy": "arrayMergeById",
                    "mergeOptions": {"idRef": "/"}
                },
                "intents": {
                    "mergeStrategy": "arrayMergeById",
                    "mergeOptions": {"idRef": "/"}
                },
                "entities": {
                    "mergeStrategy": "arrayMergeById",
                    "mergeOptions": {"idRef": "/"}
                }
            }
        }
        path_pattern = u'{}/{}*.y*ml'.format(folder_path, prefix)
        self.list_of_files = glob.glob(path_pattern)
        self.jsons = []
        self.merger = Merger(self.schema)
        self.merged = {}
        yaml.add_representer(OrderedDict, DomainsMerger.represent_ordereddict)

    def _load(self):
        for f in self.list_of_files:
            with io.open(f, 'r', encoding='utf-8') as stream:
                self.jsons.append(yaml.load(stream))

    def merge(self):
        self._load()
        merger = Merger(self.schema)
        self.merged = self.jsons[0]
        for i in range(1, len(self.jsons), 1):
            self.merged = merger.merge(self.merged, self.jsons[i])
        return self

    @staticmethod
    def represent_ordereddict(dumper, data):
        value = []

        for item_key, item_value in data.items():
            node_key = dumper.represent_data(item_key)
            node_value = dumper.represent_data(item_value)

            value.append((node_key, node_value))

        return yaml.nodes.MappingNode(u'tag:yaml.org,2002:map', value)

    yaml.add_representer(OrderedDict, represent_ordereddict)

    def dump(self):

        with io.open(self.output, 'w', encoding="utf-8") as outfile:
            yaml.dump(self.merged, outfile, default_flow_style=False, allow_unicode=True)

