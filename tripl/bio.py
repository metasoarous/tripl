import csv


def _traverse(obj, callback=None):
    '''Navigate to all nodes in a nested hash map.
    Function to traverse a nested hash map that conforms to what JSON allows:
    maps and lists. Note that this function only navigates the data structure
    (obj). Modification is provided through the callback.
    '''
    if isinstance(obj, dict):
        value = {k: _traverse(v, callback) for k, v in obj.items()}
    elif isinstance(obj, list):
        value = [_traverse(elem, callback) for elem in obj]
    else:
        value = obj

    if callback is None:  # if a callback is provided, call it to get the new value
        return value
    else:
        return callback(value)


def _traverse_modify(data, obj, ns=None):  # ns .. namespace, data as dict
    '''Traverse nested hash map and replace keys.
    Function that traverses and modifies a nested hash map (JSON format).
    Basically it substitutes keys using a map provided by the user. This map serves
    to map e.g. column headers of a table (CSV format) into tripl semantics
    like "namespace.entity:attribute" as well as adding the corresponding tripl
    type.

    Note that any e.g. column header that is not included in the attr_map is
    ignored, so we can select interesting columns in that way. If the attr_map
    specifies a key that is not found in the data, None is returned.

    Example:

    data = {
        'id': 4,
        'foo': 'bar',  # will not be included in selection
        'day1': '2017-06-07', 'day2': '2017-06-08',
        'time1': '13:17', 'time2': '13:21',
        'seq': 'ACTG'
        }

    attr_map = {
        'seq:id': 'id',
        'seq:notpresent': 'foobar',  # key not present returns None
        'seq:string': 'seq',
        'seq:date': [
            {'date:day': 'day1', 'date:time': 'time1'},
            {'date:day': 'day2', 'date:time': 'time2'}
        ]}

    _traverse_modify(data, attr_map, ns='toy')
    '''
    def transformer(value):

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            #entity = set()
            vc = {}
            # copy because iterate + mutate = bad idea, stackoverflow, 3346696
            for a, a_ in obj.items():
                a = ns + ':' + a if ns and len(a.split(':')) > 1 else a
                vc[a] = value.get(a)

            #assert len(entity) == 1, \
                #'The keys in the attribute map (obj) suggest heterogenous types.'

            if ns:
                vc.update({'tripl:type': ns})
            return vc
        else:
            return data.get(value, None)

    return _traverse(obj, callback=transformer)


def load_csv(fp, attr_map, ns=None):
    '''Turn CSV cells into triples.
    A helper function to turn data in CSV format into entity-attribute-value
    triples. The main ingredient that the user provides is an attribute map.
    This map serves to map e.g. column headers of a table (CSV format) into
    tripl semantics like "namespace.entity:attribute" as well as adding the
    corresponding tripl type. This might seem cumbersome but note that the CSV
    header is ambiguous about the data model.

    Example:

    import csv
    from tripl import tripl as t3

    fp = 'data/toy.csv'
    namespace = 'toy'

    attr_map = {
        'seq:id': 'id',
        'seq:virus': 'virus',
        'seq:notpresent': 'foobar',  # key not present returns None
        'seq:geo': 'geo',
        'seq:date': [
            {'date:day': 'date', 'date:time': 'time', 'date:id': 'date_id'}
        ],
        'seq:sample': [
            {'sample:id': 'sample'}
        ]
        }

    # create a triple generator
    gen = load_csv(fp, attr_map, namespace)

    # entries ought to look like this:
    # {'toy.seq:date': [{'toy.date:day': '2017-06-01',
    #    'toy.date:id': 't1',
    #    'toy.date:time': None,
    #    'toy:type': 'toy.type:date'}],
    #  'toy.seq:geo': 'jena',
    #  'toy.seq:id': 'i1',
    #  'toy.seq:notpresent': None,
    #  'toy.seq:sample': [{'toy.sample:id': 's1', 'toy:type': 'toy.type:sample'}],
    #  'toy.seq:virus': 'EBOV',
    #  'toy:type': 'toy.type:seq'}

    # load into triple store
    ts = t3.TripleStore()
    ts.assert_facts(gen, id_attrs=['toy.seq:id'])

    # query
    pull_expr = ['db:ident', 'toy.seq:id']
    list(ts.pull_many(pull_expr, {'toy:type': 'toy.type:seq'}))
    '''
    with open(fp) as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield _traverse_modify(data=row, obj=attr_map, ns=ns)
