"""
byml_mapper - Find relationships between actors in byml files
    Copyright (C) 2023  Michael Manis - michaelmanis@tutanota.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import argparse
from collections import defaultdict
import fnmatch
import json
import logging
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path, PosixPath
import pickle
import sys
from textwrap import dedent

import oead


def find_actors(filepath, byml) -> set:
    actors = set()
    try:
        all_actors = byml["Actors"]
    except KeyError:
        logging.debug(f"No actor key in byml {filepath}")
        return actors
    except TypeError:
        logging.error(f"Invalid byml type (probably an array) {filepath}")
        return actors

    for actor in all_actors:
        actors.add(
            json.dumps(
                {"Hash": actor["Hash"].v, "Gyaml": actor["Gyaml"]},
                ensure_ascii=True,
                sort_keys=True,
            )
        )

    return actors


def find_ai_group_references(filepath, byml) -> set:
    references = set()

    try:
        ai_groups = byml["AiGroups"]
    except KeyError:
        logging.debug(f"No AIGroups key in byml {filepath}")
        return references
    except TypeError:
        logging.error(f"Invalid byml type (probably an array) {filepath}")
        return references

    for ai_group in ai_groups:
        try:
            all_references = ai_group["References"]
        except KeyError:
            all_references = []

        for reference in all_references:
            try:
                references.add(reference["Reference"].v)
            except KeyError:
                try:
                    references.add(reference["InstanceName"])
                except KeyError:
                    logging.warning(
                        f"Ref with no 'Reference' or 'InstanceName' key in {filepath}"
                    )

    return references


def find_generic_array_references(filepath, key, byml) -> set:
    references = set()

    try:
        groups = byml[key]
    except KeyError:
        logging.debug(f"No {key} key in byml {filepath}")
        return references
    except TypeError:
        logging.error(f"Invalid byml type (probably an array) {filepath}")
        return references

    for group in groups:
        for id_ in group:
            references.add(id_.v)

    return references


def process_match(filepath) -> tuple[set, set]:
    discovered_references = set()

    with open(filepath, "rb") as matched_file:
        try:
            byml = oead.byml.from_binary(matched_file.read())
        except oead.InvalidDataError:
            logging.error(f"Unable to parse byml in {filepath}")
            return set(), set()

    actors = find_actors(filepath, byml)

    ai_group_refs_in_file = find_ai_group_references(filepath, byml)
    discovered_references.update(ai_group_refs_in_file)

    far_delete_groups_in_file = find_generic_array_references(
        filepath, "FarDeleteGroups", byml
    )
    discovered_references.update(far_delete_groups_in_file)

    simultaneous_groups_in_file = find_generic_array_references(
        filepath, "SimultaneousGroups", byml
    )
    discovered_references.update(simultaneous_groups_in_file)

    total_refs = (
        len(ai_group_refs_in_file)
        + len(far_delete_groups_in_file)
        + len(simultaneous_groups_in_file)
    )
    logging.debug(f"Found {len(actors)} Actors, {total_refs} refs in {filepath}")

    return actors, discovered_references


def generate_cache(threads, dump_path):
    cached_results = defaultdict(dict)

    cached_filepaths = set()
    all_actors = dict()
    all_references = defaultdict(set)

    try:
        with open(".cached_results", "rb") as cached_results_file:
            cached_results = pickle.load(cached_results_file)
        all_actors = cached_results["actors"]
        all_references = cached_results["references"]
        cached_filepaths = cached_results["files"]
    except (OSError, FileNotFoundError):
        logging.debug("Cache not found")

    extensions = ["*.byml"]
    paths = [dump_path]

    matched_filepaths = []
    logging.info("Finding files. . .")
    for path in paths:
        for root, dirs, files in os.walk(path):
            for file_ in files:
                for ext in extensions:
                    if fnmatch.fnmatch(file_, ext):
                        new_filepath = Path(root, file_)
                        if new_filepath.as_posix() not in cached_filepaths:
                            matched_filepaths.append(new_filepath)
    logging.info(
        f"Found {len(matched_filepaths)} new files ({len(cached_filepaths)} cached)"
    )

    if len(matched_filepaths) == 0:
        return

    logging.info("Processing files. . .")
    chunksize = len(matched_filepaths) // (2 * threads)
    logging.debug(f"Using {chunksize} chunks with {threads} threads")
    with ProcessPoolExecutor(max_workers=threads) as p:
        for pool_res in zip(
            matched_filepaths,
            p.map(process_match, matched_filepaths, chunksize=chunksize),
        ):
            path_, file_data = pool_res
            actors, refs = file_data

            for actor in actors:
                all_actors[actor] = path_
            for ref in refs:
                all_references[ref].add(path_)

            cached_filepaths.add(path_.as_posix())

    logging.info(
        f"Processed {len(matched_filepaths)} new files ({len(cached_filepaths)} cached)"
    )

    logging.info("Updating cache. . .")
    with open(".cached_results", "wb") as cached_results_file:
        pickle.dump(
            {
                "actors": all_actors,
                "references": all_references,
                "files": cached_filepaths,
            },
            cached_results_file,
        )


def search_for_refs(type_, item):
    with open(".cached_results", "rb") as cached_results_file:
        cached_results = pickle.load(cached_results_file)
    all_actors = cached_results["actors"]
    all_references = cached_results["references"]

    found_references = []
    for actor, actor_file in all_actors.items():
        actor = json.loads(actor)

        actor_val = actor[type_]
        if isinstance(actor_val, int):
            actor_val = str(actor_val)

        if actor_val == item:
            reference = {
                "hash": actor["Hash"],
                "gyaml": actor["Gyaml"],
                "source": actor_file.as_posix(),
            }
            if refs := all_references[actor["Hash"]]:
                reference["files"] = [r.as_posix() for r in refs]
            found_references.append(reference)

    return found_references


def debug_cache():
    with open(".cached_results", "rb") as cached_results_file:
        cached_results = pickle.load(cached_results_file)
    all_actors = cached_results["actors"]
    all_references = cached_results["references"]
    cached_filepaths = cached_results["files"]

    print(
        PosixPath(
            "wip/Banc/MainField/Cave/Cave_FirstPlateau_0001_GroupSet_000_Static.bcett.byml"
        )
        in cached_filepaths
    )


def main(args):
    if args.regenerate_cache:
        Path(".cached_results").unlink(missing_ok=True)

    if args.action == "generate" or args.regenerate_cache or args.update_cache:
        if args.regenerate_cache:
            dump_dir = args.regenerate_cache
        elif args.update_cache:
            dump_dir = args.update_cache
        else:
            dump_dir = args.identifier
        generate_cache(args.threads, dump_dir)

    if args.action == "gyaml":
        print(json.dumps(search_for_refs("Gyaml", args.identifier), indent=2))

    elif args.action == "hash":
        print(json.dumps(list(search_for_refs("Hash", args.identifier)), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        prog="byml_mapper",
        description="Find relationships between actors in byml files",
        epilog="""
    Copyright (C) 2023  Michael Manis - michaelmanis@tutanota.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
        """,
    )

    parser.add_argument(
        "action",
        choices=["generate", "gyaml", "hash"],
        help=dedent(
            """Specify an action:
                generate - generate cache. Run this first
                gyaml - find actor instances / relationships for all instances of a gyaml object
                hash - find the instantiation / relationships for a given actor hash
            """
        ),
    )
    parser.add_argument(
        "identifier",
        help=dedent(
            """This argument depends on which action you specified:
                generate - specify the path of the game dump. unzip ALL .zs files first (ex: ./dump)
                gyaml - specify a gyaml object. (ex: Miasma_Sphere_150)
                hash - specify a specific actor hash (ex: 18050177814911161587)
            """
        ),
    )
    parser.add_argument(
        "--threads",
        "-t",
        default=6,
        help="How many threads to use for building the cache",
    )
    parser.add_argument(
        "--loglevel",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    parser.add_argument(
        "--update-cache",
        "-u",
        metavar="CACHE_DIR",
        help="Update the cache. This is the same as using the generate action. Specify dump path",
    )
    parser.add_argument(
        "--regenerate-cache",
        "-r",
        metavar="CACHE_DIR",
        help="Delete and regenerate cache. Specify dump path",
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s: %(message)s", level=logging.getLevelName(args.loglevel)
    )

    try:
        main(args)
    # https://docs.python.org/3/library/signal.html#note-on-sigpipe
    except BrokenPipeError:
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)  # Python exits with error code 1 on EPIPE
