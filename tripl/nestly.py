
import os
import json
import copy
import uuid
import tripl
import pprint as pp
pp #lint

import SCons.Node

from Bio import SeqIO
from Bio import Phylo

import bio

#import tripl


def json_encoder_default(path_depth=0):
    def _json_encoder_default(obj):
        if isinstance(obj, (SCons.Node.FS.Entry, SCons.Node.FS.File, uuid.UUID)):
            return os.path.join(str(obj).split('/')[path_depth:])
        elif isinstance(obj, (SCons.Node.NodeList, set)):
            return list(obj)
        else:
            # warn?
            return str(obj)
    return _json_encoder_default


def failable_json_file(source):
    filename = str(source)
    try:
        return json.load(file(filename))
    except Exception as e:
        return {'tripl.nestly:error': str(e),
                'tripl.nestly:file': filename}

def _create_metadata_file(source, target, env):
    target = str(target[0])
    #pp.pprint(env['metadata_dict'])
    json_sources = [failable_json_file(f) for f in source if str(f).split('.')[-1] == 'json']
    doc = env['metadata_dict']
    for json_source in json_sources:
        doc.update(json_source)
    # TODO; handle other ingested files, maybe just reading in file contents for now, eventually fully tupling
    # them
    with open(target, 'w') as fp:
        json.dump([doc], fp, indent=4, default=json_encoder_default()) #, cls=env['encoder_cls'])


def ingest_seqs(filename):
    seqs = SeqIO.parse(filename, 'fasta')
    return {'bio.seq:set': [{'bio.seq:id': seq.id, 'bio.seq:seq': str(seq.seq)} for seq in seqs]}


def ingest_newick(filename):
    trees = list(Phylo.parse(filename, 'newick'))
    def ingest_clade(clade):
        d = clade.__dict__
        children = d.pop('clades')
        return tripl.namespaced('bio.phylo.clade',
                clades=map(ingest_clade, children),
                **{k: v for k, v in d.items() if v})
    def ingest_tree(tree):
        return {'bio.phylo.tree:root': ingest_clade(tree.root)}
    if len(trees) > 1:
        return {'bio.phylo.tree:set': map(ingest_tree, trees)}
    else:
        return ingest_tree(trees[0])


def _ingest_metadata_files(source, target, env):
    target = str(target[0])
    # First we take care of the 
    ingest_docs = (json.load(file(str(src))) for src in source if str(src).split('.')[-1] == 'json')
    ingest_docs = [(doc[0] if isinstance(doc, list) else doc) for doc in ingest_docs]
    doc = env['metadata_dict']
    if isinstance(doc, list):
        doc = doc[0]
    for ingest_doc in ingest_docs:
        doc.update(ingest_doc)
    doc['tripl.nestly:aggregate'] = doc.get('tripl.nestly:aggregate', [])
    for other_file in (str(src) for src in source if str(src).split('.')[-1] != 'json'):
        v = {'db:ident': env['file_idents'][other_file],
             'tripl.file:contents': file(other_file).read()}
        fmt = other_file.split('.')[-1]
        if fmt in {'fasta', 'fa'}:
            v.update(ingest_seqs(other_file))
        if fmt in {'csv'}:
            # ugg... to get the right attr_map from attr_maps, we need to be able to map the filepaths to tgt
            # names
            name_mappings = env.get('name_mappings', {})
            attr_map = env.get('attr_maps', {}).get(name_mappings.get(other_file), {})
            v.update({'tripl.csv:data': list(bio.load_csv(other_file, attr_map))})
        #if fmt in {'newick', 'nw', 'nwk'}:
            #v.update(ingest_newick(other_file))
        doc['tripl.nestly:aggregate'].append(v)
    with open(target, 'w') as fp:
        json.dump([doc], fp, indent=4, default=json_encoder_default())

def _ingest_aggregates(source, target, env):
    target = str(target[0])
    ingest_docs = (json.load(file(str(src))) for src in source)
    ingest_docs = [(doc[0] if isinstance(doc, list) else doc) for doc in ingest_docs]
    doc = env['metadata_dict']
    if isinstance(doc, list):
        doc = doc[0]
    doc['tripl.nestly:aggregate'] = doc.get('tripl.nestly:aggregate', [])
    doc['tripl.nestly:aggregate'] += ingest_docs
    with open(target, 'w') as fp:
        json.dump([doc], fp, indent=4, default=json_encoder_default())


def _has_namespace(name):
    return len(name.split(':')) > 1

def default_label(x):
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return str(x.get('id'))
    if isinstance(x, int) or isinstance(x, float):
        return str(x)
    else:
        raise(Exception("Not able to label {} object {}".format(type(x), x)))

class NestWrap(object):
    def __init__(self, scons_wrap, name='base', base_namespace=None, metadata=None, namespace=None, id_attrs=None, always_build_metadata=True,
            **kw_args):
        self.base_namespace = base_namespace
        self.always_build_metadata = always_build_metadata
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
            'ident_attr': namespace + '.db:ident',
            'aggregate_attrs': [],
            'child_nests': [],
            'targets': set()
            }}
        self.targets = {}

        self.file_idents = {}

        #@self.add_target()
        #def _base_aggregate(outdir, c):
            #return []

        @self.add_target(name=namespace + '.db:ident')
        def _ident_fn(outdir, c):
            val_uuid = uuid.uuid1()
            return val_uuid

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

    def add(self, name, nestable, namespace=None, metadata=None, full_dump=False, id_attrs=None,
            label_func=default_label, **kw_args):
        """Calls out to the scons_wrap add method, and contextually asserts the given id_attrs. Effectively
        defines a context in which all traversed data gets referenced, and upon which identity is asserted."""
        self.base_name = name
        namespace = namespace or name
        namespace = (self.base_namespace + "." if self.base_namespace else "") + namespace
        # Do something with id_attrs and meta...
        parent_level = self.nest_levels[self.current_nest]
        aggregate_attr = '_' + namespace + ':aggregate'

        nest_level = {
            'name': name,
            'namespace': namespace,
            'metadata': metadata,
            'label_func': label_func,
            # We want to know all parent id_attrs as well when merging down
            'id_attrs': (id_attrs or []) + self.nest_levels[self.current_nest]['id_attrs'],
            'ident_attr': namespace + '.db:ident',
            'aggregate_attr': aggregate_attr,
            'aggregate_attrs': parent_level['aggregate_attrs'] + [aggregate_attr] if full_dump else parent_level['aggregate_attrs'],
            'parent_nest': self.current_nest,
            'child_nests': [],
            'full_dump': full_dump,
            'targets': set()}
        self.nest_levels[name] = nest_level

        self.nest_levels[self.current_nest]['child_nests'].append(name)
        self.current_nest = name

        return_val = self.scons_wrap.add(name, nestable, label_func=label_func, **kw_args)
        @self.add_target(name=nest_level['ident_attr'])
        def _ident_fn(outdir, c):
            parent_ident = c.get(parent_level.get('ident_attr'))
            if not parent_ident:
                parent_ident = uuid.uuid3(uuid.NAMESPACE_URL, parent_level['namespace'])
            attr_uuid = uuid.uuid3(parent_ident, name)
            val_uuid = uuid.uuid3(attr_uuid, nest_level['label_func'](c[name]))
            return val_uuid

        if full_dump:
            @self.add_target(name=aggregate_attr)
            def _aggregate_fn(outdir, c):
                return []

            # Each level should be able to have it's own dump eventually, but for now, it's assumed there will
            # only be one, and this will be the relative directory used for all paths written out at this level
            @self.add_target(name='_output_wrt')
            def outdir_fn(outdir, c):
                return outdir


        return return_val

    # add namespace arg here?
    def add_target(self, name=None, metadata=None, omit_metadata=False, ingest=False, attr_map=None):
        def deco(f):
            real_name = f.__name__ or name
            real_name = name or f.__name__
            self.targets[real_name] = {
                    'name': real_name,
                    'doc': f.__doc__,
                    'metadata': metadata,
                    'nest': self.current_nest,
                    'attr_map': attr_map,
                    'ingest': ingest,
                    'omit_metadata': omit_metadata or real_name[0:1] == '_'}
            self.nest_levels[self.current_nest]['targets'].add(real_name)
            f_ = self.scons_wrap.add_target(real_name)(f)
            return f_
        return deco

    def _pop(self, env=None, file_name='metadata.json', full_dump=False):
        self.dump_metadata(env, file_name=file_name, full_dump=full_dump)
        self.scons_wrap.pop()
        self.current_nest = self.nest_levels[self.current_nest]['parent_nest']


    def pop(self, name=None, env=None, file_name='metadata.json', full_dump=False):
            while name and name != self.current_nest:
                self._pop(env=env, file_name=file_name)
            self._pop(env=env, file_name=file_name, full_dump=full_dump)

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
        # Set some things up
        target = self.targets[a]
        def relative_path(p):
            p = str(p)
            if p[0:1] != '/':
                return os.path.relpath(p, c['_output_wrt'])
            else:
                return p
        # recurse for list like things
        if isinstance(v, list) or isinstance(v, SCons.Node.NodeList):
            return [self._translate_target(c, a, v_) for v_ in v]
        elif isinstance(v, dict):
            v = copy.deepcopy(v)
        elif isinstance(v, SCons.Node.FS.Entry) or isinstance(v, SCons.Node.FS.File):
            # Can add more metadata here as needed
            ident = uuid.uuid3(c[self.nest_levels[self.current_nest]['ident_attr']], str(v))
            self.file_idents[str(v)] = ident
            v = {'db:ident': ident,
                 'tripl.file:path': relative_path(v),
                 # This will be super cool...
                 'tripl.file:sources': [{'tripl.file:path': relative_path(p)} for p in v.sources]}
        # This is where the metadata function gets called if it is callable
        metadata = target['metadata'](c, v) if callable(target['metadata']) else (target['metadata'] or {})
        if isinstance(v, dict):
            # Here we merge in the metadata
            v.update(metadata)
        elif metadata:
            metadata['tripl.nestly.target:value'] = v
            v = metadata
        # TODO namespace all keywords
        return v


    def _translated_metadata_dict(self, c, base_nest_level=None, full_dump=False):
        #orig_base_nest_level = base_nest_level
        base_nest_level = base_nest_level or self.current_nest
        nest_level = self.nest_levels[base_nest_level]
        nest_id = nest_level['namespace'] + ':id'

        # Presumably the root if nothing else...
        nest_val = c.get(base_nest_level, {})
        nest_metadata = nest_level['metadata']
        # Here's the other place where we call the metadata function if applicable
        metadata = nest_metadata(c, nest_val) if callable(nest_metadata) else (nest_metadata or {})


        # This is kind of stupid and should be changed... we end up recreating the metadata twice, once so that we
        # can call the label func, and then the next so that we can actually construct what we end up returning.
        # Not sure why, but if we don't do it this way, we end up getting a stackoverlow recursion. Still haven't
        # sorted out why, but for now.
        d = copy.deepcopy(nest_val) if isinstance(nest_val, dict) else {}
        if isinstance(metadata, dict):
            d.update(self._namespaced(metadata, base_nest_level=base_nest_level))
        v_id = d.get(nest_id) \
                or (nest_level['label_func'](d or nest_val) if nest_level.get('label_func') else nest_val)

        # This is where we construct the actual dictionary we're returning.
        d = {}
        d[nest_id] = v_id
        if isinstance(nest_val, dict):
            d.update({self._namespaced(a, base_nest_level): v for a, v in nest_val.items()})
        d.update(self._namespaced(metadata, base_nest_level=base_nest_level))

        #for a, v in c.items():
        # there may be a bug here:
        for a in nest_level['targets']:
            # Don't want to transact "hidden" targets
            if a[0:1] != '_':
                v = c[a]
                # handle as a target val
                v = self._translate_target(c, a, v)
                d[self._namespaced(a, base_nest_level=base_nest_level)] = v

        d['db:ident'] = c[nest_level['ident_attr']]
        d['tripl:type'] = nest_level['namespace']

        def add_parent_attrs(parent_nest_level):
            if parent_nest_level:
                parent_nest = self.nest_levels[parent_nest_level]
                parent_ident_name = parent_nest['ident_attr']
                if nest_level['full_dump']:
                    d[self._namespaced(parent_nest_level)] = self._translated_metadata_dict(c, base_nest_level=parent_nest_level)
                else:
                    d[self._namespaced(parent_nest_level)] = {'db:ident': c[parent_ident_name]}
                if parent_nest['parent_nest']:
                    add_parent_attrs(parent_nest['parent_nest'])

        add_parent_attrs(nest_level['parent_nest'])
        # Should also be serializing a secondary representation of the 
        return d


    # All to accomodate this; the export of the control dictionary as a tripl json file

    def dump_metadata(self, env=None, target_name='_metadata', file_name='metadata.json', full_dump=True):
        env = env or self.scons_wrap.alias_environment
        current_nest = self.nest_levels[self.current_nest]
        parent_nest = self.nest_levels[current_nest['parent_nest']]
        # Using `_` by default because 
        @self.add_target(name=target_name)
        def _metadata(outdir, c):
            translated_metadata = self._translated_metadata_dict(c, full_dump=full_dump)
            #for attr in parent_nest['aggregate_attrs']:
                #print "Finding attr in parent nest from main loop", attr
                #c[attr].append(translated_metadata)
            ingest_attrs = [attr for attr in current_nest['targets'] if self.targets[attr]['ingest']]
            ingest_tgts = [c[attr] for attr in ingest_attrs]
            # First we go through and write out the preingested json (do we really need this?)
            pre_ingest_file_name = ".preingest." + file_name
            pre_ingest_tgt = env.Command(os.path.join(outdir, pre_ingest_file_name),
                               # Should actually make this depend on all the other files? as a flag?
                               ingest_tgts,
                               action=_create_metadata_file,
                               metadata_dict=translated_metadata)
            if self.always_build_metadata:
                env.AlwaysBuild(pre_ingest_tgt)
            # Then we go through and ingest metadata files or other data (fasta, newick, etc)
            pre_agg_file_name = ".preagg." + file_name if current_nest['full_dump'] else file_name
            pre_agg_tgt = env.Command(os.path.join(outdir, pre_agg_file_name),
                               # Should actually make this depend on all the other files? as a flag?
                               [pre_ingest_tgt] + ingest_tgts,
                               action=_ingest_metadata_files,
                               metadata_dict=translated_metadata,
                               file_idents=self.file_idents,
                               name_mappings={str(tripl.some(v)): c_k for c_k, v in c.items()},
                               attr_maps={k: target['attr_map'] for k, target in self.targets.items()})
            env.Depends(pre_agg_tgt, pre_ingest_tgt)
            if self.always_build_metadata:
                env.AlwaysBuild(pre_agg_tgt)
            # If we're doing a full dump then we also want to aggregate over all the other data that's been
            # built
            if current_nest['full_dump']:
                #env.Depends(main_tgt, c[current_nest['aggregate_attr']])
                main_tgt = env.Command(os.path.join(outdir, file_name),
                                   # Should actually make this depend on all the other files? as a flag?
                                   c[current_nest['aggregate_attr']],
                                   action=_ingest_aggregates,
                                   metadata_dict=translated_metadata)
                env.Depends(main_tgt, pre_agg_tgt)
                if self.always_build_metadata:
                    env.AlwaysBuild(main_tgt)
            else:
                main_tgt = pre_agg_tgt

            for attr in parent_nest['aggregate_attrs']:
                c[attr].append(main_tgt)
            # TODO Add another step that ingests data marked for ingest
            return main_tgt

    # Eventually; need to reconcile with nesting as implicit aggregation for some cases
    #def add_aggregate(self, name, data_fac):
        #return self.scons_wrap.add_aggregate(name, data_fac)
    # For backwards compatibilty; eventually
    #def add_controls(self, name, data_fac):
        #return self.scons_wrap.add_controls(name, data_fac)


