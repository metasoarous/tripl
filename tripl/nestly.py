
import os
import json
import copy
#import pprint as pp

import SCons.Node

def _create_metadata_file(source, target, env):
    target = str(target[0])
    #pp.pprint(env['metadata_dict'])
    with open(target, 'w') as fp:
        json.dump([env['metadata_dict']], fp, indent=4, default=list) #, cls=env['encoder_cls'])

def _has_namespace(name):
    return len(name.split(':')) > 1

class NestWrap(object):
    def __init__(self, scons_wrap, name='base', base_namespace=None, metadata=None, namespace=None, id_attrs=None,
            **kw_args):
        self.base_namespace = base_namespace
        self.metadata = metadata
        self.id_attrs = id_attrs
        self.scons_wrap = scons_wrap

        #self.tripl_store = tripl.TripleStroe
        namespace = namespace or name
        namespace = (self.base_namespace + "." if self.base_namespace else "") + namespace
        self.current_nest = name
        self.nest_levels = {name: {
            'name': name,
            'namespace': namespace,
            'metadata': metadata,
            'id_attrs': id_attrs or [],
            'parent_nest': None,
            'targets': set()
            }}
        self.targets = {}

    # These are more or less done, and just wrap other things below
    # =============================================================

    def add_nest(self, name=None, **kw):
        """A simple decorator which wraps :meth:`nestly.core.Nest.add`."""
        def deco(func):
            self.add(name or func.__name__, func, **kw)
            return func
        return deco

    def add_metadata(self, name=None, metadata=None):
        """Add metadata as a json file of facts, to be asserted later, after build (therefore, not accessible
        during build setup)."""
        # QUESTION: How to do this? # We'll defer for now and say done, but need to think through details here
        return self.add_target(name=name, metadata=lambda c, x: {'tripl:type': 'tripl.nestly:deferred_metadata'})


    # This is the real meat of things as an interface:
    # ================================================

    def add(self, name, nestable, namespace=None, metadata=None, id_attrs=None, **kw_args):
        """Calls out to the scons_wrap add method, and contextually asserts the given id_attrs. Effectively
        defines a context in which all traversed data gets referenced, and upon which identity is asserted."""
        namespace = namespace or name
        namespace = (self.base_namespace + "." if self.base_namespace else "") + namespace
        # Do something with id_attrs and meta...
        self.nest_levels[name] = {
                'name': name,
                'namespace': namespace,
                'metadata': metadata,
                'label_func': kw_args.get('label_func'),
                # We want to know all parent id_attrs as well when merging down
                'id_attrs': (id_attrs or []) + self.nest_levels[self.current_nest]['id_attrs'],
                'parent_nest': self.current_nest,
                'targets': set()}
        self.current_nest = name
        return self.scons_wrap.add(name, nestable, **kw_args)

    # add namespace arg here?
    def add_target(self, name=None, metadata=None, omit_metadata=False):
        def deco(f):
            real_name = f.__name__ or name
            real_name = name or f.__name__
            self.targets[real_name] = {
                    'name': real_name,
                    #'namespaced_name': self.nest_levels[self.current_nest]['namespace'] + ':' + name,
                    'doc': f.__doc__,
                    'metadata': metadata,
                    'nest': self.current_nest,
                    'omit_metadata': omit_metadata or real_name[0:1] == '_'}
            self.nest_levels[self.current_nest]['targets'].add(real_name)
            f_ = self.scons_wrap.add_target(real_name)(f)
            return f_
        return deco

    def pop(self, name=None, env=None, file_name='metadata.json'):
        self.dump_metadata(env, file_name=file_name)
        self.scons_wrap.pop(name)
        self.current_nest = self.nest_levels[name or self.current_nest]['parent_nest']

    # Some implementation details...

    def _namespace(self, name):
        if _has_namespace(name):
            return name.split(':')[0]
        # This should proably be more nuanced so as to not add the base_namespace if namespace was explicitly
        # specified (possibly even as name)
        if name in self.targets:
            return self.nest_levels[self.targets[name]['nest']]['namespace']
        else:
            # We use current nest, because we name to the 
            return self.nest_levels[self.current_nest]['namespace']


    def _namespaced(self, thing, base_nest_level=None):
        if isinstance(thing, dict):
            return {self._namespaced(a, base_nest_level=base_nest_level):
                    (self._namespaced(v, base_nest_level=base_nest_level) if isinstance(v, dict) else v)
                    for a, v in thing.items()}
        elif isinstance(thing, str):
            if _has_namespace(thing):
                return thing
            namespace = self.base_namespace + '.' + base_nest_level if base_nest_level else self._namespace(thing)
            return namespace + ':' + thing


    def _translate_target(self, c, a, v):
        target = self.targets[a]
        metadata = target['metadata'](c, v) if callable(target['metadata']) else (target['metadata'] or {})
        if isinstance(v, dict):
            v = copy.deepcopy(v)
        elif isinstance(v, list) or isinstance(v, SCons.Node.NodeList):
            return [self._translate_target(c, a, v_) for v_ in v]
        elif isinstance(v, SCons.Node.FS.Entry) or isinstance(v, SCons.Node.FS.File):
            # Can add more metadata here as needed
            v = {'tripl.file:path': str(v),
                 # This will be super cool...
                 'tripl.file:sources': [{'tripl.file:path': str(p)} for p in v.sources]}
            if target['doc']:
                v['tripl:doc'] = target['doc']
        if isinstance(v, dict):
            v.update(metadata)
        elif metadata:
            v = metadata['tripl.nestly.target:value'] = v
        # TODO namespace all keywords
        return v


    def _translated_metadata_dict(self, c, base_nest_level=None):
        base_nest_level = base_nest_level or self.current_nest
        nest_level = self.nest_levels[base_nest_level]
        nest_id = nest_level['namespace'] + ':id'

        # Presumably the root if nothing else...
        nest_val = c.get(base_nest_level, {})
        nest_metadata = nest_level['metadata']
        metadata = nest_metadata(c, nest_val) if callable(nest_metadata) else (nest_metadata or {})

        if isinstance(metadata, dict) and isinstance(nest_val, dict):
            d = copy.deepcopy(nest_val)
            d.update(self._namespaced(metadata, base_nest_level=base_nest_level))
        else:
            d = {}

        v_id = d.get(nest_id) \
                or (nest_level['label_func'](d or nest_val) if nest_level.get('label_func') else nest_val)
        d = self._namespaced(metadata, base_nest_level=base_nest_level)
        d[nest_id] = v_id
        if isinstance(nest_val, dict):
            d.update({self._namespaced(a, base_nest_level): v for a, v in nest_val.items()})

        #for a, v in c.items():
        for a in nest_level['targets']:
            # Don't want to transact "hidden" targets
            if a[0:1] != '_':
                v = c[a]
                # handle as a target val
                v = self._translate_target(c, a, v)
                d[self._namespaced(a, base_nest_level=base_nest_level)] = v

        parent_nest_level = nest_level['parent_nest']
        if parent_nest_level:
            d[self._namespaced(parent_nest_level)] = self._translated_metadata_dict(c, base_nest_level=parent_nest_level)
        # Should also be serializing a secondary representation of the 
        return d

    # All to accomodate this; the export of the control dictionary as a tripl json file
    # TODO Need to add ingest steps for things flagged ingest=True

    def dump_metadata(self, env=None, target_name='_metadata', file_name='metadata.json'):
        env = env or self.scons_wrap.alias_environment
        @self.add_target(name=target_name)
        # Using `_` by default because 
        def _metadata(outdir, c):
            main_tgt = env.Command(os.path.join(outdir, file_name),
                               [],
                               action=_create_metadata_file,
                               metadata_dict=self._translated_metadata_dict(c))
                               #encoder_cls=encoder_cls)
            env.AlwaysBuild(main_tgt)
            return main_tgt
            # TODO Add another step that ingests data marked for ingest

    # Eventually; need to reconcile with nesting as implicit aggregation for some cases
    #def add_aggregate(self, name, data_fac):
        #return self.scons_wrap.add_aggregate(name, data_fac)
    # For backwards compatibilty; eventually
    #def add_controls(self, name, data_fac):
        #return self.scons_wrap.add_controls(name, data_fac)


