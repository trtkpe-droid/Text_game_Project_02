"""
Action and effect system for the game engine.
"""

import random
from typing import Any, Callable

from .models import (
    Action, Effect, Requirement, GameState, Node,
    InteractiveObject, WeightedOption, ItemPool, Item,
    normalize_stat_name
)


class ActionResult:
    """Result of executing an action."""

    def __init__(self):
        self.messages: list[str] = []
        self.navigation_target: str | None = None
        self.battle_start: dict | None = None
        self.bind_sequence_start: str | None = None
        self.game_over: bool = False
        self.game_clear: bool = False
        self.ending: str | None = None
        self.success: bool = True

    def add_message(self, message: str) -> None:
        """Add a message to the result."""
        if message:
            self.messages.append(message)


class ActionSystem:
    """System for handling actions and effects."""

    def __init__(self, game_state: GameState, nodes: dict[str, Node],
                 item_pools: dict[str, ItemPool],
                 items: dict[str, Item] | None = None):
        self.game_state = game_state
        self.nodes = nodes
        self.item_pools = item_pools
        self.items = items or {}
        self._custom_handlers: dict[str, Callable] = {}

    def register_handler(self, action_type: str, handler: Callable) -> None:
        """Register a custom action handler."""
        self._custom_handlers[action_type] = handler

    def check_requirements(self, requirements: list[Requirement]) -> bool:
        """Check if all requirements are met."""
        for req in requirements:
            if not self._check_requirement(req):
                return False
        return True

    def _check_requirement(self, req: Requirement) -> bool:
        """Check a single requirement."""
        if req.type == "stat_check":
            actual_value = self._get_stat_value(req.stat)
            return self._compare(actual_value, req.operator, req.value)

        elif req.type == "flag_check":
            actual_value = self.game_state.player.flags.get(req.flag)
            return actual_value == req.value

        elif req.type == "item_check":
            actual_count = self.game_state.player.inventory.get(req.item, 0)
            return actual_count >= req.count

        return True

    def _get_stat_value(self, stat: str) -> int:
        """Get a stat value from the player. Supports Japanese stat names."""
        # Normalize Japanese stat names to English
        stat = normalize_stat_name(stat)

        combat_stats = self.game_state.player.combat_stats
        ability_stats = self.game_state.player.ability_stats

        # Combat stats
        stat_map = {
            "sp": combat_stats.sp,
            "hp": combat_stats.hp,
            "mp": combat_stats.mp,
            "pt": combat_stats.pt,
            "sp_max": combat_stats.sp_max,
            "hp_max": combat_stats.hp_max,
            "mp_max": combat_stats.mp_max,
            "pt_max": combat_stats.pt_max,
        }

        # Ability stats
        ability_map = {
            "sanity": ability_stats.sanity,
            "strength": ability_stats.strength,
            "focus": ability_stats.focus,
            "intelligence": ability_stats.intelligence,
            "knowledge": ability_stats.knowledge,
            "dexterity": ability_stats.dexterity,
        }

        if stat in stat_map:
            return stat_map[stat]
        if stat in ability_map:
            return ability_map[stat]

        return 0

    def _set_stat_value(self, stat: str, value: int) -> None:
        """Set a stat value on the player. Supports Japanese stat names."""
        # Normalize Japanese stat names to English
        stat = normalize_stat_name(stat)

        combat_stats = self.game_state.player.combat_stats
        ability_stats = self.game_state.player.ability_stats

        # Combat stats
        if stat == "sp":
            combat_stats.sp = max(0, min(combat_stats.sp_max, value))
        elif stat == "hp":
            combat_stats.hp = max(0, min(combat_stats.hp_max, value))
        elif stat == "mp":
            combat_stats.mp = max(0, min(combat_stats.mp_max, value))
        elif stat == "pt":
            combat_stats.pt = max(0, min(combat_stats.pt_max, value))

        # Ability stats
        elif stat == "sanity":
            ability_stats.sanity = max(0, min(100, value))
        elif stat == "strength":
            ability_stats.strength = max(0, min(100, value))
        elif stat == "focus":
            ability_stats.focus = max(0, min(100, value))
        elif stat == "intelligence":
            ability_stats.intelligence = max(0, min(100, value))
        elif stat == "knowledge":
            ability_stats.knowledge = max(0, min(100, value))
        elif stat == "dexterity":
            ability_stats.dexterity = max(0, min(100, value))

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare two values using the given operator."""
        if operator == "==":
            return actual == expected
        elif operator == "!=":
            return actual != expected
        elif operator == ">=":
            return actual >= expected
        elif operator == "<=":
            return actual <= expected
        elif operator == ">":
            return actual > expected
        elif operator == "<":
            return actual < expected
        return False

    def get_available_actions(self, node: Node) -> list[Action]:
        """Get all available actions for the current node state."""
        current_state = node.states.get(node.current_state)
        if not current_state:
            return []

        available = []
        for action in current_state.actions:
            if self.check_requirements(action.requirements):
                available.append(action)

        return available

    def get_object_actions(self, obj: InteractiveObject) -> list[Action]:
        """Get all available actions for an object."""
        current_state = obj.state_machine.get(obj.current_state)
        if not current_state:
            return []

        available = []
        for action in current_state.actions:
            if self.check_requirements(action.requirements):
                available.append(action)

        return available

    def execute_action(self, action: Action) -> ActionResult:
        """Execute an action and return the result."""
        result = ActionResult()

        # Check requirements first
        if not self.check_requirements(action.requirements):
            result.success = False
            result.add_message("条件を満たしていません。")
            return result

        # Execute all effects
        for effect in action.effects:
            self._execute_effect(effect, result)

        # Handle navigation type actions
        if action.type == "navigation" and action.target:
            result.navigation_target = action.target

        return result

    def _execute_effect(self, effect: Effect, result: ActionResult) -> None:
        """Execute a single effect."""
        effect_type = effect.type

        # Check for custom handler
        if effect_type in self._custom_handlers:
            self._custom_handlers[effect_type](effect, result, self)
            return

        # Built-in effect handlers
        if effect_type == "message":
            result.add_message(effect.text)

        elif effect_type == "navigation":
            result.navigation_target = effect.target

        elif effect_type == "get_item":
            self._add_item(effect.item, effect.count)
            result.add_message(f"{effect.item}を手に入れた！")

        elif effect_type == "item_roll":
            items = self._roll_items(effect.pool, effect.count)
            for item in items:
                if item:
                    # Handle set items (list of items)
                    if isinstance(item, list):
                        for sub_item in item:
                            if sub_item:
                                self._add_item(sub_item, 1)
                                item_name = self._get_item_name(sub_item)
                                result.add_message(f"{item_name}を手に入れた！")
                    else:
                        self._add_item(item, 1)
                        item_name = self._get_item_name(item)
                        result.add_message(f"{item_name}を手に入れた！")

        elif effect_type == "set_flag":
            self.game_state.player.flags[effect.flag] = effect.value

        elif effect_type == "modify_stat":
            self._modify_stat(effect.stat, effect.operator, effect.value)

        elif effect_type == "change_node_state":
            node_id = effect.node or self.game_state.current_node
            if node_id in self.nodes:
                self.nodes[node_id].current_state = effect.new_state

        elif effect_type == "change_object_state":
            node = self.nodes.get(self.game_state.current_node)
            if node and effect.object in node.objects:
                node.objects[effect.object].current_state = effect.new_state

        elif effect_type == "battle":
            result.battle_start = {
                "enemy": effect.enemy,
                "enemy_pool": effect.enemy_pool
            }

        elif effect_type == "run_bind_sequence":
            result.bind_sequence_start = effect.sequence

        elif effect_type == "switch_bind_sequence":
            result.bind_sequence_start = effect.target
            self.game_state.current_bind_stage = effect.stage

        elif effect_type == "game_over":
            result.game_over = True
            result.add_message(effect.reason or "ゲームオーバー")
            self.game_state.game_over = True

        elif effect_type == "game_clear":
            result.game_clear = True
            result.ending = effect.ending
            self.game_state.game_clear = True

        elif effect_type == "stage_progress":
            self.game_state.current_bind_stage += effect.amount

        elif effect_type == "stage_regress":
            self.game_state.current_bind_stage = max(
                -1, self.game_state.current_bind_stage - effect.amount
            )

        elif effect_type == "escape_bind":
            self.game_state.in_bind_sequence = False
            self.game_state.current_bind_sequence = None
            self.game_state.current_bind_stage = 0

        elif effect_type == "deal_damage":
            if effect.target == "enemy" and self.game_state.current_enemy:
                self.game_state.current_enemy.current_hp -= effect.damage
                result.add_message(f"敵に{effect.damage}のダメージ！")
            elif effect.target == "self":
                if effect.damage_type == "pt":
                    current = self.game_state.player.combat_stats.pt
                    self._set_stat_value("pt", current + effect.damage)
                else:
                    current = self.game_state.player.combat_stats.hp
                    self._set_stat_value("hp", current - effect.damage)
                    result.add_message(f"{effect.damage}のダメージを受けた！")

    def _add_item(self, item_id: str, count: int) -> None:
        """Add an item to the player's inventory."""
        current = self.game_state.player.inventory.get(item_id, 0)
        self.game_state.player.inventory[item_id] = current + count

    def _get_item_name(self, item_id: str) -> str:
        """Get the display name of an item."""
        item = self.items.get(item_id)
        return item.name if item else item_id

    def use_item(self, item_id: str) -> ActionResult:
        """Use an item from inventory."""
        result = ActionResult()

        # Check if player has the item
        if self.game_state.player.inventory.get(item_id, 0) <= 0:
            result.success = False
            result.add_message("そのアイテムを持っていません。")
            return result

        # Get item definition
        item = self.items.get(item_id)
        if not item:
            result.success = False
            result.add_message("不明なアイテムです。")
            return result

        # Check if item is usable
        if item.type not in ["consumable", "usable"]:
            result.success = False
            result.add_message("このアイテムは使用できません。")
            return result

        # Consume the item
        self.game_state.player.inventory[item_id] -= 1
        if self.game_state.player.inventory[item_id] <= 0:
            del self.game_state.player.inventory[item_id]

        result.add_message(f"{item.name}を使った！")

        # Execute item effects
        for effect in item.effects:
            self._execute_effect(effect, result)

        return result

    def get_usable_items(self) -> list[Item]:
        """Get list of usable items in inventory."""
        usable = []
        for item_id, count in self.game_state.player.inventory.items():
            if count > 0:
                item = self.items.get(item_id)
                if item and item.type in ["consumable", "usable"]:
                    usable.append(item)
        return usable

    def _roll_items(self, pool_id: str, count: int) -> list[Any]:
        """Roll items from a pool."""
        pool = self.item_pools.get(pool_id)
        if not pool:
            return []

        results = []
        for _ in range(count):
            item = self._weighted_random(pool.options)
            results.append(item)

        return results

    def _weighted_random(self, options: list[WeightedOption]) -> Any:
        """Select a random option based on weights."""
        if not options:
            return None

        total_weight = sum(opt.weight for opt in options)
        if total_weight == 0:
            return random.choice(options).value

        roll = random.randint(1, total_weight)
        cumulative = 0
        for opt in options:
            cumulative += opt.weight
            if roll <= cumulative:
                return opt.value

        return options[-1].value

    def _modify_stat(self, stat: str, operator: str, value: int) -> None:
        """Modify a stat value."""
        current = self._get_stat_value(stat)

        if operator == "+":
            new_value = current + value
        elif operator == "-":
            new_value = current - value
        elif operator == "=":
            new_value = value
        elif operator == "*":
            new_value = current * value
        elif operator == "/":
            new_value = current // value if value != 0 else current
        else:
            new_value = current

        self._set_stat_value(stat, new_value)
