"""
State machine system for managing node and object states.
"""

from typing import Any, Callable

from .models import Node, InteractiveObject, NodeState, GameState


class StateMachine:
    """Manages state transitions for nodes and objects."""

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self._state_listeners: list[Callable] = []

    def add_listener(self, callback: Callable) -> None:
        """Add a listener for state changes."""
        self._state_listeners.append(callback)

    def _notify_listeners(self, event_type: str, data: dict) -> None:
        """Notify all listeners of a state change."""
        for callback in self._state_listeners:
            callback(event_type, data)

    def get_current_state(self, node: Node) -> NodeState | None:
        """Get the current state of a node."""
        return node.states.get(node.current_state)

    def get_object_state(self, obj: InteractiveObject) -> NodeState | None:
        """Get the current state of an interactive object."""
        return obj.state_machine.get(obj.current_state)

    def transition_node_state(self, node: Node, new_state: str) -> bool:
        """Transition a node to a new state."""
        if new_state not in node.states:
            return False

        old_state = node.current_state
        node.current_state = new_state

        self._notify_listeners("node_state_change", {
            "node_id": node.id,
            "old_state": old_state,
            "new_state": new_state
        })

        return True

    def transition_object_state(self, obj: InteractiveObject, new_state: str) -> bool:
        """Transition an object to a new state."""
        if new_state not in obj.state_machine:
            return False

        old_state = obj.current_state
        obj.current_state = new_state

        self._notify_listeners("object_state_change", {
            "object_id": obj.id,
            "old_state": old_state,
            "new_state": new_state
        })

        return True

    def check_triggers(self, node: Node) -> str | None:
        """Check if any state triggers should fire and return the new state."""
        for state_name, state in node.states.items():
            if state.trigger and self._evaluate_trigger(state.trigger):
                return state_name
        return None

    def _evaluate_trigger(self, trigger: dict) -> bool:
        """Evaluate a trigger condition."""
        trigger_type = trigger.get("type")

        if trigger_type == "flag_check":
            flag = trigger.get("flag")
            expected_value = trigger.get("value")
            actual_value = self.game_state.player.flags.get(flag)
            return actual_value == expected_value

        elif trigger_type == "stat_check":
            stat = trigger.get("stat")
            operator = trigger.get("operator", "==")
            value = trigger.get("value")
            actual_value = self._get_stat_value(stat)
            return self._compare(actual_value, operator, value)

        elif trigger_type == "item_check":
            item = trigger.get("item")
            count = trigger.get("count", 1)
            actual_count = self.game_state.player.inventory.get(item, 0)
            return actual_count >= count

        return False

    def _get_stat_value(self, stat: str) -> int:
        """Get a stat value from the player."""
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

        # Ability stats (Japanese names)
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

    def update(self, nodes: dict[str, Node]) -> None:
        """Update all nodes, checking for state triggers."""
        for node_id, node in nodes.items():
            new_state = self.check_triggers(node)
            if new_state and new_state != node.current_state:
                self.transition_node_state(node, new_state)
