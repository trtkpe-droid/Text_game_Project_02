"""
Core game engine that ties all systems together.
"""

from pathlib import Path
from typing import Callable, Any
import json

from .models import (
    GameState, Node, Player, CombatStats, AbilityStats,
    Enemy, BindSequence, Spell, Item, ItemPool, ModInfo, Brand
)
from .yaml_parser import YAMLParser
from .state_machine import StateMachine
from .actions import ActionSystem, ActionResult, Action
from .battle import BattleSystem, BattleAction
from .bind_sequence import BindSequenceSystem, BindChoice
from .plugins import PluginManager, PluginContext


class GameEngine:
    """Main game engine class."""

    def __init__(self):
        self.game_state = GameState()
        self.nodes: dict[str, Node] = {}
        self.enemies: dict[str, Enemy] = {}
        self.bind_sequences: dict[str, BindSequence] = {}
        self.spells: dict[str, Spell] = {}
        self.items: dict[str, Item] = {}
        self.item_pools: dict[str, ItemPool] = {}
        self.mod_info: ModInfo | None = None

        self.state_machine: StateMachine | None = None
        self.action_system: ActionSystem | None = None
        self.battle_system: BattleSystem | None = None
        self.bind_system: BindSequenceSystem | None = None
        self.plugin_manager = PluginManager()

        self._message_callback: Callable[[list[str]], None] | None = None
        self._mod_path: Path | None = None

    def set_message_callback(self, callback: Callable[[list[str]], None]) -> None:
        """Set callback for displaying messages."""
        self._message_callback = callback

    def _emit_messages(self, messages: list[str]) -> None:
        """Emit messages through callback."""
        if self._message_callback:
            self._message_callback(messages)

    def load_mod(self, mod_path: str | Path) -> bool:
        """Load a MOD from the specified path."""
        self._mod_path = Path(mod_path)

        if not self._mod_path.exists():
            self._emit_messages([f"MODパス '{mod_path}' が見つかりません。"])
            return False

        # Parse YAML data
        parser = YAMLParser(self._mod_path)
        parser.load_mod()

        # Transfer data
        self.nodes = parser.nodes
        self.enemies = parser.enemies
        self.bind_sequences = parser.bind_sequences
        self.spells = parser.spells
        self.items = parser.items
        self.item_pools = parser.item_pools
        self.mod_info = parser.mod_info

        # Initialize systems
        self._init_systems()

        # Load plugins
        plugins_path = self._mod_path / "plugins"
        self.plugin_manager.load_plugins_from_directory(plugins_path)

        return True

    def _init_systems(self) -> None:
        """Initialize game systems."""
        self.state_machine = StateMachine(self.game_state)
        self.action_system = ActionSystem(
            self.game_state, self.nodes, self.item_pools, self.items
        )
        self.battle_system = BattleSystem(
            self.game_state, self.spells,
            items=self.items,
            status_effects={},  # TODO: Load from YAML
            spell_pools=self.item_pools  # Reuse item pools for spell pools
        )
        self.bind_system = BindSequenceSystem(self.game_state, self.bind_sequences)

        # Set up callbacks
        self.battle_system.set_battle_end_callback(self._on_battle_end)
        self.bind_system.set_sequence_end_callback(self._on_bind_end)

        # Register plugin handlers with action system
        self._register_plugin_handlers()

    def _register_plugin_handlers(self) -> None:
        """Register plugin action handlers."""
        def create_handler(action_type: str):
            def handler(effect, result, system):
                context = PluginContext(
                    self.game_state, self.nodes, self.enemies,
                    self.items, self.navigate_to
                )
                params = {"target": effect.target, "value": effect.value}
                plugin_result = self.plugin_manager.execute_action(
                    action_type, context, params
                )
                if plugin_result:
                    result.messages.extend(plugin_result.messages)
            return handler

        for action_type in self.plugin_manager.action_plugins:
            self.action_system.register_handler(
                action_type, create_handler(action_type)
            )

    def new_game(self) -> None:
        """Start a new game."""
        # Reset game state
        self.game_state = GameState()
        self._init_systems()

        # Initialize player
        self.game_state.player = Player(
            combat_stats=CombatStats(),
            ability_stats=AbilityStats()
        )

        # Set starting node
        if self.mod_info:
            self.game_state.current_node = self.mod_info.entry_point
        elif self.nodes:
            self.game_state.current_node = next(iter(self.nodes.keys()))

        # Show initial location
        self._show_current_location()

    def _show_current_location(self) -> None:
        """Show the current location description and actions."""
        node = self.nodes.get(self.game_state.current_node)
        if not node:
            self._emit_messages(["現在地が見つかりません。"])
            return

        messages = []

        # Location name
        messages.append(f"【{node.metadata.display_name}】")

        # Check for state triggers
        if self.state_machine:
            new_state = self.state_machine.check_triggers(node)
            if new_state and new_state != node.current_state:
                self.state_machine.transition_node_state(node, new_state)

        # State description
        current_state = node.states.get(node.current_state)
        if current_state:
            messages.append(current_state.description)

        # Object descriptions
        for obj_id, obj in node.objects.items():
            obj_state = obj.state_machine.get(obj.current_state)
            if obj_state and obj_state.description:
                messages.append(obj_state.description)

        self._emit_messages(messages)

        # Mark as visited
        self.game_state.visited_nodes.add(self.game_state.current_node)

    def get_available_actions(self) -> list[dict]:
        """Get all available actions in the current context."""
        # In bind sequence (takes priority over battle)
        if self.game_state.in_bind_sequence and self.bind_system:
            return self.bind_system.get_available_choices()

        # In battle
        if self.game_state.in_battle and self.battle_system:
            return self.battle_system.get_player_actions()

        # Normal exploration
        node = self.nodes.get(self.game_state.current_node)
        if not node:
            return []

        actions = []

        # Node actions
        if self.action_system:
            node_actions = self.action_system.get_available_actions(node)
            for i, action in enumerate(node_actions):
                actions.append({
                    "index": i,
                    "type": "node_action",
                    "action": action,
                    "label": action.label
                })

        # Object actions
        for obj_id, obj in node.objects.items():
            if self.action_system:
                obj_actions = self.action_system.get_object_actions(obj)
                for action in obj_actions:
                    actions.append({
                        "type": "object_action",
                        "object_id": obj_id,
                        "action": action,
                        "label": f"[{obj_id}] {action.label}"
                    })

        return actions

    def execute_action(self, action_index: int) -> None:
        """Execute an action by index."""
        actions = self.get_available_actions()

        if action_index < 0 or action_index >= len(actions):
            self._emit_messages(["無効な選択です。"])
            return

        action_data = actions[action_index]

        # Handle different contexts
        if self.game_state.in_battle:
            self._execute_battle_action(action_data)
        elif self.game_state.in_bind_sequence:
            self._execute_bind_action(action_data)
        else:
            self._execute_exploration_action(action_data)

    def _execute_exploration_action(self, action_data: dict) -> None:
        """Execute an exploration action."""
        action = action_data.get("action")
        if not action or not self.action_system:
            return

        result = self.action_system.execute_action(action)

        # Emit messages
        self._emit_messages(result.messages)

        # Handle special results
        if result.navigation_target:
            self.navigate_to(result.navigation_target)

        if result.battle_start:
            enemy_id = result.battle_start.get("enemy")
            if enemy_id and enemy_id in self.enemies:
                self._start_battle(enemy_id)

        if result.bind_sequence_start:
            self._start_bind_sequence(result.bind_sequence_start)

        if result.game_over:
            self._emit_messages(["", "=== GAME OVER ==="])

        if result.game_clear:
            self._emit_messages(["", "=== GAME CLEAR ==="])

    def _execute_battle_action(self, action_data: dict) -> None:
        """Execute a battle action."""
        if not self.battle_system:
            return

        action_type = action_data.get("type")
        spell_id = action_data.get("spell_id")
        item_id = action_data.get("item_id")

        messages = self.battle_system.execute_player_action(action_type, spell_id, item_id)
        self._emit_messages(messages)

        # Check for bind sequence trigger during battle
        if self.game_state.in_bind_sequence:
            seq_id = self.game_state.current_bind_sequence
            if seq_id and self.bind_system:
                bind_messages = self.bind_system.start_sequence(seq_id)
                self._emit_messages(bind_messages)

    def _execute_bind_action(self, action_data: dict) -> None:
        """Execute a bind sequence action."""
        if not self.bind_system:
            return

        choice_type = action_data.get("type")
        action_id = action_data.get("action_id")

        if choice_type == "custom":
            messages = self.bind_system.execute_choice("custom", action_id)
        else:
            messages = self.bind_system.execute_choice(choice_type)

        self._emit_messages(messages)

        # Check if sequence ended and we should return to battle
        if not self.game_state.in_bind_sequence and self.game_state.in_battle:
            self._emit_messages(["", "戦闘を再開する。"])

    def navigate_to(self, node_id: str) -> None:
        """Navigate to a different node."""
        if node_id not in self.nodes:
            self._emit_messages([f"移動先 '{node_id}' が見つかりません。"])
            return

        self.game_state.current_node = node_id
        self._emit_messages([""])
        self._show_current_location()

    def _start_battle(self, enemy_id: str) -> None:
        """Start a battle with an enemy."""
        enemy = self.enemies.get(enemy_id)
        if not enemy or not self.battle_system:
            return

        messages = self.battle_system.start_battle(enemy)
        self._emit_messages(messages)

    def _start_bind_sequence(self, sequence_id: str) -> None:
        """Start a bind sequence."""
        if not self.bind_system:
            return

        messages = self.bind_system.start_sequence(sequence_id)
        self._emit_messages(messages)

    def _on_battle_end(self, player_won: bool, escaped: bool = False) -> None:
        """Handle battle end."""
        # Note: current_enemy is cleared in battle system, so we get it from battle_state
        enemy = None
        if self.battle_system and self.battle_system.battle_state:
            enemy = self.battle_system.battle_state.enemy

        if player_won:
            # Check for victory event
            if enemy and enemy.events.get("on_victory"):
                self.navigate_to(enemy.events["on_victory"])
        elif not escaped:
            # Check for defeat event
            if enemy and enemy.events.get("on_defeat"):
                self.navigate_to(enemy.events["on_defeat"])

    def _on_bind_end(self, escaped: bool) -> None:
        """Handle bind sequence end."""
        if not escaped:
            # Player failed to escape
            self._emit_messages(["拘束から逃れられなかった……"])

    def get_player_status(self) -> dict:
        """Get current player status."""
        player = self.game_state.player
        combat = player.combat_stats
        ability = player.ability_stats

        return {
            "combat": {
                "SP": f"{combat.sp}/{combat.sp_max}",
                "HP": f"{combat.hp}/{combat.hp_max}",
                "MP": f"{combat.mp}/{combat.mp_max}",
                "PT": f"{combat.pt}/{combat.pt_max}",
            },
            "abilities": {
                "strength": ability.strength,
                "sanity": ability.sanity,
                "focus": ability.focus,
                "intelligence": ability.intelligence,
                "knowledge": ability.knowledge,
                "dexterity": ability.dexterity,
            },
            "inventory": dict(player.inventory),
            "flags": dict(player.flags),
        }

    def save_game(self, save_path: str | Path) -> bool:
        """Save the current game state."""
        save_data = {
            "current_node": self.game_state.current_node,
            "visited_nodes": list(self.game_state.visited_nodes),
            "player": {
                "combat_stats": {
                    "sp": self.game_state.player.combat_stats.sp,
                    "sp_max": self.game_state.player.combat_stats.sp_max,
                    "hp": self.game_state.player.combat_stats.hp,
                    "hp_max": self.game_state.player.combat_stats.hp_max,
                    "mp": self.game_state.player.combat_stats.mp,
                    "mp_max": self.game_state.player.combat_stats.mp_max,
                    "pt": self.game_state.player.combat_stats.pt,
                    "pt_max": self.game_state.player.combat_stats.pt_max,
                },
                "ability_stats": {
                    "sanity": self.game_state.player.ability_stats.sanity,
                    "strength": self.game_state.player.ability_stats.strength,
                    "focus": self.game_state.player.ability_stats.focus,
                    "intelligence": self.game_state.player.ability_stats.intelligence,
                    "knowledge": self.game_state.player.ability_stats.knowledge,
                    "dexterity": self.game_state.player.ability_stats.dexterity,
                },
                "inventory": self.game_state.player.inventory,
                "flags": self.game_state.player.flags,
                "spells": self.game_state.player.spells,
                "brands": [
                    {
                        "enemy_id": b.enemy_id,
                        "enemy_name": b.enemy_name,
                        "debuff_ratio": b.debuff_ratio
                    }
                    for b in self.game_state.player.brands
                ],
            },
            "node_states": {
                node_id: node.current_state
                for node_id, node in self.nodes.items()
            },
            "object_states": {
                node_id: {
                    obj_id: obj.current_state
                    for obj_id, obj in node.objects.items()
                }
                for node_id, node in self.nodes.items()
            }
        }

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self._emit_messages([f"セーブに失敗: {e}"])
            return False

    def load_game(self, save_path: str | Path) -> bool:
        """Load a saved game state."""
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                save_data = json.load(f)

            # Restore game state
            self.game_state.current_node = save_data["current_node"]
            self.game_state.visited_nodes = set(save_data["visited_nodes"])

            # Restore player
            player_data = save_data["player"]
            combat = player_data["combat_stats"]
            ability = player_data["ability_stats"]

            self.game_state.player.combat_stats = CombatStats(
                sp=combat["sp"], sp_max=combat["sp_max"],
                hp=combat["hp"], hp_max=combat["hp_max"],
                mp=combat["mp"], mp_max=combat["mp_max"],
                pt=combat["pt"], pt_max=combat["pt_max"],
            )
            self.game_state.player.ability_stats = AbilityStats(
                sanity=ability["sanity"],
                strength=ability["strength"],
                focus=ability["focus"],
                intelligence=ability["intelligence"],
                knowledge=ability["knowledge"],
                dexterity=ability["dexterity"],
            )
            self.game_state.player.inventory = player_data["inventory"]
            self.game_state.player.flags = player_data["flags"]
            self.game_state.player.spells = player_data["spells"]

            # Restore brands
            self.game_state.player.brands = [
                Brand(
                    enemy_id=b["enemy_id"],
                    enemy_name=b.get("enemy_name", ""),
                    debuff_ratio=b.get("debuff_ratio", 0.2)
                )
                for b in player_data.get("brands", [])
            ]

            # Restore node states
            for node_id, state in save_data["node_states"].items():
                if node_id in self.nodes:
                    self.nodes[node_id].current_state = state

            # Restore object states
            for node_id, objects in save_data["object_states"].items():
                if node_id in self.nodes:
                    for obj_id, state in objects.items():
                        if obj_id in self.nodes[node_id].objects:
                            self.nodes[node_id].objects[obj_id].current_state = state

            # Re-initialize systems with restored state
            self._init_systems()

            # Show current location
            self._show_current_location()

            return True

        except Exception as e:
            self._emit_messages([f"ロードに失敗: {e}"])
            return False

    def is_game_over(self) -> bool:
        """Check if the game is over."""
        return self.game_state.game_over

    def is_game_clear(self) -> bool:
        """Check if the game is cleared."""
        return self.game_state.game_clear
