"""
Tripy - a python library for working with Trip semantic graph data inspired by Datomic, DataScript, and their
roots in the Semantic Web.

Trip is our working name for a simple data format, inspired by Datomic and DataScript's transaction forms, the
EAV index model, the Alternative RDF-JSON specification, and more broadly, a generalized and simplified
interpretation of RDF. The README has more context on how all of these things fit together philosophically.

Broadly speaking, our goal is a universal data model flexible enough to allow us to express all of our
knowledge in a single format, for simpler bioinformatics, data science and systems programming. This is the
problem RDF sets out to solve, as part of the vision of the Semantic Web. Yet while it lives us to many of its
goals, RDF has a number of features which make it very 
"""

from __future__ import print_function
import collections
import uuid
import json
import pprint
import copy


# Util
# ----

def log(name, value):
    print(name)
    pprint.pprint(value)
    print("\n")

def some(xs, default=None):
    "return some thing from the set, or None if nothing"
    if isinstance(xs, (str, unicode, int, float, bool, dict, Entity, uuid.UUID)):
        return xs
    else:
        try:
            return next(iter(xs))
        except TypeError:
            # Then not iterable
            return xs if xs != None else default
        except StopIteration:
            # Then empty
            return default



# Now for the code:
# =================


class TupleIndex(object):
    def __init__(self, depth=2, vals_container=set):
        self.vals_container = vals_container
        self.depth = depth
        self.keys = {}

    def __iter__(self):
        for k, vs in self.keys:
            if self.depth == 1:
                for v in vs:
                    yield k, v
            else:
                for tupl in v:
                    yield (k,) + tupl

    def get(self, tupl, default=None):
        sub_index = self.keys.get(tupl[0])
        if len(tupl) == 1:
            return sub_index or default
        else:
            if sub_index:
                return sub_index.get(tupl[1:]) or default
        return default

    def get_some(self, tupl):
        return some(self.get(tupl))

    def add(self, tupl):
        sub_index = self.keys.get(tupl[0])
        if len(tupl) == 2:
            if not sub_index:
                self.keys[tupl[0]] = self.vals_container()
            self.keys[tupl[0]].add(tupl[1])
        else:
            if not sub_index:
                sub_index = TupleIndex(depth=self.depth - 1, vals_container=self.vals_container)
                self.keys[tupl[0]] = sub_index
            sub_index.add(tupl[1:])

    def retract(self, tupl):
        sub_index = self.keys.get(tupl[0])
        if sub_index and len(tupl) == 2:
           sub_index.remove(tupl[1])
        else:
           sub_index.retract(tupl[1:])

    def to_dict(self):
        return {k: v.to_dict() if self.depth > 1 else v for k, v in self.keys.items()}

    def contains(self, tupl):
        return (tupl[0] in self.keys) \
                and (len(tupl) == 1 \
                     or (tupl[1] in self.keys
                         if self.depth == 1
                         else self.get([tupl[0]]).contains(tupl[1:])))




#def _triple_index(vals_container=set):
    #return collections.defaultdict(lambda: collections.defaultdict(vals_container))

def _triple_index(vals_container=set):
    return TupleIndex()


# Would be great to implement something analagous to the entity API, but would need to have schema I think
# to traverse the references
class Entity(object):
    def __init__(self, graph, ident, namespace=None):
        self._graph = graph
        # TODO Should allow for entity in leiu of ident
        self.ident = ident
        self._entity = graph._eav_index.get([ident])
        # Question: Should we call this type or namespace?
        self.namespace = namespace
        self.namespace = namespace or graph._eav_index.get_some([ident, 'tripl:type'])

    def __repr__(self):
        r = self.namespace + ':' if self.namespace else ''
        return r + str({k: self._entity.get([k]) for k in self.keys()})

    def __getitem__(self, key):
        # This is really the only magic to this object, over just looking at the EAV index
        # Should probably have these globally cached or something, so we don't create dups?
        # lazy_ref means that we allow you to infer relationships without assigning a reference type
        if self.namespace and len(key.split(':')) == 1:
            return self.__getitem__(self.namespace + ':' + key)
        if self._graph._ref_attr(key) or \
                (self._graph.lazy_refs \
                 and self._entity.get([key]) \
                 and all(self._graph._eav_index.contains([v]) for v in self._entity.get([key]))):
            return [type(self)(self._graph, ident) for ident in self._entity.get([key])]
        if str(key).split(':')[-1][0:1] == '_':
            namespace, name = key.split(':')
            name = name[1:]
            key = namespace + ':' + name
            if self._graph._ref_attr(key):
                return list(type(self)(self._graph, v) for v in self._graph._vae_index.get([self.eid, key]))
            else:
                # reverse lookups only supported currently with ref typing; need to generalize to do a scan if
                # graph.lazy_refs is truthy; TODO
                return []
        else:
            return self._entity.get([key])

    def some(self, key, default=None):
        return some(self[key], default=default)

    def __getattr__(self, key):
        if self.namespace and len(key.split(':')) == 1:
            return self[self.namespace + ':' + key]
        else:
            return self[key]

    def __contains__(self, key):
        if key in self._entity.keys:
            return True
        else:
            if str(key).split(':')[-1][0:1] == '_':
                key = key.replace('_', '')
                return self._graph._ref_attr(key)

    def __len__(self):
        return len(self._entity.keys)

    def keys(self):
        if self._entity:
            keys = self._entity.keys.keys()
            if 'db:ident' not in keys:
                return ['db:ident'] + keys
            return keys
        else:
            return []


#def generate_entity_class(name, namespace):
    #return type(name, (Entity), {



def reverse_lookup(attr_name):
    parts = attr_name.split(':')
    if parts[-1][0] == '_'[0]:
        parts[-1] = parts[-1][1:]
        return ':'.join(parts)

def base_schema(ident_attr):
    return [{ident_attr: 'db:schema',
             'db:attributes': [
                 {ident_attr: 'db:cardinality',
                  'db:cardinality': 'db.cardinality:one'},
                 {ident_attr: 'db:valueType',
                  'db:cardinality': 'db.cardinality:one'},
                 {ident_attr: 'db.schema:attributes',
                  'db:cardinality': 'db.cardinality:many',
                  'db:valueType': 'db.type:ref'},
                 {ident_attr: 'db.schema:types',
                  'db:cardinality': 'db.cardinality:many',
                  'db:valueType': 'db.type:ref'},
                 {ident_attr: 'db.refs:lazy',
                  'db:cardinality': 'db.cardinality:one'},
                 {ident_attr: 'db.cardinality:default',
                  'db.cardinality': 'db.cardinality:one'}]}]


class TripleStore(object):
    #def __new__(cls, schema=None, facts=None):
        #if 
        
    def __init__(self, schema=None, facts=None, lazy_refs=None, default_cardinality=None, types=None,
            ident_attr="db:ident", id_attrs=None):
        """Construct a new TripleStore instance, with the optional facts attribute asserted as via
        assert_facts. The schema can be specified by the facts data, by the schema attribute, and by the
        global default setting kw attrs in this signature, and precedence is taken in that order.

        * 
        
        The schema dict should map attribute names to schema attributes (`db:cardinality` and
        `db:valueType: db.type:ref` only for the moment), and should not be updated once set (for now at
        least). Additional options are:
            """
        # 1. Load all facts, which may include schema
        #
        # Start by assuming everything cardinality many with lazy refs, to load everything without conflict
        self.default_cardinality = 'db.cardinality:many'
        self.lazy_refs = True
        # Set up index
        self._eav_index = _triple_index(vals_container=set)
        self._vae_index = _triple_index(vals_container=set)
        # This must be statically set for now? Should check compatibility with facts?
        self.ident_attr = ident_attr
        self.assert_facts(base_schema(self.ident_attr))
        if facts:
            self.assert_facts(facts, id_attrs=id_attrs)

        # 2. Load schema, if specified
        if schema:
            self.assert_schema(schema)

        # 3. Query current schema, and update with kw_args as appropriate, and cache as attributes
        # (semi-static; could generalize with method calls based on schema)
        schema_pull = self.pull(['*'], 'db:schema')
        lazy_refs = lazy_refs or some(schema_pull.get('db.refs:lazy'))
        self.lazy_refs = True if lazy_refs == None else lazy_refs
        # Setting default cardinality
        default_cardinality = default_cardinality or some(schema_pull.get('db.cardinality:default'))
        self.default_cardinality = 'db.cardinality:many' if default_cardinality == None else default_cardinality
        self.assert_fact({
            self.ident_attr: 'db:schema',
            'db.refs:lazy': self.lazy_refs,
            'db.cardinality:default': self.default_cardinality})
        # Now we set up all the defaults
        # Should probably eventually be able to specify vals container, primary key strategy, etc.;
        self.types = types
        # other indices to follow possibly; well see what DS does
        # Reload facts to flush out indices, constraints, etc. (will this be safe?)
        # No! Not safe! Duplicates!
        # Like... if schema has changed, create a new tripl store with explicit schema, and then return that?
        # Have to do this in new above
        # Or... can we just think through the things that need to be flushed and do that post schema change in
        # update? That seems to be the sanest way if we don't want to have to specify schema everywhere
        #if facts:
            #self.assert_facts(facts, id_attrs=id_attrs)

    # This could get rather interesting...
    # Only semi-public for the moment

    def entity(self, eid, namespace=None):
        "Return a read only entity dict representation for a given eid."
        return Entity(self, eid, namespace=namespace)


    # Should define triples iterator
    # Define write to file


    def assert_schema(self, schema):
        def attr_entity(attr, attr_schema):
            attr_schema = copy.deepcopy(attr_schema)
            attr_schema[self.ident_attr] = attr
            return attr_schema
        eid = self.assert_fact({self.ident_attr: 'db:schema',
                                'db:attributes': [
                                    attr_entity(attr, attr_schema)
                                    for attr, attr_schema in schema.items()]})
        return eid

    def schema(self, attr=None, meta_attr=None):
        if attr and meta_attr:
            # This could be optimized
            #return some(self.schema(attr).get(meta_attr))
            return self._eav_index.get([attr, meta_attr])
        elif attr:
            # Could work to get the cards right here
            _entity = self._eav_index.get([attr])
            return _entity.to_dict().copy() if _entity else {} # Will this work? XXX
        else:
            return [self.schema(a) for a in self._eav_index.get(['db:schema', 'db:attributes'])]


    # Some implementation details:

    def _attr_cardinality(self, attr):
        attr_schema = self.schema(attr)
        if attr_schema:
            return some(attr_schema.get('db:cardinality', [self.default_cardinality]))

    def _attr_type(self, attr):
        attr_schema = self.schema(attr)
        if attr_schema:
            schema = attr_schema.get('db:valueType')
            return some(schema) if schema else None

    def _ref_attr(self, attr):
        lookup = reverse_lookup(attr)
        if lookup:
            return self._ref_attr(lookup)
        else:
            return self._attr_type(attr) == 'db.type:ref'

    def _card_one(self, attr):
        lookup = reverse_lookup(attr)
        if lookup:
            # Just always assume sets for reverse lookups
            return False
            # Todo; if you have a unique attribute here, you can do one-one
            #return blah if self._unique(lookup) else blah
        elif attr == 'db:cardinality':
            return 'db.cardinality:one'
        else:
            return self._attr_cardinality(attr) == 'db.cardinality:one'

    def _assert_triple(self, triple):
        e, a, v = triple
        # First if cardinality one, remove any other values
        if self._card_one(a) and self._eav_index.get([e, a]):
            for x in self._eav_index.get([e, a]).copy():
                if x != v:
                    self._retract_triple((e, a, x))
        # Add the canonical eav index
        self._eav_index.add([e, a, v])
        if self._ref_attr(a):
            self._vae_index.add([v, a, e])
        # And a lazy index of 

    def _retract_triple(self, triple):
        e, a, v = triple
        # Have to be careful here; remove only removes the first entry; Should just be using sets
        self._eav_index.remove([e, a, v])
        reverse_index = self._vae_index.get([v])
        if reverse_index:
            reverse_attr_index = reverse_index.get([a])
            if reverse_attr_index and e in reverse_attr_index:
                reverse_attr_index.remove(e)


    # Should the following two be public?
    def _assert_val(self, e, a, val, id_attrs=None, _ids=None):
        "Asserts a val as either a literal or a nested entity; recursively defers to _assert_triple"
        if isinstance(val, dict):
            val = self._assert_dict(val, id_attrs=id_attrs, _ids=_ids)
        self._assert_triple((e, a, val))

    def _assert_vals(self, e, a, vals, id_attrs=None, _ids=None):
        "Asserts some number of vals as by _assert_val"
        for val in vals:
            self._assert_val(e, a, val, id_attrs=id_attrs, _ids=_ids)

    def _resolve_eid(self, fact_dict, id_attrs=None, _ids=None):
        ident_val = some(fact_dict.get(self.ident_attr))
        if id_attrs:
            # This is not particularly efficient; should be using an aev or ave index
            id_facts = {a: _ids[a].get(fact_dict[a]) or some(self.match_pattern({a: fact_dict[a]}))
                        for a in id_attrs if a in fact_dict}
            if ident_val:
                # make sure no conflicting facts?
                if any(id_facts.values()):
                    print("Warning! Conflicting values in _resolve_eid!")
                eid = ident_val
            else:
                eids = set(v for v in id_facts.values() if v)
                if eids:
                    if len(eids) > 1:
                        print("Warning! Conflicting values in _resolve_eid (2)!")
                    eid = some(eids)
                else:
                    eid = uuid.uuid1()
            # Set the corresponding value in ids map for future
            for k in id_facts:
                _ids[k][fact_dict[k]] = eid
        else:
            eid = ident_val or uuid.uuid1()
        return str(eid)


    def _assert_dict(self, fact_dict, id_attrs=None, _ids=None):
        # Is it possible to middleware-factor local db:id vs global db:ident :vs native uuid or tuples?
        eid = self._resolve_eid(fact_dict, id_attrs=id_attrs, _ids=_ids)
        for a, v in fact_dict.items():
            if isinstance(v, list):
                self._assert_vals(eid, a, v, id_attrs=id_attrs, _ids=_ids)
            else:
                self._assert_val(eid, a, v, id_attrs=id_attrs, _ids=_ids)
        if not fact_dict.get(self.ident_attr):
            self._assert_val(eid, self.ident_attr, eid, id_attrs=id_attrs, _ids=_ids)
        # Returns eid so you can make connections; need to generalize for references
        return eid

    def _retract_triples(self, triples):
        for triple in triples:
            self._retract_triple(triple)


    # Our public API for asserting and retracting facts

    def assert_fact(self, fact, id_attrs=None, _ids=None):
        """Assert fact about an entity as a dict or as a single eav triple. Dictionaries are interpretted as a set of eav triples
        where e is a unique identitier for the entity (uuid, globally namespaced keyword, web url,
        whatever...), either specified in the dictionary, or generated for you (by default as a random uuid).
        The a, v components of the triples for such an e correspond with the key value pairs of the map.
        The vals of the dictionary should be a single value, or list of values for db.cardinality:many
        attributes. Identity attr can be set on graph instantiation."""
        if isinstance(fact, dict):
            # Returns eid
            return self._assert_dict(fact, id_attrs=id_attrs, _ids=_ids)
        else:
            self._assert_triple(fact)

    def assert_facts(self, facts, id_attrs=None, _ids=None):
        """As with assert_fact, except asserts either a collection of facts via assert_fact, or if passed a
        dictionary, interprets as a eav index to merge in. If passed in another TripleStore, interprets as
        it's eav index, thereby merging the graphs :-)"""
        if isinstance(facts, dict):
            # Then merge as an eav index of values
            for e, d in facts.items():
                for a, vs in d.items():
                    for v in vs:
                        # May be more lookup time than if we look up and remember the nested dicts as we go
                        self.assert_fact((e, a, v))
        elif isinstance(facts, TripleStore):
            # TODO; think about what id_attrs might mean here
            # Mmmm... need to update? use to_dict if needed...
            self.assert_facts(facts._eav_index)
        else:
            _ids = _ids or collections.defaultdict(dict)
            for fact in facts:
                self.assert_fact(fact, id_attrs=id_attrs, _ids=_ids)

    @classmethod
    def load(cls, filename, schema=None, id_attrs=None): # add format option eventually?
        "Load data from a JSON file, and assert as with assert_facts."
        with open(filename, 'rb') as fp:
            data = json.load(fp)
            return cls(facts=data, schema=schema, id_attrs=id_attrs)

    @classmethod
    def loads(cls, filenames, schema=None, id_attrs=None):
        """Load data as with load_file, but reduces over facts from all filenames. Takes the schema from the
        first file as default for the global defaults schema parameters. Per attribute schema should absorb
        from each though."""
        result = cls.load(filenames[0], schema=schema, id_attrs=id_attrs)
        for filename in filenames[1:]:
            with open(filename, 'rb') as fp:
                data = json.load(fp)
                result.assert_facts(data, id_attrs=id_attrs)
        return result

    def dump(self, filename):
        "Save semantic graph to a json file as an EAV index."
        with open(filename, 'w') as fp:
            json.dump(self._eav_index.to_dict(), fp, default=list)


    # # Now our query engine
    # We have a few different kind of queries we want to be able to execute

    # Match pattern
    # simple
    #{'cft:id': 'dk398fjd03kjdfkj23'}
    # more interesting
    #{'cft:dataset': {'cft.dataset:id': 'whatever-crazy-id'}}
    # This can more or less always be done efficiently very easily, and extends on base GraphQL, om-next etc
    # significantly;

    # My python Datalog grammar proposal:
    ##base query; matches graph
    #{'find': ['?x', '?y'],
     #'where': [['?x', 'person:parent', '?y']
               #['?y', 'person:name', 'joe']]
     ##optionally:
     #'rules': [[['ancestor', '?x', '?y'],
                #['?x', 'person:parent', '?y']],
               #[['ancestor', '?x', '?z'],
                #['?x', 'person:parent', '?y'],
                #['ancestor' '?y', '?z']]]
     #'take': 20,
     #'sort': 'db:ident',
     #}
     # Could in memory be evaluated via a local DataScript JS server via https://pypi.python.org/pypi/PyExecJS

    # Going to start for now with the simple pull and match queries

    def _entity_match(self, entity, pattern):
        "For a match, at least one of the pattern options must match"
        return all(entity.get([k], set()).intersection(v if isinstance(v, (list, set)) else [v])
                   for k, v in pattern.items())

    # Should probably rename just match, instead of match pattern; then can do match_some for get first?
    def match_pattern(self, pattern):
        xf_subpattern = lambda v: (self.match_pattern(v) if isinstance(v, dict) else v)
        pattern = {k: xf_subpattern(v) for k, v in pattern.items()}
        return set(eid for eid, entity
                       in self._eav_index.keys.items()
                       if self._entity_match(entity, pattern))

    def entities(self, pattern, namespace=None):
        return [self.entity(some(ident), namespace=namespace) for ident in self.match_pattern(pattern)]

    def pull(self, pull_expr, entity,
             _seen_entities=None, _base_pattern=None):
        """
        Pulls a nested dictionary/list datastructure out corresponding to the shape specified in pull_expression 
        as for the specfied entity.
        * entity:
          * can be eid literal, Entity instance, or attribute pattern dictionary
          * attribute pattern dictionary is interpretted as in self.match_pattern
          * will eventually have warn, fail, etc. options for multiple matches in pattern; presently take-first

        * pull-expression:
          * e.g. imagine you wanted to look up the birth place of every one of your ancestors, for as far back
            as you have info, and all the available information about these locations, including university names:

            ['person:name',
             'person:birth_date',
             {'person:parent': '...',
              'person:birth_place': ['*',
                                     {'university:_location': ['university:name']}]}]

          * `'...'` is used here to specify a recursion point, the ancestral relation
          * `'*'` is a wildcard that can be used to catch all attributes of the matched locations
          * `_` after the `:` separator of the namespaced `university:_location` attribute specifies a reverse
            lookup on the attribute `university:location` of the university entities.
        """
        if isinstance(entity, dict):
            eids = self.match_pattern(entity)
            return self.pull(pull_expr, some(eids))
        else:
            eid = entity.eid if isinstance(entity, Entity) else entity
            _entity = self._eav_index.get([eid])
            _seen_entities = _seen_entities or {eid} # seed the seen entities if needed
            dict_patterns = filter(lambda x: isinstance(x, dict), pull_expr)
            attr_patterns = filter(lambda x: not(isinstance(x, dict)), pull_expr)
            # Get the attr_patterns (non recursive patterns), separate reverse lookups, etc
            # QUESTION Do we want to return an id dictionary when we know it's a ref? who should we copy?
            normal_attributes = filter(lambda x: x not in {'*'} and not reverse_lookup(x), attr_patterns)
            reverse_lookups = filter(reverse_lookup, attr_patterns)
            pull_data = {attr: _entity.get([attr]) for attr in normal_attributes}
            # Handling reverse lookups at base attr_patterns (not in the dict_patterns)
            if reverse_lookups:
                for lookup in reverse_lookups:
                    pull_data[reverse_lookup] = self.pull([{lookup: [self.ident_attr]}], eid)[reverse_lookup]
            # Handle * attrs
            if '*' in attr_patterns:
                for a, vs in _entity.keys.items():
                    if a not in pull_data:
                        pull_data[a] = vs # cardinality schema?
            # Deal with the dict patterns, which correspond with relations/refs (implicit are fine; though
            # need to think about the details of how defaults and options work out)
            for dict_pattern in dict_patterns:
                for attr, token in dict_pattern.items():
                    reverse = reverse_lookup(attr)
                    if reverse:
                        # Then reverse lookup
                        if self._ref_attr(reverse):
                            # Can do this; have reverse mapping indexed (vae)
                            eids = self._vae_index.get([eid, reverse])
                        elif self.lazy_refs:
                            # have to search through all triples
                            eids = set(e for e, attrs in self._eav_index.keys.items()
                                         if eid in attrs.get([reverse]))
                        else:
                            print("Warning! Should have either lazy refs or or a schema for reverse lookups!")
                    else:    
                        eids = _entity[attr]
                    if token == '...':
                        # Only track recursion points in seen entities; all else statically terminates
                        _seen_entities = _seen_entities.update(_entity[attr])
                        token = _base_pattern

                    # * identity attr should key cardinality as well for reverse lookups; could have ref ident
                    results = [self.pull(token, e,
                                         # in case of recursive pulls
                                         _base_pattern=(_base_pattern or pull_expr),
                                         # Each of the pull results needs to know that the others
                                         # will have been seed, as well as what has been seen.
                                         # Note: doesn't look for relationships forked past
                                         # that... Have to think about these side cases... update
                                         # compute global state?
                                         _seen_entities=_seen_entities)
                               for e in eids]
                    pull_data[attr] = results
            for a, vs in pull_data.items():
                pull_data[a] = some(vs) if self._card_one(a) else vs
            return pull_data
            # ctn...

    def pull_many(self, pull_expr, eids_or_pattern, sort_by=None, sort_desc=True):
        # Could eventually first sort and take by some attribute without having to pull everything, if that
        # became necessary, using a first step to just pull that attribute, without the rest. Then do full
        # pull only for what's needed.
        eids = self.match_pattern(eids_or_pattern) if isinstance(eids_or_pattern, dict) else eids_or_pattern
        results = (self.pull(pull_expr, eid) for eid in eids)
        if sort_by:
            results = sorted(results, key = lambda x: x[sort_by])
        if not sort_desc:
            results = results.reversed()
        return results


# Our data constructors, as pure functions

def entity_cons(type_name, default_attr_base):
    "Return a constructor function for creating namespaced entities"
    def f(**avs):
        avs = dict(((default_attr_base + ':' + k if ':' not in k else k), v) for k, v in avs.items())
        avs[type_name.split('.')[0] + ':type'] = type_name
        return avs
    return f


def namespaced(namespace, **avs):
    "Return a constructor function for creating namespaced entities"
    avs = dict(((namespace + ':' + k if ':' not in k else k), v) for k, v in avs.items())
    return avs



