"""
YAML parser for loading game data.
"""

import yaml
from pathlib import Path
from typing import Any

from .models import (
    Node, NodeState, NodeMetadata, Action, Requirement, Effect,
    InteractiveObject, Enemy, EnemyStats, EnemyRewards, EnemyText,
    BehaviorNode, BindSequence, BindSequenceMetadata, BindSequenceConfig,
    BindStage, CustomAction, SuccessCheck, DefaultChoiceOverride,
    Spell, SpellEffect, SpellText, StatusEffect, Item, ItemPool,
    WeightedOption, Player, CombatStats, AbilityStats, ModInfo, ModMetadata
)


class YAMLParser:
    """Parser for loading YAML game data."""

    def __init__(self, mod_path: Path):
        self.mod_path = mod_path
        self.nodes: dict[str, Node] = {}
        self.enemies: dict[str, Enemy] = {}
        self.bind_sequences: dict[str, BindSequence] = {}
        self.spells: dict[str, Spell] = {}
        self.status_effects: dict[str, StatusEffect] = {}
        self.items: dict[str, Item] = {}
        self.item_pools: dict[str, ItemPool] = {}
        self.mod_info: ModInfo | None = None

    def load_mod(self) -> None:
        """Load all data from the MOD."""
        # Load mod.yaml
        mod_yaml_path = self.mod_path / "mod.yaml"
        if mod_yaml_path.exists():
            self.mod_info = self._load_mod_info(mod_yaml_path)

        # Load data directories
        data_path = self.mod_path / "data"
        if data_path.exists():
            self._load_directory(data_path / "nodes", self._parse_node)
            self._load_directory(data_path / "enemies", self._parse_enemy)
            self._load_directory(data_path / "sequences", self._parse_bind_sequence)
            self._load_directory(data_path / "spells", self._parse_spell)
            self._load_directory(data_path / "items", self._parse_item)
            self._load_directory(data_path / "pools", self._parse_pool)

    def _load_directory(self, path: Path, parser_func) -> None:
        """Load all YAML files from a directory."""
        if not path.exists():
            return

        for yaml_file in path.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    parser_func(data)

    def _load_mod_info(self, path: Path) -> ModInfo:
        """Load MOD info from mod.yaml."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        mod_data = data.get("mod", data)
        metadata = ModMetadata(
            name=mod_data.get("metadata", {}).get("name", "Unknown"),
            author=mod_data.get("metadata", {}).get("author", ""),
            description=mod_data.get("metadata", {}).get("description", ""),
            tags=mod_data.get("metadata", {}).get("tags", [])
        )

        return ModInfo(
            id=mod_data.get("id", "unknown"),
            version=mod_data.get("version", "1.0.0"),
            metadata=metadata,
            entry_point=mod_data.get("entry_point", "start"),
            dependencies=mod_data.get("dependencies", {})
        )

    def _parse_requirement(self, req_data: dict) -> Requirement:
        """Parse a requirement from YAML data."""
        return Requirement(
            type=req_data.get("type", ""),
            stat=req_data.get("stat"),
            flag=req_data.get("flag"),
            item=req_data.get("item"),
            operator=req_data.get("operator"),
            value=req_data.get("value"),
            count=req_data.get("count", 1)
        )

    def _parse_effect(self, effect_data: dict) -> Effect:
        """Parse an effect from YAML data."""
        return Effect(
            type=effect_data.get("type", ""),
            target=effect_data.get("target"),
            text=effect_data.get("text"),
            item=effect_data.get("item"),
            count=effect_data.get("count", 1),
            pool=effect_data.get("pool"),
            flag=effect_data.get("flag"),
            value=effect_data.get("value"),
            stat=effect_data.get("stat"),
            operator=effect_data.get("operator"),
            node=effect_data.get("node"),
            new_state=effect_data.get("new_state"),
            object=effect_data.get("object"),
            enemy=effect_data.get("enemy"),
            enemy_pool=effect_data.get("enemy_pool"),
            sequence=effect_data.get("sequence"),
            stage=effect_data.get("stage", 0),
            reason=effect_data.get("reason"),
            ending=effect_data.get("ending"),
            amount=effect_data.get("amount", 1),
            damage=effect_data.get("damage", 0),
            damage_type=effect_data.get("damage_type")
        )

    def _parse_action(self, action_data: dict) -> Action:
        """Parse an action from YAML data."""
        requirements = [
            self._parse_requirement(req)
            for req in action_data.get("requirements", [])
        ]
        effects = [
            self._parse_effect(eff)
            for eff in action_data.get("effects", [])
        ]

        return Action(
            id=action_data.get("id", ""),
            type=action_data.get("type", "interaction"),
            label=action_data.get("label", ""),
            target=action_data.get("target"),
            requirements=requirements,
            effects=effects,
            description=action_data.get("description")
        )

    def _parse_node_state(self, state_data: dict) -> NodeState:
        """Parse a node state from YAML data."""
        actions = [
            self._parse_action(act)
            for act in state_data.get("actions", [])
        ]

        return NodeState(
            description=state_data.get("description", ""),
            actions=actions,
            trigger=state_data.get("trigger")
        )

    def _parse_interactive_object(self, obj_data: dict) -> InteractiveObject:
        """Parse an interactive object from YAML data."""
        state_machine_data = obj_data.get("state_machine", {})
        states = {}
        for state_name, state_data in state_machine_data.get("states", {}).items():
            states[state_name] = self._parse_node_state(state_data)

        return InteractiveObject(
            id=obj_data.get("id", ""),
            type=obj_data.get("type", "interactive_object"),
            state_machine=states,
            initial_state=state_machine_data.get("initial_state", "normal")
        )

    def _parse_node(self, data: dict) -> None:
        """Parse a node from YAML data."""
        node_data = data.get("node", data)

        # Handle multiple nodes in one file
        if "nodes" in data:
            for node_item in data["nodes"]:
                self._parse_single_node(node_item)
        else:
            self._parse_single_node(node_data)

    def _parse_single_node(self, node_data: dict) -> None:
        """Parse a single node."""
        metadata = NodeMetadata(
            display_name=node_data.get("metadata", {}).get("display_name", ""),
            description=node_data.get("metadata", {}).get("description", "")
        )

        state_machine_data = node_data.get("state_machine", {})
        states = {}
        for state_name, state_data in state_machine_data.get("states", {}).items():
            states[state_name] = self._parse_node_state(state_data)

        objects = {}
        for obj_name, obj_data in node_data.get("objects", {}).items():
            objects[obj_name] = self._parse_interactive_object(obj_data)

        node = Node(
            id=node_data.get("id", ""),
            type=node_data.get("type", "location"),
            metadata=metadata,
            states=states,
            initial_state=state_machine_data.get("initial_state", "normal"),
            objects=objects
        )

        self.nodes[node.id] = node

    def _parse_behavior_node(self, behavior_data: dict) -> BehaviorNode:
        """Parse a behavior tree node."""
        children = [
            self._parse_behavior_node(child)
            for child in behavior_data.get("children", [])
        ]

        return BehaviorNode(
            type=behavior_data.get("type", ""),
            name=behavior_data.get("name"),
            conditions=behavior_data.get("conditions", []),
            action=behavior_data.get("action"),
            children=children,
            options=behavior_data.get("options", [])
        )

    def _parse_enemy(self, data: dict) -> None:
        """Parse an enemy from YAML data."""
        enemy_data = data.get("enemy", data)

        # Handle multiple enemies in one file
        if "enemies" in data:
            for enemy_item in data["enemies"]:
                self._parse_single_enemy(enemy_item)
        else:
            self._parse_single_enemy(enemy_data)

    def _parse_single_enemy(self, enemy_data: dict) -> None:
        """Parse a single enemy."""
        stats_data = enemy_data.get("stats", {})
        stats = EnemyStats(
            hp=stats_data.get("hp", 100),
            atk=stats_data.get("atk", 20),
            defense=stats_data.get("def", 10),
            matk=stats_data.get("matk", 15),
            initiative=stats_data.get("initiative", 10)
        )

        rewards_data = enemy_data.get("rewards", {})
        rewards = EnemyRewards(
            exp=rewards_data.get("exp", 0),
            drops=rewards_data.get("drops")
        )

        text_data = enemy_data.get("text", {})
        text = EnemyText(
            encounter=text_data.get("encounter", ""),
            defeat=text_data.get("defeat", ""),
            victory=text_data.get("victory", "")
        )

        # Parse attack texts
        attack_texts_data = enemy_data.get("attack_texts", {})
        if isinstance(attack_texts_data, dict):
            attack_texts = attack_texts_data.get("options", [])
        else:
            attack_texts = attack_texts_data

        # Parse behavior tree
        behavior_tree = None
        if "behavior_tree" in enemy_data:
            behavior_tree = self._parse_behavior_node(enemy_data["behavior_tree"])

        enemy = Enemy(
            id=enemy_data.get("id", ""),
            name=enemy_data.get("metadata", {}).get("name", "Unknown"),
            description=enemy_data.get("metadata", {}).get("description", ""),
            stats=stats,
            rewards=rewards,
            text=text,
            attack_texts=attack_texts,
            spells=enemy_data.get("spells", []),
            behavior_tree=behavior_tree,
            events=enemy_data.get("events", {})
        )

        self.enemies[enemy.id] = enemy

    def _parse_success_check(self, check_data: dict) -> SuccessCheck:
        """Parse a success check."""
        return SuccessCheck(
            type=check_data.get("type", "fixed"),
            rate=check_data.get("rate", 50),
            base_rate=check_data.get("base_rate", 0),
            formula=check_data.get("formula"),
            expression=check_data.get("expression"),
            modifiers=check_data.get("modifiers", [])
        )

    def _parse_custom_action(self, action_data: dict) -> CustomAction:
        """Parse a custom action."""
        requirements = [
            self._parse_requirement(req)
            for req in action_data.get("requirements", [])
        ]

        success_check = None
        if "success_check" in action_data:
            success_check = self._parse_success_check(action_data["success_check"])

        return CustomAction(
            id=action_data.get("id", ""),
            label=action_data.get("label", ""),
            description=action_data.get("description", ""),
            requirements=requirements,
            cost=action_data.get("cost", {}),
            success_check=success_check,
            on_success=action_data.get("on_success"),
            on_failure=action_data.get("on_failure")
        )

    def _parse_default_choice_override(self, override_data: dict) -> DefaultChoiceOverride:
        """Parse a default choice override."""
        return DefaultChoiceOverride(
            enabled=override_data.get("enabled", True),
            override_result=override_data.get("override_result"),
            success_rate_modifier=override_data.get("success_rate_modifier", 0),
            reason=override_data.get("reason")
        )

    def _parse_bind_stage(self, stage_data: dict) -> BindStage:
        """Parse a bind sequence stage."""
        # Parse default choice overrides
        overrides = {}
        for key, override_data in stage_data.get("default_choices_override", {}).items():
            overrides[key] = self._parse_default_choice_override(override_data)

        # Parse custom actions
        custom_actions = [
            self._parse_custom_action(ca)
            for ca in stage_data.get("custom_actions", [])
        ]

        # Parse loop effects
        loop_effects = [
            self._parse_effect(eff)
            for eff in stage_data.get("loop_effects", [])
        ]

        return BindStage(
            stage=stage_data.get("stage", 0),
            description=stage_data.get("description", ""),
            player_texts=stage_data.get("player_texts", {}),
            enemy_reactions=stage_data.get("enemy_reactions", {}),
            default_choices_override=overrides,
            custom_actions=custom_actions,
            loop_effects=loop_effects
        )

    def _parse_bind_sequence(self, data: dict) -> None:
        """Parse a bind sequence from YAML data."""
        seq_data = data.get("bind_sequence", data)

        # Handle multiple sequences in one file
        if "bind_sequences" in data:
            for seq_item in data["bind_sequences"]:
                self._parse_single_bind_sequence(seq_item)
        else:
            self._parse_single_bind_sequence(seq_data)

    def _parse_single_bind_sequence(self, seq_data: dict) -> None:
        """Parse a single bind sequence."""
        metadata = BindSequenceMetadata(
            name=seq_data.get("metadata", {}).get("name", ""),
            description=seq_data.get("metadata", {}).get("description", "")
        )

        config_data = seq_data.get("config", {})
        config = BindSequenceConfig(
            base_difficulty=config_data.get("base_difficulty", 50),
            escape_target=config_data.get("escape_target", "battle_resume"),
            loop_damage=config_data.get("loop_damage", {})
        )

        stages = [
            self._parse_bind_stage(stage)
            for stage in seq_data.get("stages", [])
        ]

        sequence = BindSequence(
            id=seq_data.get("id", ""),
            metadata=metadata,
            config=config,
            stages=stages
        )

        self.bind_sequences[sequence.id] = sequence

    def _parse_spell_effect(self, effect_data: dict) -> SpellEffect:
        """Parse a spell effect."""
        return SpellEffect(
            type=effect_data.get("type", ""),
            damage_type=effect_data.get("damage_type"),
            element=effect_data.get("element"),
            base=effect_data.get("base", 0),
            scaling=effect_data.get("scaling"),
            status=effect_data.get("status"),
            duration=effect_data.get("duration", 0),
            chance=effect_data.get("chance", 100)
        )

    def _parse_spell(self, data: dict) -> None:
        """Parse a spell from YAML data."""
        spell_data = data.get("spell", data)

        # Handle multiple spells in one file
        if "spells" in data:
            for spell_item in data["spells"]:
                self._parse_single_spell(spell_item)
        else:
            self._parse_single_spell(spell_data)

    def _parse_single_spell(self, spell_data: dict) -> None:
        """Parse a single spell."""
        effects = [
            self._parse_spell_effect(eff)
            for eff in spell_data.get("effects", [])
        ]

        text_data = spell_data.get("text", {})
        text = SpellText(
            cast=text_data.get("cast", ""),
            hit=text_data.get("hit", ""),
            miss=text_data.get("miss", ""),
            success=text_data.get("success", ""),
            resist=text_data.get("resist", "")
        )

        spell = Spell(
            id=spell_data.get("id", ""),
            name=spell_data.get("metadata", {}).get("name", ""),
            description=spell_data.get("metadata", {}).get("description", ""),
            cost=spell_data.get("cost", {}),
            effects=effects,
            text=text
        )

        self.spells[spell.id] = spell

    def _parse_item(self, data: dict) -> None:
        """Parse an item from YAML data."""
        item_data = data.get("item", data)

        # Handle multiple items in one file
        if "items" in data:
            for item_item in data["items"]:
                self._parse_single_item(item_item)
        else:
            self._parse_single_item(item_data)

    def _parse_single_item(self, item_data: dict) -> None:
        """Parse a single item."""
        effects = [
            self._parse_effect(eff)
            for eff in item_data.get("effects", [])
        ]

        item = Item(
            id=item_data.get("id", ""),
            name=item_data.get("name", ""),
            description=item_data.get("description", ""),
            type=item_data.get("type", "consumable"),
            effects=effects,
            value=item_data.get("value", 0)
        )

        self.items[item.id] = item

    def _parse_pool(self, data: dict) -> None:
        """Parse item pools from YAML data."""
        pools_data = data.get("item_pools", data)

        for pool_id, pool_data in pools_data.items():
            if isinstance(pool_data, dict) and "options" in pool_data:
                options = [
                    WeightedOption(
                        weight=opt.get("weight", 1),
                        value=opt.get("value")
                    )
                    for opt in pool_data.get("options", [])
                ]

                pool = ItemPool(id=pool_id, options=options)
                self.item_pools[pool_id] = pool


def load_yaml_file(path: str | Path) -> dict:
    """Load a single YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
