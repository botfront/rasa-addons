import logging
import re

logger = logging.getLogger(__name__)

TEXT_VALIDATION_OPERATORS = [
    "is_exactly",
    "contains",
    "starts_with",
    "ends_with",
    "matches",
]

NUM_VALIDATION_OPERATORS = [
    "eq",
    "gt",
    "gte",
    "lt",
    "lte",
]

VALIDATION_OPERATORS = ["is_in"] + TEXT_VALIDATION_OPERATORS + NUM_VALIDATION_OPERATORS

def validate_with_rule(
    value,
    validation_rule
) -> bool:
    if validation_rule is None: return True
    operator, comparatum = validation_rule.get("operator"), validation_rule.get("comparatum")
    try:
        if operator not in VALIDATION_OPERATORS:
            raise ValueError(f"Validation operator '{operator}' not suported.")
        if operator == "is_in" and (not isinstance(comparatum, list) or any([not isinstance(str, e) for e in comparatum])):
            raise ValueError(f"Validation operator '{operator}' requires a comparatum that's a list of strings.")
        if operator in TEXT_VALIDATION_OPERATORS and not isinstance(comparatum, str):
            raise ValueError(f"Validation operator '{operator}' requires a string comparatum.")
        if operator in NUM_VALIDATION_OPERATORS:
            try: comparatum = float(comparatum)
            except ValueError:
                raise ValueError(f"Validation operator '{operator}' requires a numerical comparatum.")
    except ValueError as e:
        logger.error(str(e))
        return False
    if operator in TEXT_VALIDATION_OPERATORS + ["is_in"] and not isinstance(value, str):
        return False
    if operator == "is_in": return value in comparatum
    if operator == "contains": return value.contains(comparatum)
    if operator == "starts_with": return value.startswith(comparatum)
    if operator == "ends_with": return value.endswith(comparatum)
    if operator == "matches": return re.compile(comparatum).match(value)
    if operator in NUM_VALIDATION_OPERATORS:
        try: value = float(value)
        except ValueError: return False
    if operator == "eq": return value == comparatum
    if operator == "lt": return value < comparatum
    if operator == "lte": return value <= comparatum
    if operator == "gt": return value > comparatum
    if operator == "gte": return value >= comparatum
    return False