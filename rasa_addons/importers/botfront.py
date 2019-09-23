import logging
import os
import copy
from typing import Optional, Text, Union, List, Dict

from rasa import data
from rasa.core.domain import Domain, InvalidDomain
from rasa.core.interpreter import RegexInterpreter, NaturalLanguageInterpreter
from rasa.core.training.structures import StoryGraph
from rasa.core.training.dsl import StoryFileReader
from rasa.importers import utils
from rasa.importers.importer import TrainingDataImporter
from rasa.nlu.training_data import TrainingData
from rasa.utils import io as io_utils
from  rasa.core.utils import get_file_hash

logger = logging.getLogger(__name__)


class BotfrontFileImporter(TrainingDataImporter):

    def __init__(
        self,
        config_paths: Optional[Dict[Text, Text]] = None,
        domain_path: Optional[Text] = None,
        training_data_path: Optional[Text] = None,
    ):
        # keep only policies in core_config
        self.core_config = {'policies': io_utils.read_config_file(
            config_paths[list(config_paths.keys())[0]]
        )['policies']}
        self._stories_path = os.path.join(training_data_path, 'stories.md')
        
        # keep all but policies in nlu_config
        self.nlu_config = {}
        for lang in config_paths:
            self.nlu_config[lang] = io_utils.read_config_file(config_paths[lang])
            del self.nlu_config[lang]['policies']
            self.nlu_config[lang]['data'] = 'data_for_' + lang # so rasa.nlu.train.train makes the right get_nlu_data call
            self.nlu_config[lang]['path'] = os.path.join(training_data_path, 'nlu', '{}.md'.format(lang))

        self._domain_path = domain_path

    async def get_core_config(self) -> Dict:
        return self.core_config
    
    async def get_nlu_config(self, languages = True) -> Dict:
        if not isinstance(languages, list):
            languages = self.nlu_config.keys()
        return {lang: self.nlu_config[lang] if lang in languages else False for lang in self.nlu_config.keys()}

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:

        story_steps = await StoryFileReader.read_from_files(
            [self._stories_path],
            await self.get_domain(),
            interpreter,
            template_variables,
            use_e2e,
            exclusion_percentage,
        )
        return StoryGraph(story_steps)

    async def get_stories_hash(self):
        # Use a file hash of stories file to figure out Core fingerprint, instead of
        # storygraph object hash which is unstable
        return get_file_hash(self._stories_path)

    async def get_nlu_data(self, languages = True) -> Dict[Text, TrainingData]:
        if isinstance(languages, str) and languages.startswith('data_for_'):
            lang = languages.replace('data_for_', '')
            return utils.training_data_from_paths([self.nlu_config[lang]['path']], 'xx')
        if not isinstance(languages, list):
            languages = self.nlu_config.keys()
        td = {}
        for lang in languages:
            try:
                td[lang] = utils.training_data_from_paths([self.nlu_config[lang]['path']], 'xx')
            except ValueError as e:
                if str(e).startswith("Unknown data format"):
                    from rasa.nlu.training_data import TrainingData
                    td[lang] = TrainingData()
        return td

    async def get_domain(self) -> Domain:
        domain = Domain.empty()
        try:
            domain = Domain.load(self._domain_path)
            domain.check_missing_templates()
        except InvalidDomain as e:
            logger.warning(
                "Loading domain from '{}' failed. Using empty domain. Error: '{}'".format(
                    self._domain_path, e.message
                )
            )

        return domain
