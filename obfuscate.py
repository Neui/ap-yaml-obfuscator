#!/usr/bin/env python3

import argparse
import logging
import sys
import yaml


log = logging.getLogger(__name__)


def ord_to_unicode(codepoint: int) -> str:
    assert codepoint >= 0
    assert codepoint < 2**32
    if codepoint < 2**16:
        return f'\\u{codepoint:04x}'
    else:
        return f'\\U{codepoint:08x}'


def str_to_unicode_escapes(string: str) -> str:
    return ''.join(map(ord_to_unicode, map(ord, string)))


def do_dict_inner(key, value) -> str:
    try:
        if isinstance(key, str):
            return f'"{str_to_unicode_escapes(key)}":{do(value)}'
        elif isinstance(key, int):
            # Space required otherwise there is a syntax error
            return f'{key}: {do(value)}'
        elif key is None:
            # TODO: Why doesnt null work here?
            return f'"":{do(value)}'
        else:
            raise NotImplementedError(str(type(key)))
    except NotImplementedError as e:
        e.add_note(f"inside {repr(key)}")
        # e.add_note(f"inside {repr(key)}, {repr(value)}")
        raise


def do(obj) -> str:
    if isinstance(obj, str):
        return f'"{str_to_unicode_escapes(obj)}"'
    elif isinstance(obj, list):
        try:
            return '[' + ','.join(map(do, obj)) + ']'
        except NotImplementedError as e:
            e.add_note("inside list")
            raise
    elif obj is None:
        return 'null'
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    elif isinstance(obj, int):
        return str(obj)
    elif isinstance(obj, float):
        return str(obj)
    elif isinstance(obj, dict):
        return '{' + ','.join(map(lambda x: do_dict_inner(*x),
                                  obj.items())) + '}'
    else:
        raise NotImplementedError(str(type(obj)))


def to_obfuscated_yaml(obj) -> str:
    return do(obj)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.description = "Obfuscate YAML"

    parser.add_argument("input", help="Input YAML")
    parser.add_argument("output", help="Output obfuscated YAML")

    args = parser.parse_args()

    with open(args.input, 'rt') as input_file:
        # TODO look into why load_all doesnt work with multiple documents
        # (but seemingly works on archipelago)
        # inp = list(yaml.safe_load_all(input_file.read()))
        inp = [yaml.safe_load(i) for i in input_file.read().split('\n---\n')]

    with open(args.output, 'wt') as output_file:
        output_file.write("\n---\n".join(map(to_obfuscated_yaml, inp)))

    return 0


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    sys.exit(main())
