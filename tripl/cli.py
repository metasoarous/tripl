#!/usr/bin/env python

import argparse
import tripl
import json
import functools as fun
import subprocess
import multiprocessing as mp


def run_ingest_command(command, input_path):
    command = command.split()
    command.append(input_path)
    return subprocess.check_output(command)


def ingest(args):
    # Have to figure out how to handle the id attrs
    if args.map_command:
        pool = mp.Pool(processes=args.processes)
        run_ingest = fun.partial(run_ingest_command, args.command)
        fact_sets = pool.map(run_ingest, args.inputs)
        # And also finish setting up the inputs mappings
        # Should really be doing this in a pool of workers or something
        t = tripl.TripleStore()
        for facts in fact_sets:
            t.assert_facts(facts, id_attrs=args.id_attrs)
    else:
        inputs = args.inputs
        t = tripl.TripleStore.loads(inputs, id_attrs=args.id_attrs)
    return t


def cs_arg(argval):
    return argval.split(',')


def json_arg(argval):
    try:
        return json.JSONDecoder().decode(argval)
    except Exception as e:
        print("Unable to parse argument value")
        raise e


# planned subcommand structure:
# tripl
#   join
#   pull
#   plot
#   diff ?


def add_base_arguments(parser):
    parser.add_argument('-s', '--schema', help="schema, in schema format as in tripl python api")
    parser.add_argument('-i', '--inputs', default=['/dev/stdin'], nargs="+",
                        help="input files; if there's schema, it should come first; defaults to stdin")
    # Should have extension matching, and when you use stdout should pprint; also add `-` for stdin/stdout
    # shortcuts
    parser.add_argument('-o', '--output', help='output file', default='/dev/stdout')
    parser.add_argument('-m', '--map-command',
                        help="""map each input through this command, al a `map-command input`; command should write as
                        json to stdout a list of fact dictionaries, or a single, nested EAV index dictionary, as json,
                        to stdout.""")
    parser.add_argument('-I', '--id-attrs', type=cs_arg,
                        help="comma separated list of attrs to treat as unique in transactions")
    parser.add_argument('-n', '--default-namespace',
                        help="""MOCK! JSON files loaded with unnamespaced keywords will be given this namespace""")
    parser.add_argument('-P', '--processes', type=int, default=12, help="ingest parallelism")


def get_args():
    parser = argparse.ArgumentParser(prog='tripl', description='The tripl data Swizz Army Knife utility')
    # Basic arguments
    subparsers = parser.add_subparsers(dest='subcommand')

    # Subparsers
    # For join / ingest
    join_parser = subparsers.add_parser('join',
                                        help="""Join data from some number of files or directories, subject to
                                        --map-command output interpretation as tripl data where applied, and spit out
                                         to -o tripl.json file as an eav index mapping.""")
    add_base_arguments(join_parser)  # lint

    # Now for pull
    pull_parser = subparsers.add_parser('pull',
                                        help="""Pull document/json structure out of ingested tripl data, given pull
                                        expression, and save to -o.""")
    add_base_arguments(pull_parser)  # lint
    pull_parser.add_argument('-p', '--pull-expr', type=json_arg, default='["*"]', help='the pull expression to pull')
    entities_arg = pull_parser.add_mutually_exclusive_group()
    entities_arg.add_argument('-e', '--entity-pattern', type=json_arg, help="entity pattern for which to pull")
    entities_arg.add_argument('-E', '--entities', type=cs_arg, help="comma separated list of entity ids")
    pull_parser.add_argument('-N', '--drop-namespaces',
                             help='MOCK! output results with namespaces removed from keywords')

    # And done
    return parser.parse_args()


def _main(args):
    t = ingest(args)
    if args.subcommand == 'join':
        t.dump(args.output)
    elif args.subcommand == 'pull':
        with open(args.output, 'w') as fh:
            json.dump(t.pull_many(args.pull_expr, args.entities or args.entity_pattern), fh, default=list,
                      indent=4)
    elif args.subcommand == 'plot':
        print('Plot is not yet supported')


def main():
    args = get_args()
    return _main(args)


if __name__ == '__main__':
    main()
