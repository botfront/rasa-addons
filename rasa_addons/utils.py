import yaml
import io

def load_yaml(rules_file):
    with io.open(rules_file, 'r', encoding='utf-8') as stream:
        try:
            return yaml.load(stream)
        except yaml.YAMLError as exc:
            raise ValueError(exc)
