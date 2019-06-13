import editdistance
import operator


def distance(val1, val2):
    return editdistance.eval(val1, val2)


def ratio(val1, val2):
    max_distance = max(len(val1), len(val2))
    return int(100*(1 - distance(val1, val2) / max_distance))


def partial_distance(val1, val2):
    values = sorted([val1, val2], key=len, reverse=True)
    distances = []
    for i in range(0, len(values[0]) - len(values[1]) + 1):
        distances.append(editdistance.eval(values[1], values[0][i:i + len(values[1])]))
    return min(distances)


def partial_ratio(val1, val2):
    max_distance = len(val1)
    return int(100*(1 - partial_distance(val1, val2) / max_distance))


def _get_scorer(scorer_name):
    if scorer_name == 'ratio':
        return ratio
    elif scorer_name == 'partial_ratio':
        return partial_ratio


def extract(value, choices=[], scorer='ratio', limit=5):
    scorerfn = _get_scorer(scorer)
    distances = [(choice, scorerfn(value, choice)) for choice in choices]
    distances.sort(key=operator.itemgetter(1), reverse=True)
    return distances[0:limit]



