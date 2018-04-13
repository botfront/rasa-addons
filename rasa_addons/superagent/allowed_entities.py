
import io
import yaml
import logging
logger = logging.getLogger(__name__)


class AllowedEntities(object):
    def __init__(self, rules_file):
        self.allowed_entities = self._load_yaml(rules_file)

    def filter_entities(self, parse_data):

        if parse_data['intent']['name'] in self.allowed_entities.keys():
            filtered = filter(lambda ent: ent['entity'] in self.allowed_entities[parse_data['intent']['name']],
                              parse_data['entities'])
        else:
            filtered = []

        if len(filtered) < len(parse_data['entities']):
            # logging first
            logger.warn("entity(ies) were removed from parse stories")
            parse_data['entities'] = filtered

    @staticmethod
    def _load_yaml(rules_file):
        with io.open(rules_file, 'r', encoding='utf-8') as stream:
            try:
                return yaml.load(stream)
            except yaml.YAMLError as exc:
                raise ValueError(exc)
