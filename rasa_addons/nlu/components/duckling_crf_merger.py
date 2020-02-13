from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
from rasa.nlu.components import Component
from typing import Any, List, Optional, Text, Dict

from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.model import Metadata
from rasa.nlu.training_data import Message

logger = logging.getLogger(__name__)


class DucklingCrfMerger(Component):
    """Merges Duckling and CRF entities"""

    name = "DucklingCrfMerger"

    provides = []

    defaults = {
        "entities": None,
        "duckling_name": "rasa_addons.nlu.components.duckling_http_extractor.DucklingHTTPExtractor",
    }

    def __init__(self, component_config=None):
        # type: (Text, Optional[List[Text]]) -> None

        super(DucklingCrfMerger, self).__init__(component_config)

    @classmethod
    def create(
        cls, component_config: Dict[Text, Any], config: RasaNLUModelConfig
    ) -> "DucklingCrfMerger":
        return cls(component_config)

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None
        crf_entities = list(
            filter(
                lambda e: e["extractor"] == "ner_crf"
                and e["entity"] in self.component_config["entities"].keys(),
                message.get("entities"),
            )
        )
        indices_to_remove = []

        for index, duck_entity in enumerate(message.get("entities")):
            if duck_entity["extractor"].startswith(
                self.component_config["duckling_name"]
            ):
                # looking for CRF entities surrounding the duckling one matching config settings
                containing_crf = list(
                    filter(
                        lambda e: e["start"] <= duck_entity["start"]
                        and e["end"] >= duck_entity["end"]
                        and duck_entity["entity"]
                        in self.component_config["entities"][e["entity"]],
                        crf_entities,
                    )
                )
                # list -> single object
                containing_crf = (
                    containing_crf[0]
                    if type(containing_crf) is list and len(containing_crf) > 0
                    else None
                )
                if containing_crf is not None:
                    # Add duckling value + additional infos
                    containing_crf["value"] = duck_entity["value"]
                    containing_crf["additional_info"] = duck_entity["additional_info"]
                    indices_to_remove.append(index)

        # Remove merged duckling entities
        for i in sorted(indices_to_remove, reverse=True):
            del message.get("entities")[i]

    @classmethod
    def load(
        cls,
        component_meta: Dict[Text, Any],
        model_dir: Text = None,
        model_metadata: Metadata = None,
        cached_component: Optional["DucklingCrfMerger"] = None,
        **kwargs: Any
    ) -> "DucklingCrfMerger":
        return cls(component_meta)
