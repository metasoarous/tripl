
# Tripl

A data format for "all the things", inspired by Datomic and the Semantic Web that has

* explicit, global meaning and context
* an easy document-store like write semantic
* capable of expressing arbitrary graph data
* is extensible and polymorphic
* primarily targets JSON for reach and interoperability
* theoretical underpinnings in RDF, with a simpler data-oriented buy-in model

Tripl can be created and used from any language with a natural interpretation of JSON data.
However, getting the most out of the implied graph structure of the data requires some tooling.
(Thought not much! The first passable version of this tool was only 120 LOC!)

This repository contains a python library for working with this data programatically from python, and will evolve into a command line tool for working with this data.


## Vision

NoSQL document stores have of late gained popularity for their tremendous flexibility and ease of entry.
The problem is that once you want to access the data in a different way, you're locked in to the ad hoc schema you hacked together that one night.

The Datomic database owes some of it's success to having brought sanity to this madness.
Datomic transactions can be map forms that look more or less like the sort of JSON document you might throw into a Mongo store.
These maps are interpreted as entities, and nested maps as named relationships between entities.
Relationships between entities can also be established in these map forms using unique integer ids or other unique attribute value pairs.
Under the hood, all of this data is stored as Entity Attribute Value (EAV) triples, a model for graph data at the heart of the Semantic Web (RDF).
At the end of the day, we get the flexible write model of a document store, with the read flexibility of a relational graph data.

A key feature of RDF that inspired Datomic was that of global statement of fact.
RDF data is designed so that even the smallest bit of information - the EAV triple (fact) - is globally meaningful.
It does this by using unique URIs for object and predicate identifiers.
Datomic simplifies buy-in here through the use of namespaced keywords for attributes (and schema identities), and database specific integer ids for identity.

All of this is fine and dandy for Datomic as a database.
But what would this idea look like as a more general _format_?
RDF has formats, but they are generally complicated by the burden of URIs for global interpretability, intricacies of object metadata, etc.
We could just write "Datomic transaction like" data to files, but there are various details of its design that don't quite make sense in this setting.
How would we formalize and simplify this idea?
How would we interact with this data?


## Motivating application - Bioinformatics

The motivating use case for this library is bioinformatics.

In this field, we write scripts that compute one piece of data for one set of inputs, and then wire _those_ up in scripts for _many_ such scripts and input sets.
Taking one of these files, you generally have _no idea_ what any piece of data means outside of the _implicit_ context of the directory in which you found it.
Given a FASTA file of genetic sequence data, and a CSV with metadata about those sequences, how do I join the two?
More importantly, why do I _have_ to?
How is it (presently) 2017 and we still aren't using a data format capable of expressing the relationships between sequence data, metadata, phylogenetic information, and arbitrary domain entities?
So much time is wasted "munging" in bioinformatics simply due to lack of global, relational interpretability.

However, all these formats and build patterns are often necessary to deal with the fact that bioinformatics tools are frequently written to do one thing, in one particular way.
Every analysis has different demands, and so it's vital that you be able to stitch together different tools for different tasks, in line with the Unix Philosophy.
And if this is done well, there are some serious benefits to being in Unix and using the wealth of tools available.
So a proper solution must take this into account, and accentuate these strengths.


## Enter Tripl

Tripl's aim is to solve this problem via a minimally constrained JSON usage pattern taking the best of Datomic and its antecedent DataScript, maximizing flexibility as a simple data format.
The constraints are:

* Every entity must have a globally unique identity, represented as a string
  * Typically either a namespaced keyword, a UUID, or a URI
  * Can be asserted via `db:ident` in a dictionary/map form
  * If you assert a dictionary/map without one, a random UUID will be assigned
* Attributes should be namespaced keywords
  * `'name'` means nothing as an identifier if used variously among different dictionaries/maps in different places
  * `'person:name'` and `'company:name'` as attributes unambiguously describe what their corresponding values _mean_, independent of the context of the corresponding entity
* Values must also be serializable and hashable in JSON and any languages you use to interact with the data
* Lookup refs can be arbitrary maps which identify that entity, either at the transaction level, 

Some notable differences from Datomic et al.:

* canonical identities are globally unique strings instead of database specific integers, for minimal coordination and simpler compute distribution
* uses `:` namespace separation instead of `/` (falling in line with traditional RDF notation), and strings instead of proper keywords for idents
* default cardinality is (presently; this may be revised) `db.cardinality:many`, again to simplify coordination and defaulting to flexibility (Datomic requires a cardinality specification for each attribute, while DataScript defaults to `:db.cardinality/one`)
* doesn't require specifying references before hand (lazily infers them, in contrast with both DataScript and Datomic)

Files containing such data can be trivially merged (from the shell, `tripl -i file1.trip.json file2.trip.json -o out.trip.json`; The `.trip` prefix is for clarity but totally optional), because all data is globally meaningful.
So, as bioinformaticians, we enter this paradigm where we can conveniently spit out facts as json data scattered about our nested directory structures, and ingest that data as EAV triples, with a queryable, relational graph model.

Targeting JSON, there's no limit to where this data can go.
Any language should be able to read and use this data without a ton of difficulty.
The core Tripl library clocked in at right around 120 lines of code with basic file read/write, pull query, and entity pattern matching evaluation.
With all of the schema, indexing of VAE triples for faster reverse lookup queries and such, this looks to go a few hundred lines, but is still a fairly simple thing.
But also, if you are on a platform or circumstance where Datomic, DataScript or Mentat are available, the format being used here can very naturally target any of these databases.


## Tripl

This is the canonical python API.
It's still in draft, so details may change, but the flavor is as follows.

For starters, let's create our triple store:

```python
from tripl import tripl
ts = tripl.TripleStore()
```

Let's start by imagining we have a project named `cft`.
We have sequences, timepoints, and subjects.
We might come up with the following attributes to describe our data:

```python
['cft:type', 'cft.subject:id', 'cft.timepoint:id', 'cft.seq:id', 'cft.seq:string', 'cft.seq:description', 'cft.seq:timepoint', 'cft.seq:subject']
```

Note that each of the attributes in and of itself, is more or less self descriptive.
If something has a `cft.seq:timepoint` attribute, it's clear that it is a sequence and has timepoint data associated with it.

We can use that to describe Tripl data as follows:

```python
data = [# some subjects
        {'cft.subject:id': 'QA255', 'cft:type': 'cft.type:subject'},
        {'cft.subject:id': 'QA344', 'cft:type': 'cft.type:subject'},
        # sequence and timepoint data
        {'cft.seq:id': 'QA255-092.Vh',
         'cft:type': 'cft.type:seq',
         'cft:description': 'seed sequence for patient QA255',
         'cft.seq:string': 'AGCGGTGAGCTGA',
         'cft.seq:subject': {'cft.subject:id': 'QA255'},
         'cft.seq:timepoint': [
             {'cft.timepoint:id': 'seed-sample', 'cft:type': 'cft.type:timepoint'},
             {'cf:.timepoint:id': 'dpi1204', 'cft:type': 'cft.type:timepoint'}]},
        {'cft.seq:id': '15423-1',
         'cft:type': 'cft.type:seq',
         'cft.seq:string': 'AGCGGTGAGCTGA',
         'cft.seq:subject': {'cft.subject:id': 'QA255'},
         'cft.seq:timepoint': [
             {'cft.timepoint:id': 'dpi234', 'cft:type': 'cft.type:timepoint'},
             {'cft.timepoint:id': 'dpi1204', 'cft:type': 'cft.type:timepoint'}]},
        {'cft.seq:id': '1534-2',
         'cft:type': 'cft.type:seq',
         'cft.seq:string': 'AGCGGTGAGCTGA',
         'cft.seq:subject': {'cft.subject:id': 'QA344'},
         'cft.seq:timepoint': [
             {'cft.timepoint:id': 'L1', 'cft:type': 'cft.type:timepoint'}]}]
```

There's only one catch here.
Each map here is going to get a new entity, while it's likely clear that the intent of this data structure is to have each instance `{'cft.subject:id': _}` to correspond to a single entity, the data has not explicitly told us this.

There are three things we can do to achieve this:

1. Simply create a unique ident for these entities (say, via `import uuid; uuid.uuid1()`)

```python
import uuid

subject_255 = uuid.uuid1()

data = [{'db:ident': subject_255, 'cft.subject:id': 'QA255', 'cft:type': 'cft.type:subject'},
        #...
        {'cft.seq:id': 'QA255-092.Vh',
         'cft:type': 'cft.type:seq',
         'cft:description': 'seed sequence for patient QA255',
         'cft.seq:string': 'AGCGGTGAGCTGA',
         # We can refer to that ident directly, in a `{'db:ident': subject_255}` dict
         'cft.seq:subject': subject_255,
         'cft.seq:timepoint': [
             {'cft.timepoint:id': 'seed-sample', 'cft:type': 'cft.type:timepoint'},
             {'cf:.timepoint:id': 'dpi1204', 'cft:type': 'cft.type:timepoint'}]},
        #...
        ]
```

2. When we assert this data, we can specify that the `cft.timepoint:id` attribute should be considered unique within the context of that assertion, using the `id_attrs` option.

```python
data = [
        # as before...
        ]

# Using id_attrs
ts.assert_facts(data, id_attrs=['cft.timepoint:id', 'cft.seq:id', 'cft.subject:id'])
```

3. Identity attributes

For attributes we wish to be unique, we should also be able to specify schema asserting this, which effectively fixes this `id_attrs` setting for us (and, as we'll see, as part of the data itself).
However, this should be employed with care.
As soon as you have a uniqueness constraint like this, it becomes difficult to (e.g.) compare datasets which might contain overlapping values.
For this reason I suggest sticking with the two methods above.
_Usually_, if you are asserting information about something that has already been created, you'll have it in a dictionary, and can just call `that_dict['db:ident']` to get the identity for a new set of assertions without too much difficulty.
(2) Helps us deal with the process of creating and asserting a particular set of facts from within our language.
There's even been some research on contextual ontological constraints, which would effectively allow you to say "within a particular data set, such and such ids are unique".
However, doing this raises a lot of questions, and I think the W3C jury is still out on the recommendation here.


### Schema

In any case, schema is still a good idea!
For one thing, we may wish to specify that the default cardinality should be `db.cardinality:one` (which is, TBQH, better from a data modelling perspective).

```python
schema = [
    {'db:ident': 'cft.seq:timepoint', 'db.uniqueness'
```

So we have the ability to 
It's worth pointing out here that we're implicitly treating each of these `cft.timepoint:id` values as unique identifiers in the context of this data.


```python
# First let's construct some helpers for creating and working with this data

def cft_cons(name):
    return tripl.entity_cons('cft.type:' + name, 'cft.' + name)

subject = cft_cons('subject')
seq = cft_cons('seq')
timepoint = cft_cons('timepoint')
tree_node = tripl.entity_cons('cft.type:tree_node', 'cft.tree.node')


# Next our schema

schema = {
   'cft.seq:timepoint': {'db:valueType': 'db.type:ref',
                         'db:cardinality': 'db.cardinality:many'},
   'cft.seq:subject': {'db:valueType': 'db.type:ref'}}


## Let's imagine the following data having been transacted in here

ts = tripl.TripleStore(schema=schema, default_cardinality='db.cardinality:one')


# Now we can see our constructors in action :-)

ts.assert_facts([
    subject(id='QA255'),
    subject(id='QA344'),
    seq(id='QA255-092.Vh',
        seq='AGCGGTGAGCTGA',
        timepoint=[timepoint(id='seed-sample'), timepoint(id='dpi1204')],
        **{'cft:description': 'seed sequence for patient QA255'}),
    seq(id='15423-1',
        seq='AGCGGTGAGCTGA',
        timepoint=[timepoint(id='dpi234'), timepoint(id='dpi1204')]),
    seq(id='1534-2',
        seq='AGCGGTGAGCTGA',
        timepoint=[timepoint(id='L1')])],
    id_attrs=['cft.timepoint:id', 'cft.seq:id', 'cft.subject:id'])


# We can query data using a pull query specifying what attributes and references you'd like to extract
pull_expr = ['db:ident', 'cft.seq:id', {'cft.seq:timepoint': ['cft.timepoint:id']}]
pull_data = ts.pull_many(pull_expr, {'cft:type': 'cft.type:seq'})
import pprint
pprint.pprint(list(pull_data))


# Prints out the following:
#
#    [{'cft.seq:id': '1534-2',
#      'cft.seq:timepoints': [{'cft.timepoint:id': 'L1'}]},
#     {'cft.seq:id': '15423-1',
#      'cft.seq:timepoints': [{'cft.timepoint:id': 'dpi1204'},
#                             {'cft.timepoint:id': 'dpi234'}]},
#     {'cft.seq:id': 'QA255-092.Vh',
#      'cft.seq:timepoints': [{'cft.timepoint:id': 'dpi1204'},
#                             {'cft.timepoint:id': 'seed-sample'}]}]


# Save out to file
ts.dump('test.json')

# Reload; note that schema is persisted
ts2 = TripleStore.load('test.json')

# Reproducibility :-)
pprint.pprint(list(ts2.pull_many(pull_expr, {'cft:type': 'cft.type:seq'})))

# We can also do reverse reference lookups, by using `_` after the namespace separator
pull_expr = ['cft.timepoint:id', {'cft.seq:_timepoint': ['*']}]
pprint.pprint(
    list(ts2.pull_many(pull_expr, {'cft:type': 'cft.type:timepoint'})))


# We also have an entity API
e = ts.entity({'cft.timepoint:id': 'seed-sample'})

# These behave as dict like views over the EAV index, that update as the store updates.

print e['cft.timepoint:id']
pprint.pprint(e['cft.seq:_timepoint'])

```

That's all for now!
Stay Tuned!



