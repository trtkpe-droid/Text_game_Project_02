"""
Data models for the game engine.
Uses dataclasses for type safety and validation.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class ActionType(Enum):
    """Types of actions available in the game."""
    NAVIGATION = "navigation"
    MESSAGE = "message"
    GET_ITEM = "get_item"
    ITEM_ROLL = "item_roll"
    SET_FLAG = "set_flag"
    MODIFY_STAT = "modify_stat"
    CHANGE_NODE_STATE = "change_node_state"
    CHANGE_OBJECT_STATE = "change_object_state"
    BATTLE = "battle"
    RUN_BIND_SEQUENCE = "run_bind_sequence"
    SWITCH_BIND_SEQUENCE = "switch_bind_sequence"
    GAME_OVER = "game_over"
    GAME_CLEAR = "game_clear"
    INTERACTION = "interaction"
    STAGE_PROGRESS = "stage_progress"
    STAGE_REGRESS = "stage_regress"
    ESCAPE_BIND = "escape_bind"
    DEAL_DAMAGE = "deal_damage"


class RequirementType(Enum):
    """Types of requirements for actions."""
    STAT_CHECK = "stat_check"
    FLAG_CHECK = "flag_check"
    ITEM_CHECK = "item_check"


class Operator(Enum):
    """Comparison operators."""
    EQ = "=="
    NE = "!="
    GE = ">="
    LE = "<="
    GT = ">"
    LT = "<"
    ADD = "+"
    SUB = "-"
    SET = "="
    MUL = "*"
    DIV = "/"


@dataclass
class Requirement:
    """Requirement for an action to be available."""
    type: str
    stat: Optional[str] = None
    flag: Optional[str] = None
    item: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    count: int = 1


@dataclass
class Effect:
    """Effect of an action."""
    type: str
    target: Optional[str] = None
    text: Optional[str] = None
    item: Optional[str] = None
    count: int = 1
    pool: Optional[str] = None
    flag: Optional[str] = None
    value: Any = None
    stat: Optional[str] = None
    operator: Optional[str] = None
    node: Optional[str] = None
    new_state: Optional[str] = None
    object: Optional[str] = None
    enemy: Optional[str] = None
    enemy_pool: Optional[str] = None
    sequence: Optional[str] = None
    stage: int = 0
    reason: Optional[str] = None
    ending: Optional[str] = None
    amount: int = 1
    damage: int = 0
    damage_type: Optional[str] = None


@dataclass
class Action:
    """An action that can be performed."""
    id: str
    type: str
    label: str
    target: Optional[str] = None
    requirements: list[Requirement] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class NodeState:
    """A state within a node's state machine."""
    description: str
    actions: list[Action] = field(default_factory=list)
    trigger: Optional[dict] = None


@dataclass
class InteractiveObject:
    """An interactive object within a node."""
    id: str
    type: str
    state_machine: dict[str, NodeState] = field(default_factory=dict)
    initial_state: str = "normal"
    current_state: str = ""

    def __post_init__(self):
        if not self.current_state:
            self.current_state = self.initial_state


@dataclass
class NodeMetadata:
    """Metadata for a node."""
    display_name: str
    description: str = ""


@dataclass
class Node:
    """A location or event point in the game."""
    id: str
    type: str
    metadata: NodeMetadata
    states: dict[str, NodeState] = field(default_factory=dict)
    initial_state: str = "normal"
    current_state: str = ""
    objects: dict[str, InteractiveObject] = field(default_factory=dict)

    def __post_init__(self):
        if not self.current_state:
            self.current_state = self.initial_state


@dataclass
class WeightedOption:
    """A weighted option for random selection."""
    weight: int
    value: Any


@dataclass
class WeightedRandom:
    """Weighted random selection."""
    type: str = "weighted_random"
    options: list[WeightedOption] = field(default_factory=list)


@dataclass
class ItemPool:
    """A pool of items for random selection."""
    id: str
    options: list[WeightedOption] = field(default_factory=list)


@dataclass
class CombatStats:
    """Combat stats for player or enemy."""
    sp: int = 100
    sp_max: int = 100
    hp: int = 80
    hp_max: int = 80
    mp: int = 50
    mp_max: int = 50
    pt: int = 0
    pt_max: int = 100


@dataclass
class AbilityStats:
    """Ability stats for checks and calculations."""
    sanity: int = 70  # 正気
    strength: int = 50  # 筋力
    focus: int = 60  # 集中
    intelligence: int = 65  # 知性
    knowledge: int = 55  # 知識
    dexterity: int = 45  # 器用


# Japanese to English stat name mapping
STAT_NAME_MAP: dict[str, str] = {
    # Japanese -> English
    "正気": "sanity",
    "筋力": "strength",
    "集中": "focus",
    "知性": "intelligence",
    "知識": "knowledge",
    "器用": "dexterity",
    # Combat stats
    "SP": "sp",
    "HP": "hp",
    "MP": "mp",
    "PT": "pt",
    # English names (pass through)
    "sanity": "sanity",
    "strength": "strength",
    "focus": "focus",
    "intelligence": "intelligence",
    "knowledge": "knowledge",
    "dexterity": "dexterity",
    "sp": "sp",
    "hp": "hp",
    "mp": "mp",
    "pt": "pt",
    "sp_max": "sp_max",
    "hp_max": "hp_max",
    "mp_max": "mp_max",
    "pt_max": "pt_max",
}


def normalize_stat_name(stat: str) -> str:
    """Convert Japanese stat name to English internal name."""
    return STAT_NAME_MAP.get(stat, stat)


@dataclass
class Player:
    """Player character."""
    combat_stats: CombatStats = field(default_factory=CombatStats)
    ability_stats: AbilityStats = field(default_factory=AbilityStats)
    inventory: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)
    spells: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    status_effects: list["StatusEffectInstance"] = field(default_factory=list)
    brands: list["Brand"] = field(default_factory=list)

    def has_status(self, status_id: str) -> bool:
        """Check if player has a specific status effect."""
        return any(se.id == status_id for se in self.status_effects)

    def is_action_prevented(self) -> bool:
        """Check if player's action is prevented by status effects."""
        for se in self.status_effects:
            for effect in se.effects:
                if effect.get("type") == "prevent_action":
                    return True
        return False

    def has_brand(self, enemy_id: str) -> bool:
        """Check if player has a brand from specific enemy."""
        return any(b.enemy_id == enemy_id for b in self.brands)

    def get_brand_debuff(self, enemy_id: str) -> float:
        """Get the attack debuff ratio for a specific enemy (0.0-1.0)."""
        for brand in self.brands:
            if brand.enemy_id == enemy_id:
                return brand.debuff_ratio
        return 0.0

    def add_brand(self, enemy_id: str, enemy_name: str, debuff_ratio: float = 0.2) -> None:
        """Add a brand from an enemy (if not already branded)."""
        if not self.has_brand(enemy_id):
            from .models import Brand  # Avoid circular import at module level
            self.brands.append(Brand(
                enemy_id=enemy_id,
                enemy_name=enemy_name,
                debuff_ratio=debuff_ratio
            ))

    def remove_brand(self, enemy_id: str) -> bool:
        """Remove a brand. Returns True if removed, False if not found."""
        for i, brand in enumerate(self.brands):
            if brand.enemy_id == enemy_id:
                self.brands.pop(i)
                return True
        return False


@dataclass
class EnemyStats:
    """Stats for an enemy."""
    hp: int = 100
    atk: int = 20
    defense: int = 10
    matk: int = 15
    initiative: int = 10


@dataclass
class EnemyRewards:
    """Rewards for defeating an enemy."""
    exp: int = 0
    drops: Optional[WeightedRandom] = None


@dataclass
class EnemyText:
    """Text for enemy encounters."""
    encounter: str = ""
    defeat: str = ""
    victory: str = ""


@dataclass
class BehaviorNode:
    """A node in the behavior tree."""
    type: str
    name: Optional[str] = None
    conditions: list[dict] = field(default_factory=list)
    action: Optional[dict] = None
    children: list["BehaviorNode"] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)


@dataclass
class Enemy:
    """An enemy character."""
    id: str
    name: str
    description: str = ""
    stats: EnemyStats = field(default_factory=EnemyStats)
    current_hp: int = 0
    rewards: EnemyRewards = field(default_factory=EnemyRewards)
    text: EnemyText = field(default_factory=EnemyText)
    attack_texts: list[str] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    behavior_tree: Optional[BehaviorNode] = None
    events: dict[str, str] = field(default_factory=dict)
    cooldowns: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.stats.hp


@dataclass
class SuccessCheck:
    """Success check configuration for custom actions."""
    type: str  # fixed, stat_based, formula
    rate: int = 50
    base_rate: int = 0
    formula: Optional[str] = None
    expression: Optional[str] = None
    modifiers: list[dict] = field(default_factory=list)


@dataclass
class CustomAction:
    """A custom action in a bind sequence stage."""
    id: str
    label: str
    description: str = ""
    requirements: list[Requirement] = field(default_factory=list)
    cost: dict[str, int] = field(default_factory=dict)
    success_check: Optional[SuccessCheck] = None
    on_success: Optional[dict] = None
    on_failure: Optional[dict] = None


@dataclass
class DefaultChoiceOverride:
    """Override for default choices in bind sequences."""
    enabled: bool = True
    override_result: Optional[str] = None  # auto_success, auto_fail
    success_rate_modifier: int = 0
    reason: Optional[str] = None


@dataclass
class BindStage:
    """A stage in a bind sequence."""
    stage: int
    description: str
    player_texts: dict[str, Any] = field(default_factory=dict)
    enemy_reactions: dict[str, str] = field(default_factory=dict)
    default_choices_override: dict[str, DefaultChoiceOverride] = field(default_factory=dict)
    custom_actions: list[CustomAction] = field(default_factory=list)
    loop_effects: list[Effect] = field(default_factory=list)


@dataclass
class BindSequenceConfig:
    """Configuration for a bind sequence."""
    base_difficulty: int = 50
    escape_target: str = "battle_resume"
    loop_damage: dict[str, int] = field(default_factory=dict)


@dataclass
class BindSequenceMetadata:
    """Metadata for a bind sequence."""
    name: str
    description: str = ""


@dataclass
class BindSequence:
    """A bind sequence (restraint event)."""
    id: str
    metadata: BindSequenceMetadata
    config: BindSequenceConfig = field(default_factory=BindSequenceConfig)
    stages: list[BindStage] = field(default_factory=list)


@dataclass
class SpellEffect:
    """Effect of a spell."""
    type: str
    damage_type: Optional[str] = None
    element: Optional[str] = None
    base: int = 0
    scaling: Optional[dict] = None
    status: Optional[str] = None
    duration: int = 0
    chance: int = 100


@dataclass
class SpellText:
    """Text for spell casting."""
    cast: str = ""
    hit: str = ""
    miss: str = ""
    success: str = ""
    resist: str = ""


@dataclass
class Spell:
    """A spell or skill."""
    id: str
    name: str
    description: str = ""
    cost: dict[str, int] = field(default_factory=dict)
    effects: list[SpellEffect] = field(default_factory=list)
    text: SpellText = field(default_factory=SpellText)


@dataclass
class StatusEffect:
    """A status effect definition."""
    id: str
    name: str
    description: str = ""
    duration: int = 1
    effects: list[dict] = field(default_factory=list)  # On-apply effects (e.g., prevent_action)
    tick_effects: list[dict] = field(default_factory=list)  # Per-turn effects (e.g., poison damage)
    text: dict[str, str] = field(default_factory=dict)


@dataclass
class StatusEffectInstance:
    """An active status effect on a character."""
    id: str
    name: str
    remaining_turns: int
    effects: list[dict] = field(default_factory=list)
    tick_effects: list[dict] = field(default_factory=list)
    text: dict[str, str] = field(default_factory=dict)


@dataclass
class Brand:
    """A brand/mark left by an enemy after climax defeat."""
    enemy_id: str
    enemy_name: str = ""
    debuff_ratio: float = 0.2  # Default: 20% attack reduction


@dataclass
class Item:
    """An item."""
    id: str
    name: str
    description: str = ""
    type: str = "consumable"
    effects: list[Effect] = field(default_factory=list)
    value: int = 0


@dataclass
class ModMetadata:
    """Metadata for a MOD."""
    name: str
    author: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ModInfo:
    """Information about a MOD."""
    id: str
    version: str
    metadata: ModMetadata
    entry_point: str = "start"
    dependencies: dict[str, Any] = field(default_factory=dict)


@dataclass
class GameState:
    """Current state of the game."""
    current_node: str = ""
    player: Player = field(default_factory=Player)
    visited_nodes: set[str] = field(default_factory=set)
    in_battle: bool = False
    in_bind_sequence: bool = False
    current_enemy: Optional[Enemy] = None
    current_bind_sequence: Optional[str] = None
    current_bind_stage: int = 0
    game_over: bool = False
    game_clear: bool = False
