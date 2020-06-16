import logging
import re

logger = logging.getLogger(__name__)

TEXT_VALUE_OPERATORS = [
    "is_in",
    "is_exactly",
    "contains",
    "starts_with",
    "ends_with",
    "matches",
    "longer",
    "longer_or_equal",
    "shorter",
    "shorter_or_equal",
    "email",
    "word",
]

NUM_VALUE_OPERATORS = [
    "eq",
    "gt",
    "gte",
    "lt",
    "lte",
]

TEXT_COMPARATUM_OPERATORS = [
    "is_exactly",
    "contains",
    "starts_with",
    "ends_with",
    "matches",
]

NUM_COMPARATUM_OPERATORS = [
    "eq",
    "gt",
    "gte",
    "lt",
    "lte",
    "longer",
    "longer_or_equal",
    "shorter",
    "shorter_or_equal",
]

OTHER_COMPARATUM_OPERATORS = ["is_in", "email", "word"]

VALIDATION_OPERATORS = TEXT_VALUE_OPERATORS + NUM_VALUE_OPERATORS


def validate_with_rule(value, validation_rule) -> bool:
    if validation_rule is None:
        return True
    operator, comparatum = (
        validation_rule.get("operator"),
        validation_rule.get("comparatum"),
    )
    try:
        if operator not in VALIDATION_OPERATORS:
            raise ValueError(f"Validation operator '{operator}' not suported.")
        if operator == "is_in" and (
            not isinstance(comparatum, list)
            or any([not isinstance(e, str) for e in comparatum])
        ):
            raise ValueError(
                f"Validation operator '{operator}' requires a comparatum that's a list of strings."
            )
        if operator in TEXT_COMPARATUM_OPERATORS and not isinstance(comparatum, str):
            raise ValueError(
                f"Validation operator '{operator}' requires a string comparatum."
            )
        if operator in NUM_COMPARATUM_OPERATORS:
            try:
                comparatum = float(comparatum)
            except ValueError:
                raise ValueError(
                    f"Validation operator '{operator}' requires a numerical comparatum."
                )
    except ValueError as e:
        logger.error(str(e))
        return False
    if operator in TEXT_VALUE_OPERATORS and not isinstance(value, str):
        return False
    if operator in NUM_VALUE_OPERATORS:
        try:
            value = float(value)
        except ValueError:
            return False
    if operator == "is_in":
        return value in comparatum
    if operator == "is_exactly":
        return value == comparatum
    if operator == "contains":
        return comparatum in value
    if operator == "starts_with":
        return value.startswith(comparatum)
    if operator == "ends_with":
        return value.endswith(comparatum)
    if operator == "matches":
        return re.compile(comparatum).match(value) is not None
    if operator == "longer":
        return len(value) > comparatum
    if operator == "longer_or_equal":
        return len(value) >= comparatum
    if operator == "shorter":
        return len(value) < comparatum
    if operator == "shorter_or_equal":
        return len(value) <= comparatum
    if operator == "email":
        return (
            re.compile(
                r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
            ).match(value) is not None
        )
    if operator == "word":
        return re.compile(r"^[^\W\d_]+$").match(value) is not None

    if operator == "eq":
        return value == comparatum
    if operator == "lt":
        return value < comparatum
    if operator == "lte":
        return value <= comparatum
    if operator == "gt":
        return value > comparatum
    if operator == "gte":
        return value >= comparatum
    return False
