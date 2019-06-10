from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


from rasa_addons.nlu.components.fuzzy_matcher import process


def test_partial_distance():
    query = "orange"
    candidates = ['orangoutan', 'orange tango', 'olive martini', 'orangemartinin', 'martininorange']
    partial_distances = [process.partial_distance(query, val) for val in candidates]
    assert partial_distances == [1, 0, 5, 0, 0]


def test_ratio():

    query = "orange"
    val = ['blue', 'orange', 'brown', 'ornage', 'range', 'angel', 'gang', 'ang']
    fuzzy = process.extract(query, val, limit=3, scorer='ratio')
    assert fuzzy == [('orange', 100), ('range', 83), ('ornage', 66)]


def test_partial_ratio():
    query = "orange"
    val = ['blue tango', 'orange tango', 'brown tango']
    fuzzy = process.extract(query, val, limit=3, scorer='partial_ratio')
    assert fuzzy == [('orange tango', 100), ('blue tango', 50), ('brown tango', 50)]

