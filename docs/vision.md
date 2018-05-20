

# Vision

NoSQL document stores have of late gained popularity for their tremendous flexibility and ease of entry.
The problem is that once you want to access the data in a different way, you're locked in to the ad hoc schema you hacked together that one night.

The Datomic database owes some of it's success to having brought sanity to this madness.
Datomic transactions can be map forms that look more or less like the sort of JSON document you might throw into a Mongo store.
These maps are interpreted as entities, and nested maps as named relationships between entities.
Relationships between entities can also be established in these map forms using other unique attribute value pairs.
Under the hood, all of this data is stored as Entity Attribute Value (EAV) triples, a model for graph data at the heart of the Semantic Web (RDF, which tasked itself with the challenge of being **the** data language for the full complexity of the web).
At the end of the day, we get the flexible write model of a document store, with the read flexibility of a relational graph database.

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
So much time is wasted "munging" in bioinformatics due to lack of global, relational interpretability.

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
* uses `:` namespace separation instead of `/` (falling in line with traditional RDF notation), and strings instead of proper keywords for idents (we may change this default in the future, but not once out of alpha)
* default cardinality is (presently; again this may be revised) `db.cardinality:many`, to simplify coordination and defaulting to flexibility (Datomic requires a cardinality specification for each attribute, while DataScript defaults to `:db.cardinality/one`)
* doesn't require specifying references before hand (lazily infers them, in contrast with both DataScript and Datomic)



Files containing such data can be trivially merged (from the shell, `tripl -i file1.tripl.json file2.trip.json -o out.tripl.json`; The `.tripl` prefix is for clarity but totally optional), because all data is globally meaningful.
So, as data scientists and bioinformaticians, we enter this paradigm where we can conveniently spit out facts as json data scattered about our nested directory structures, and ingest that data as EAV triples, with a queryable, relational graph model.

Targeting JSON, there's no limit to where this data can go.
Any useful language should be able to read and use this data without a ton of difficulty.
The core Tripl library clocked in at right around 120 lines of code with basic file read/write, pull query, and entity pattern matching evaluation.
With all of the schema, indexing of VAE triples for faster reverse lookup queries and such, this looks to go a few hundred lines, but is still a fairly simple/small thing.
But also, if you are on a platform or circumstance where Datomic, DataScript or Mentat are available, the format being used here can very naturally target any of these databases.
There's now also an effort to bring this storage and query pattern to the JVM and JS via the [Datahike](https://github.com/replicativ/datahike) project.


