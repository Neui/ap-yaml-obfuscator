#!/usr/bin/env python3

import argparse
import copy
import dataclasses
import logging
import obfuscate
import random
import sys
import time
import yaml  # PyYAML
from typing import Any
from apmodel import Option, WeightedOption, Options, \
    Trigger, Triggers, Root


log = logging.getLogger(__name__)

DEBUG = False
WEIRD_CHARS = (
    # https://en.wikipedia.org/wiki/Whitespace_character
    # Whitespaces
    " "
    # "\t"  # YAMLLint.com makes it visible
    # "\n"  # YAMLLint.com makes it visible
    # "\u000c"  # FORM FEED  # YAMLLint.com makes it visible
    # "\u000d"  # CARRIAGE RETURN  # YAMLLint.com makes it visible
    # "\u0085"  # NEXT LINE  # Is visible
    "\u00a0"  # NO-BREAK SPACE
    # "\u1680"  # OGHAM SPACE MARK  # Is visible
    "\u2000"  # EN QUAD
    "\u2001"  # EM QUAD
    "\u2002"  # EN SPACE
    "\u2003"  # EM SPACE
    "\u2004"  # THREE-PER-EM SPACE
    "\u2005"  # FOUR-PER-EM SPACE
    "\u2006"  # SIX-PER-EM SPACE
    "\u2007"  # FIGURE SPACE
    "\u2008"  # PUNCTUATION SPACE
    "\u2009"  # THIN SPACE
    "\u200a"  # HAIR SPACE
    "\u2028"  # LINE SEPERATOR
    "\u2029"  # PARAGRAPH SEPARATOR
    "\u202f"  # NARROW NO-BREAK SPACE
    "\u205f"  # MEDIUM MATHEMATICAL SPACE
    "\u3000"  # IDEOGRAPHIC SPACE
    # Special
    "\u180e"  # MONGOLIAN VOWEL SEPARATOR
    "\u200b"  # ZERO WIDTH SPACE
    "\u200d"  # ZERO WIDTH JOINER
    "\u2060"  # WORD JOINER
    "\ufeff"  # ZERO WIDTH NON-BREAKING SPACE
)
if DEBUG:
    WEIRD_CHARS = ("abcdefghijklmnopqrstuvwxyz")


def generate_new_name(minlen=20, maxlen=50, random=random) -> str:
    return ''.join(random.choice(WEIRD_CHARS)
                   for _ in range(random.randint(minlen, maxlen)))


def generate_unique_name(inside, minlen=20, maxlen=50, random=random) -> str:
    for _ in range(100000):
        name = generate_new_name(minlen, maxlen, random)
        if name not in inside:
            return name
    raise Exception("Unable to generate unique name")


def generate_multiple_unique_names(count: int,
                                   minlen=20, maxlen=50, random=random
                                   ) -> list[str]:
    names: list[str] = []
    for _ in range(count):
        names.append(generate_unique_name(names))
    return names


def list_extend_beginning(base_list: list, prepend_with: list) -> list:
    for elem in reversed(prepend_with):
        base_list.insert(0, elem)
    return base_list


@dataclasses.dataclass
class WrappedWeightedOption(WeightedOption):
    original_option: Option
    original_name: str
    wrapped_weights_names: dict[str, str]

    @classmethod
    def wrap(cls, name: str, option: WeightedOption
             ) -> 'WrappedWeightedOption':
        return cls(original_option=option, original_name=name,
                   weights=option.weights.copy(),
                   wrapped_weights_names={k: k for k in option.weights.keys()})


@dataclasses.dataclass
class ContextExtra:
    # Name → Option
    game_name: str
    options: Options = dataclasses.field(default_factory=dict)
    triggers: Triggers = dataclasses.field(default_factory=list)

    def generate_option(self, option: Option) -> tuple[str, Option]:
        name = generate_unique_name(self.options.keys())
        self.options[name] = option
        return (name, option)

    @staticmethod
    def generate_option_weight_names(num: int) -> list[str]:
        return generate_multiple_unique_names(num)

    def create_wrapper_options(self, orig_options: dict[str, Option]
                               ) -> tuple[Triggers, dict[str, str]]:
        """
        Wrap existing options by replacing them with renamed version
        and use triggers to apply them to the original option.
        """
        real_to_wrapped: dict[str, str] = dict()
        triggers: list[Trigger] = []
        for orig_name, orig_option in orig_options.items():
            if not isinstance(orig_option, WeightedOption):
                log.debug("Skipping %r, not a WeightedOption", orig_name)
                continue

            wrapped_name, wrapped_option = self.generate_option(
                WrappedWeightedOption.wrap(orig_name, orig_option))
            assert isinstance(wrapped_option, WrappedWeightedOption)
            real_to_wrapped[orig_name] = wrapped_name

            wrapped_weight_names: set[str] = set()
            wrapped_option.weights = {}
            wrapped_option.wrapped_weights_names = {}
            for weight_name, weight in orig_option.weights.items():
                wrapped_weight_name = generate_unique_name(
                    wrapped_weight_names)
                wrapped_weight_names.add(wrapped_weight_name)
                wrapped_option.weights[wrapped_weight_name] = weight
                wrapped_option.wrapped_weights_names[weight_name] \
                    = wrapped_weight_name
                triggers.append(Trigger(
                    option_category=self.game_name,
                    option_name=wrapped_name,
                    option_result=wrapped_weight_name,
                    options={self.game_name: {orig_name: weight_name}}))
            assert len(wrapped_option.weights) == len(orig_option.weights)
            assert wrapped_option.weights != {}

        return triggers, real_to_wrapped


class Context:
    orig_root: Root
    root: Root
    """YAML we modify"""
    extra_root: ContextExtra
    """Extra modifications we do on the top-level"""
    extra_games: dict[str, ContextExtra]
    """Extra modifications we do per game"""
    iteration: int

    def __init__(self, root: Root):
        self.orig_root = root
        self.root = copy.deepcopy(root)
        self.random = random
        self.extra_root = ContextExtra("")
        self.extra_games = dict()
        self.iteration = 0
        for game in self.root.games:
            self.extra_games[game.name] = ContextExtra(game.name)

    def obfuscate(self) -> None:
        for game_name in self.extra_games.keys():
            self.obfuscate_game(game_name)
        self.iteration += 1

    def obfuscate_game(self, game_name: str) -> None:
        self.obfuscate_game_wrap(game_name, self.iteration == 0)

    def obfuscate_game_wrap(self, game_name: str, first_time: bool) -> None:
        game = self.root.game_by_name(game_name)
        extra_games = self.extra_games[game_name]
        # Wrap every option in custom options
        wrapped_triggers, real_name_to_wrapped = \
            extra_games.create_wrapper_options(
                {option_name: option
                 for option_name, option in game.options.items()
                 if isinstance(option, WeightedOption)})
        for real_name, wrapped_name in real_name_to_wrapped.items():
            del game.options[real_name]
            game.options[wrapped_name] = extra_games.options[wrapped_name]
        # Also rename existing triggers
        if first_time:
            # Only do this on the first time, otherwise there is a rpoblem
            # about creating dead options.
            # Example:
            #   progression_balancing: random
            # First iteration:
            #   abc: random
            #   triggers:
            #     - ...
            #       option_name: abc
            #       options: {progression_balancing: random}
            # Second iteration with triggers:
            #   xyz: random
            #   triggers:
            #     - ...
            #       option_name: xyz
            #       options: {progression_balancing: random}
            #     - ...  # Unused! since this appears later
            #       option_name: xyz
            #       options: {abc: random}
            for trigger in game.triggers:
                # Ignore triggers not to us
                if trigger.option_category != game_name \
                        or trigger.option_name not in real_name_to_wrapped.keys():
                    log.debug("Ignoring trigger because not affected: %r",
                              trigger)
                    continue

                trigger.option_name = real_name_to_wrapped[trigger.option_name]

                wrapped_option = extra_games.options[trigger.option_name]
                assert isinstance(wrapped_option, WrappedWeightedOption)
                new_weight_names = wrapped_option.wrapped_weights_names
                trigger.option_result = new_weight_names[trigger.option_result]

                # Also rename options it modifies
                game_trigger_options = trigger.options.get(game_name, {})
                for option_name, weights in list(game_trigger_options.items()):
                    if option_name not in real_name_to_wrapped.keys():
                        log.debug("Ignoring option because not wrapped: %r",
                                  option_name)
                        continue
                    if not isinstance(weights, dict):
                        # Turn option_name: 'xyz' into option_name: {'xyz':1}
                        weights = {weights: 1}
                    wrapped_option_name = real_name_to_wrapped[option_name]
                    del game_trigger_options[option_name]
                    game_trigger_options[wrapped_option_name] = weights
                    # Also rename weight names
                    wrapped_option = extra_games.options[wrapped_option_name]
                    assert isinstance(wrapped_option, WrappedWeightedOption)
                    new_weight_names = wrapped_option.wrapped_weights_names
                    for weight_name, weight in list(weights.items()):
                        if weight_name in new_weight_names.keys():
                            del weights[weight_name]
                            weights[new_weight_names[weight_name]] = weight
            # Insert at the end so the modified existing triggers work correctly
            game.triggers.extend(wrapped_triggers)
        else:
            list_extend_beginning(game.triggers, wrapped_triggers)

    def generate(self) -> dict[str, Any]:
        return self.root.output()


def to_obfuscated_ap_yaml(obj) -> str:
    root = Root.parse(obj)
    context = Context(root)
    for _ in range(2):
        begin_time = time.monotonic()
        context.obfuscate()
        end_time = time.monotonic()
        log.debug("Obfuscation iteration took %0.3fs", end_time - begin_time)
    if DEBUG:
        return yaml.dump(context.generate())
    else:
        return obfuscate.to_obfuscated_yaml(context.generate())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.description = "Obfuscate YAML"

    parser.add_argument("input", help="Input AP YAML")
    parser.add_argument("output", help="Output obfuscated AP YAML")

    args = parser.parse_args()

    with open(args.input, 'rt') as input_file:
        # TODO look into why load_all doesnt work with multiple documents
        # (but seemingly works on archipelago)
        # inp = list(yaml.safe_load_all(input_file.read()))
        inp = [yaml.safe_load(i) for i in input_file.read().split('\n---\n')]

    with open(args.output, 'wt') as output_file:
        output_file.write("\n---\n".join(map(to_obfuscated_ap_yaml, inp)))

    return 0


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    sys.exit(main())
