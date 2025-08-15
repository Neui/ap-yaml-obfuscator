import dataclasses
import logging
from typing import Any


log = logging.getLogger(__name__)


@dataclasses.dataclass
class Option:
    pass

    @classmethod
    def parse(cls, option_name: str, obj) -> 'Option':
        if option_name in GAME_SPECIAL_OPTIONS:
            return CustomOption.parse(option_name, obj)
        try:
            return WeightedOption.parse(option_name, obj)
        except NotImplementedError:
            return CustomOption.parse(option_name, obj)

    def output(self) -> Any:
        raise NotImplementedError(str(self))


Options = dict[str, Option]


@dataclasses.dataclass
class WeightedOption(Option):
    """Weights of the different values."""
    weights: dict[str, int]

    @classmethod
    def parse(cls, option_name: str, obj) -> 'WeightedOption':
        if isinstance(obj, dict):
            return cls(weights={str(k): v for k, v in obj.items()})
        elif isinstance(obj, str) or isinstance(obj, int):
            return cls(weights={str(obj): 1})
        elif isinstance(obj, list):
            raise NotImplementedError("Not weighted option")
        else:
            raise NotImplementedError(str(type(obj)))

    def output(self) -> Any:
        if len(self.weights) == 1:
            return list(self.weights.keys())[0]
        elif len(self.weights) == 0:
            raise Exception("Empty weigthed option")
        else:
            return self.weights


@dataclasses.dataclass
class CustomOption(Option):
    """Option that is seemingly not weigthed?"""
    raw: Any

    @classmethod
    def parse(cls, option_name: str, obj) -> 'CustomOption':
        return cls(raw=obj)

    def output(self) -> Any:
        return self.raw


@dataclasses.dataclass
class Trigger:
    """Game or root to trigger"""
    option_category: str
    """Option inside that category"""
    option_name: str
    """Trigger when the specified option equals to this result"""
    option_result: str
    """What options to apply when this is the case"""
    options: dict[str, Any]

    @classmethod
    def parse(cls, obj) -> 'Trigger':
        assert isinstance(obj, dict)
        return cls(
            # TODO: Support not specifiying option category
            option_category="" if obj.get('option_category') is None else
                            str(obj['option_category']),
            option_name=str(obj['option_name']),
            option_result=obj['option_result'],
            options=obj['options'])

    def output(self) -> dict[str, Any]:
        return {
            'option_category': self.option_category,
            'option_name': self.option_name,
            'option_result': self.option_result,
            'options': self.options
        }


Triggers = list[Trigger]


@dataclasses.dataclass
class Game:
    name: str
    triggers: Triggers
    options: Options

    @classmethod
    def parse(cls, name: str, obj) -> 'Game':
        assert isinstance(obj, dict)
        triggers = [Trigger.parse(trigger)
                    for trigger in obj.get('triggers', [])]
        options = {option_name: Option.parse(option_name, option)
                   for option_name, option in obj.items()
                   if option_name != "triggers"}
        return cls(
            name=name,
            triggers=triggers,
            options=options)

    def output(self) -> dict[str, Any]:
        try:
            base: dict[str, Any] = {}
            for option_name, option in self.options.items():
                try:
                    base[option_name] = option.output()
                except Exception as e:
                    e.add_note(f"Option: {repr(option_name)}")
                    raise

            if self.triggers != []:
                base['triggers'] = [trigger.output()
                                    for trigger in self.triggers]
            return base
        except Exception as e:
            e.add_note(f"Game: {self.name}")
            raise


@dataclasses.dataclass
class Requires:
    version: str = "0.6.1"
    # plando: str = ""

    def output(self) -> dict[str, Any]:
        return {
            'version': self.version
        }


TOP_LEVEL_DIRECTIVES = {"name", "description", "requires", "game", "triggers"}
GAME_LEVEL_DIRECTIVES = {"triggers"}
GAME_SPECIAL_OPTIONS = {"local_items", "non_local_items", "start_inventory",
                        "start_inventory_from_pool",
                        "start_hints", "start_location_hints",
                        "exclude_locations", "priority_locations",
                        "item_links",
                        "plando_weakness"}


@dataclasses.dataclass
class Root:
    name: str
    description: str
    requires: Requires
    games: list[Game] = dataclasses.field(default_factory=list)
    game_weights: dict[str, int] = dataclasses.field(default_factory=dict)
    triggers: Triggers = dataclasses.field(default_factory=list)

    def game_by_name(self, game_name: str) -> Game:
        for game in self.games:
            if game.name == game_name:
                return game
        raise IndexError(game_name)

    @classmethod
    def parse(cls, obj) -> 'Root':
        assert isinstance(obj, dict)
        requires = Requires(version=obj['requires']['version'])
        if isinstance(obj['game'], str):
            game_weigths = {obj['game']: 1}
        elif isinstance(obj['game'], dict):
            game_weigths = obj['game']
        else:
            raise NotImplementedError(f"Unknown game node {obj['game']}")
        # game_names = game_weigths.keys()

        games = [Game.parse(game_name, game)
                 for game_name, game in obj.items()
                 if game_name not in TOP_LEVEL_DIRECTIVES]

        triggers = [Trigger.parse(trigger)
                    for trigger in obj.get('triggers', [])]

        return cls(
            name=obj['name'],
            description=obj['description'],
            requires=requires,
            games=games,
            game_weights=game_weigths,
            triggers=triggers)

    def output(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            'name': self.name,
            'description': self.description,
            'requires': {
                'version': self.requires.version
            },
        }
        if self.triggers != []:
            base['triggers'] = [trigger.output() for trigger in self.triggers]
        assert len(self.game_weights) > 0
        if len(self.game_weights) == 1:
            base['game'] = list(self.game_weights.keys())[0]
        else:
            base['game'] = self.game_weights.copy()
        base.update({game.name: game.output() for game in self.games})
        return base
