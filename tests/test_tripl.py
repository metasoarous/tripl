from pytest import fixture
from hypothesis import given
from hypothesis.strategies import builds, text, lists

from tripl import tripl


def cft_cons(name):
    return tripl.entity_cons('cft.type:' + name, 'cft.' + name)


make_subject = cft_cons('subject')

schema = {
    'cft.seq:timepoint': {'db:valueType': 'db.type:ref',
                          'db:cardinality': 'db.cardinality:many'},
    'cft.seq:subject': {'db:valueType': 'db.type:ref'}}


@fixture
def triple_store():
    return tripl.TripleStore(schema=schema, default_cardinality='db.cardinality:one')


@given(lists(builds(make_subject, id=text())))
def test_issue14(triple_store, subjects):
    triple_store.assert_facts(subjects, id_attrs=['cft.subject:id'])
