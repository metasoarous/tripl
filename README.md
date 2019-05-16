
# Tripl

A data format for "all the things", inspired by Datomic and the Semantic Web that

* has an easy document-store like write semantic
* can express arbitrary graph data
* enables explicit, global meaning and context
* is extensible and polymorphic
* primarily targets JSON for reach and interoperability
* rests upon the theoretical underpinnings in RDF, with a simpler data-oriented buy-in model

Tripl can be created and used from any language with a natural interpretation of JSON data.
However, getting the most out of the implied graph structure of the data requires some tooling.
(Thought not much! The first passable version of this tool was only 120 LOC!)

This repository contains a python library for working with this data programatically from python, as well as a command line tool for working with data from the shell.


## Conceptual model

At the heart of the Semantic Web is a data language called the Resource Description Framework, or RDF.
Parts of RDF can be a bit complicated, but there are some core ideas as relate to data modelling which are very valuable for data scientists and other programmers.

RDF is based on the Entity Attribute Value (EAV) data modelling pattern, in which _facts_ about _entities_ are stored as a set of `(entity, attribute, value)` triples.
It's possible in this framework to have attributes that point from one entity to another (e.g. `(entity1, attribute, entity2)`).
This gives EAV and thus RDF the ability to very flexibly model arbitrary graph relationships between data.

It's worth contrasting this approach to data modelling with that of other SQL and NoSQL databases.
In SQL databases, entities are stored as rows in tables.
We end up being locked into the structure of these tables and their relationships.
Meanwhile NoSQL databases allow us great flexibility in how we organize collections of documents, but we end up being locked into the de facto schema we create in the process.

With EAV, any entity can have any attribute assigned to it, and attributes between entities (_reference_ attributes) can point to any entity they like.
This means that EAV and RDF are inherently and effortlessly polymorphic.
But because everything is being represented under the hood as a collection of simple triples/facts, we end up being less locked into the ways we initially organize our relationships between entities.


## The tooling

There is a catch though.
To get anything meaningful out of a raw set of EAV triples, we really need some tooling: a query language and a convenient write semantic.
Additionally, this data tends to be most useful when we know some things about the attributes of our data before hand, so we would like a way for this tooling to interpret some _schema_ for the attributes (ultimately much easier that specifying a SQL schema).

This python library provides both a simple query language and write semantic.
The data though can more or less be used from wherever.


## Usage

Keep in mind that this is still in draft, so details may change, but the flavor is as follows.

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
        # ...
        {'cft.seq:id': 'QA255-092.Vh',
         'cft:type': 'cft.type:seq',
         'cft:description': 'seed sequence for patient QA255',
         'cft.seq:string': 'AGCGGTGAGCTGA',
         # We can refer to that ident directly, in a `{'db:ident': subject_255}` dict
         'cft.seq:subject': subject_255,
         'cft.seq:timepoint': [
             {'cft.timepoint:id': 'seed-sample', 'cft:type': 'cft.type:timepoint'},
             {'cf:.timepoint:id': 'dpi1204', 'cft:type': 'cft.type:timepoint'}]},
        # ...
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
    {'db:ident': 'cft.seq:timepoint', 'db:cardinality': 'db.cardinality:one'}]
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


# Let's imagine the following data having been transacted in here

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

print(e['cft.timepoint:id'])
pprint.pprint(e['cft.seq:_timepoint'])

```

That's all for now!
Stay Tuned!



