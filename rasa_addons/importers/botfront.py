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
from rasa.core.utils import get_file_hash

logger = logging.getLogger(__name__)


class BotfrontFileImporter(TrainingDataImporter):
    def __init__(
        self,
        config_file: Optional[Union[List[Text], Text]] = None,
        domain_path: Optional[Text] = None,
        training_data_paths: Optional[Union[List[Text], Text]] = None,
    ):
        self._domain_path = domain_path

        self._story_files, self._nlu_files = data.get_core_nlu_files(
            training_data_paths
        )

        self.core_config = {}
        self.nlu_config = {}
        if config_file:
            if not isinstance(config_file, list): config_file = [config_file]
            for file in config_file:
                if not os.path.exists(file): continue
                config = io_utils.read_config_file(file)
                lang = config["language"]
                self.core_config = {"policies": config["policies"]}
                self.nlu_config[lang] = {"pipeline": config["pipeline"], "data": lang}
    
    def path_for_nlu_lang(self, lang) -> Text:
        return [x for x in self._nlu_files if "{}.md".format(lang) in x]

    async def get_config(self) -> Dict:
        return self.core_config

    async def get_nlu_config(self, languages=True) -> Dict:
        if not isinstance(languages, list):
            languages = self.nlu_config.keys()
        return {
            lang: self.nlu_config[lang] if lang in languages else False
            for lang in self.nlu_config.keys()
        }

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:

        story_steps = await StoryFileReader.read_from_files(
            self._story_files,
            await self.get_domain(),
            interpreter,
            template_variables,
            use_e2e,
            exclusion_percentage,
        )
        return StoryGraph(story_steps)

    async def get_nlu_data(self, languages=True) -> Dict[Text, TrainingData]:
        language = None
        if isinstance(languages, str):
            language = languages
            languages = [language]
        if not isinstance(languages, list):
            languages = self.nlu_config.keys()
        td = {}
        for lang in languages:
            try:
                td[lang] = utils.training_data_from_paths(
                    self.path_for_nlu_lang(lang), lang,
                )
            except ValueError as e:
                if str(e).startswith("Unknown data format"):
                    td[lang] = TrainingData()
        if language: return td.get(language, TrainingData())
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
