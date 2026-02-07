"""
Plugin system for extending the game engine.
Allows custom actions and conditions to be added via Python modules.
"""

import importlib.util
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from .models import GameState, Effect
from .actions import ActionResult


class ActionPlugin(ABC):
    """Base class for custom action plugins."""

    # The type name used in YAML
    action_type: str = ""

    @abstractmethod
    def execute(self, context: "PluginContext", params: dict) -> ActionResult:
        """
        Execute the custom action.

        Args:
            context: Game context with access to state and utilities
            params: Parameters from YAML definition

        Returns:
            ActionResult with messages and effects
        """
        pass


class ConditionPlugin(ABC):
    """Base class for custom condition plugins."""

    # The type name used in YAML
    condition_type: str = ""

    @abstractmethod
    def evaluate(self, context: "PluginContext", params: dict) -> bool:
        """
        Evaluate the custom condition.

        Args:
            context: Game context
            params: Parameters from YAML definition

        Returns:
            True if condition is met
        """
        pass


class PluginContext:
    """Context provided to plugins for accessing game state."""

    def __init__(self, game_state: GameState, nodes: dict, enemies: dict,
                 items: dict, navigate_func: Callable):
        self.game_state = game_state
        self.player = game_state.player
        self.nodes = nodes
        self.enemies = enemies
        self.items = items
        self._navigate = navigate_func
        self._effects: list[str] = []

    def message(self, text: str) -> ActionResult:
        """Create a result with a message."""
        result = ActionResult()
        result.add_message(text)
        return result

    def navigate_to(self, node_id: str) -> None:
        """Navigate to a different node."""
        self._navigate(node_id)

    def add_effect(self, effect_name: str) -> None:
        """Add a visual/audio effect."""
        self._effects.append(effect_name)

    def get_flag(self, flag_name: str) -> Any:
        """Get a flag value."""
        return self.player.flags.get(flag_name)

    def set_flag(self, flag_name: str, value: Any) -> None:
        """Set a flag value."""
        self.player.flags[flag_name] = value

    def has_item(self, item_id: str, count: int = 1) -> bool:
        """Check if player has an item."""
        return self.player.inventory.get(item_id, 0) >= count

    def add_item(self, item_id: str, count: int = 1) -> None:
        """Add an item to inventory."""
        current = self.player.inventory.get(item_id, 0)
        self.player.inventory[item_id] = current + count

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """Remove an item from inventory. Returns False if insufficient."""
        current = self.player.inventory.get(item_id, 0)
        if current < count:
            return False
        self.player.inventory[item_id] = current - count
        return True

    def get_stat(self, stat_name: str) -> int:
        """Get a player stat value."""
        combat = self.player.combat_stats
        ability = self.player.ability_stats

        stat_map = {
            "sp": combat.sp, "hp": combat.hp, "mp": combat.mp, "pt": combat.pt,
            "sp_max": combat.sp_max, "hp_max": combat.hp_max,
            "mp_max": combat.mp_max, "pt_max": combat.pt_max,
            "sanity": ability.sanity, "strength": ability.strength,
            "focus": ability.focus, "intelligence": ability.intelligence,
            "knowledge": ability.knowledge, "dexterity": ability.dexterity,
        }
        return stat_map.get(stat_name, 0)

    def modify_stat(self, stat_name: str, amount: int) -> None:
        """Modify a player stat by amount (can be negative)."""
        combat = self.player.combat_stats
        ability = self.player.ability_stats

        if stat_name == "sp":
            combat.sp = max(0, min(combat.sp_max, combat.sp + amount))
        elif stat_name == "hp":
            combat.hp = max(0, min(combat.hp_max, combat.hp + amount))
        elif stat_name == "mp":
            combat.mp = max(0, min(combat.mp_max, combat.mp + amount))
        elif stat_name == "pt":
            combat.pt = max(0, min(combat.pt_max, combat.pt + amount))
        elif stat_name == "sanity":
            ability.sanity = max(0, min(100, ability.sanity + amount))
        elif stat_name == "strength":
            ability.strength = max(0, min(100, ability.strength + amount))


class PluginManager:
    """Manages loading and executing plugins."""

    def __init__(self):
        self.action_plugins: dict[str, ActionPlugin] = {}
        self.condition_plugins: dict[str, ConditionPlugin] = {}
        self._loaded_modules: list[str] = []

    def load_plugins_from_directory(self, plugins_path: Path) -> None:
        """Load all plugins from a directory."""
        if not plugins_path.exists():
            return

        # Add plugins directory to path
        plugins_str = str(plugins_path)
        if plugins_str not in sys.path:
            sys.path.insert(0, plugins_str)

        # Load each Python file
        for py_file in plugins_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            self._load_plugin_module(py_file, module_name)

    def _load_plugin_module(self, file_path: Path, module_name: str) -> None:
        """Load a single plugin module."""
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find and register plugin classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if isinstance(attr, type):
                    if issubclass(attr, ActionPlugin) and attr is not ActionPlugin:
                        if hasattr(attr, 'action_type') and attr.action_type:
                            instance = attr()
                            self.register_action_plugin(instance)

                    elif issubclass(attr, ConditionPlugin) and attr is not ConditionPlugin:
                        if hasattr(attr, 'condition_type') and attr.condition_type:
                            instance = attr()
                            self.register_condition_plugin(instance)

            self._loaded_modules.append(module_name)

        except Exception as e:
            print(f"Error loading plugin {module_name}: {e}")

    def register_action_plugin(self, plugin: ActionPlugin) -> None:
        """Register an action plugin."""
        self.action_plugins[plugin.action_type] = plugin

    def register_condition_plugin(self, plugin: ConditionPlugin) -> None:
        """Register a condition plugin."""
        self.condition_plugins[plugin.condition_type] = plugin

    def execute_action(self, action_type: str, context: PluginContext,
                       params: dict) -> ActionResult | None:
        """Execute a custom action if plugin exists."""
        plugin = self.action_plugins.get(action_type)
        if plugin:
            return plugin.execute(context, params)
        return None

    def evaluate_condition(self, condition_type: str, context: PluginContext,
                           params: dict) -> bool | None:
        """Evaluate a custom condition if plugin exists."""
        plugin = self.condition_plugins.get(condition_type)
        if plugin:
            return plugin.evaluate(context, params)
        return None

    def get_loaded_plugins(self) -> dict[str, list[str]]:
        """Get list of loaded plugins."""
        return {
            "actions": list(self.action_plugins.keys()),
            "conditions": list(self.condition_plugins.keys()),
            "modules": self._loaded_modules
        }
