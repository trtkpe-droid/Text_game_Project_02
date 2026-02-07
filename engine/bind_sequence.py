"""
Bind sequence system for restraint events.
Implements staged struggle mechanics with custom actions.
"""

import random
import re
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .models import (
    GameState, BindSequence, BindStage, CustomAction,
    SuccessCheck, DefaultChoiceOverride, Effect, Player,
    normalize_stat_name
)


class BindChoice(Enum):
    """Default bind sequence choices."""
    RESIST = "resist"
    RESIST_HARD = "resist_hard"
    WAIT = "wait"


@dataclass
class BindSequenceState:
    """Current state of a bind sequence."""
    sequence: BindSequence
    current_stage: int = 0
    turn: int = 1
    next_turn_bonus: int = 0
    messages: list[str] = field(default_factory=list)
    escaped: bool = False
    failed: bool = False


class BindSequenceSystem:
    """Handles bind sequence (restraint) mechanics."""

    def __init__(self, game_state: GameState,
                 sequences: dict[str, BindSequence]):
        self.game_state = game_state
        self.sequences = sequences
        self.bind_state: BindSequenceState | None = None
        self._on_sequence_end: Callable | None = None

    def set_sequence_end_callback(self, callback: Callable) -> None:
        """Set callback for when sequence ends."""
        self._on_sequence_end = callback

    def start_sequence(self, sequence_id: str, start_stage: int = 0) -> list[str]:
        """Start a bind sequence."""
        sequence = self.sequences.get(sequence_id)
        if not sequence:
            return [f"シーケンス '{sequence_id}' が見つかりません。"]

        self.bind_state = BindSequenceState(
            sequence=sequence,
            current_stage=start_stage
        )
        self.game_state.in_bind_sequence = True
        self.game_state.current_bind_sequence = sequence_id
        self.game_state.current_bind_stage = start_stage

        messages = [f"【{sequence.metadata.name}】"]

        # Show current stage description
        stage = self._get_current_stage()
        if stage:
            messages.append(stage.description)

        return messages

    def get_available_choices(self) -> list[dict]:
        """Get available choices for the current stage."""
        if not self.bind_state:
            return []

        stage = self._get_current_stage()
        if not stage:
            return []

        choices = []

        # Default choices (may be overridden)
        overrides = stage.default_choices_override

        # Resist
        resist_override = overrides.get("resist", DefaultChoiceOverride())
        if resist_override.enabled:
            choices.append({
                "type": BindChoice.RESIST,
                "label": "抵抗する",
                "description": "成功率高、1段階改善"
            })

        # Resist hard
        resist_hard_override = overrides.get("resist_hard", DefaultChoiceOverride())
        if resist_hard_override.enabled:
            choices.append({
                "type": BindChoice.RESIST_HARD,
                "label": "全力で抵抗する",
                "description": "成功率低、成功で即脱出、失敗でPT大幅上昇"
            })

        # Wait
        wait_override = overrides.get("wait", DefaultChoiceOverride())
        if wait_override.enabled:
            choices.append({
                "type": BindChoice.WAIT,
                "label": "抵抗しない",
                "description": "判定なしで1段階進行、次ターンボーナス"
            })

        # Custom actions
        for custom_action in stage.custom_actions:
            if self._check_custom_action_requirements(custom_action):
                choices.append({
                    "type": "custom",
                    "action_id": custom_action.id,
                    "label": custom_action.label,
                    "description": custom_action.description
                })

        return choices

    def execute_choice(self, choice_type: BindChoice | str,
                       action_id: str | None = None) -> list[str]:
        """Execute a player choice and return messages."""
        if not self.bind_state:
            return ["拘束シーケンスが開始されていません。"]

        stage = self._get_current_stage()
        if not stage:
            return ["現在のステージが見つかりません。"]

        messages = []

        if choice_type == BindChoice.RESIST:
            messages.extend(self._execute_resist(stage))
        elif choice_type == BindChoice.RESIST_HARD:
            messages.extend(self._execute_resist_hard(stage))
        elif choice_type == BindChoice.WAIT:
            messages.extend(self._execute_wait(stage))
        elif choice_type == "custom" and action_id:
            messages.extend(self._execute_custom_action(stage, action_id))

        # Check for escape (stage < 0)
        if self.bind_state.current_stage < 0:
            messages.append("拘束から脱出した！")
            self._end_sequence(escaped=True)
            return messages

        # Check for max stage (loop)
        max_stage = len(self.bind_state.sequence.stages) - 1
        if self.bind_state.current_stage > max_stage:
            self.bind_state.current_stage = max_stage
            # Apply loop effects
            messages.extend(self._apply_loop_effects(stage))

        # Update game state
        self.game_state.current_bind_stage = self.bind_state.current_stage

        # Show next stage description if stage changed
        new_stage = self._get_current_stage()
        if new_stage and new_stage != stage:
            messages.append("")
            messages.append(new_stage.description)

        self.bind_state.turn += 1
        return messages

    def _get_current_stage(self) -> BindStage | None:
        """Get the current bind stage."""
        if not self.bind_state:
            return None

        for stage in self.bind_state.sequence.stages:
            if stage.stage == self.bind_state.current_stage:
                return stage
        return None

    def _calculate_success_rate(self, base_rate: int,
                                modifier: int = 0) -> int:
        """Calculate success rate with modifiers."""
        rate = base_rate + modifier + self.bind_state.next_turn_bonus
        self.bind_state.next_turn_bonus = 0  # Reset bonus
        return max(5, min(95, rate))  # Clamp between 5% and 95%

    def _execute_resist(self, stage: BindStage) -> list[str]:
        """Execute normal resist action."""
        messages = []
        override = stage.default_choices_override.get("resist", DefaultChoiceOverride())

        # Check for auto result
        if override.override_result == "auto_fail":
            messages.append(override.reason or "抵抗できない……！")
            self._progress_stage(1)
            if stage.enemy_reactions.get("on_player_resist_fail"):
                messages.append(stage.enemy_reactions["on_player_resist_fail"])
            return messages

        if override.override_result == "auto_success":
            messages.append("抵抗に成功した！")
            self._regress_stage(1)
            if stage.enemy_reactions.get("on_player_resist_success"):
                messages.append(stage.enemy_reactions["on_player_resist_success"])
            return messages

        # Normal calculation
        base_difficulty = self.bind_state.sequence.config.base_difficulty
        success_rate = self._calculate_success_rate(
            100 - base_difficulty,
            override.success_rate_modifier
        )

        if random.randint(1, 100) <= success_rate:
            # Success
            text = self._get_player_text(stage, "on_resist_success", "抵抗に成功した！")
            messages.append(text)
            self._regress_stage(1)
            if stage.enemy_reactions.get("on_player_resist_success"):
                messages.append(stage.enemy_reactions["on_player_resist_success"])
        else:
            # Failure
            text = self._get_player_text(stage, "on_resist_fail", "抵抗に失敗した……")
            messages.append(text)
            self._progress_stage(1)
            self._modify_pt(10)
            if stage.enemy_reactions.get("on_player_resist_fail"):
                messages.append(stage.enemy_reactions["on_player_resist_fail"])

        return messages

    def _execute_resist_hard(self, stage: BindStage) -> list[str]:
        """Execute hard resist action."""
        messages = []
        override = stage.default_choices_override.get("resist_hard", DefaultChoiceOverride())

        # Check for auto result
        if override.override_result == "auto_fail":
            messages.append(override.reason or "全力で抵抗したが、無駄だった……！")
            self._progress_stage(2)
            self._modify_pt(25)
            return messages

        if override.override_result == "auto_success":
            messages.append("渾身の力で拘束を振りほどいた！")
            self.bind_state.current_stage = -1
            return messages

        # Hard resist has lower base success rate but escapes immediately
        base_difficulty = self.bind_state.sequence.config.base_difficulty
        success_rate = self._calculate_success_rate(
            50 - base_difficulty // 2,
            override.success_rate_modifier
        )

        if random.randint(1, 100) <= success_rate:
            # Success - immediate escape
            messages.append("全力で抵抗し、拘束から脱出した！")
            self.bind_state.current_stage = -1
            if stage.enemy_reactions.get("on_player_resist_success"):
                messages.append(stage.enemy_reactions["on_player_resist_success"])
        else:
            # Failure - progress and PT increase
            messages.append("全力で抵抗したが、失敗した……！")
            self._progress_stage(1)
            self._modify_pt(25)
            if stage.enemy_reactions.get("on_player_resist_fail"):
                messages.append(stage.enemy_reactions["on_player_resist_fail"])

        return messages

    def _execute_wait(self, stage: BindStage) -> list[str]:
        """Execute wait (no resist) action."""
        messages = []
        override = stage.default_choices_override.get("wait", DefaultChoiceOverride())

        if override.override_result == "auto_fail":
            messages.append(override.reason or "抵抗を諦めるわけにはいかない……！")
            return messages

        text = self._get_player_text(stage, "on_wait", "抵抗せずに力を溜める……")
        messages.append(text)

        # Progress stage but gain bonus for next turn
        self._progress_stage(1)
        self.bind_state.next_turn_bonus = 20

        if stage.enemy_reactions.get("on_player_wait"):
            messages.append(stage.enemy_reactions["on_player_wait"])

        return messages

    def _execute_custom_action(self, stage: BindStage, action_id: str) -> list[str]:
        """Execute a custom action."""
        messages = []

        # Find the custom action
        custom_action = None
        for ca in stage.custom_actions:
            if ca.id == action_id:
                custom_action = ca
                break

        if not custom_action:
            return ["アクションが見つかりません。"]

        # Check and apply cost
        if not self._apply_cost(custom_action.cost):
            return ["コストが足りません。"]

        # Calculate success
        success = self._check_custom_success(custom_action.success_check)

        if success:
            # Execute success effects
            if custom_action.on_success:
                effects = custom_action.on_success.get("effects", [])
                messages.extend(self._apply_effects(effects))
                enemy_reaction = custom_action.on_success.get("enemy_reaction")
                if enemy_reaction:
                    messages.append(enemy_reaction)
        else:
            # Execute failure effects
            if custom_action.on_failure:
                effects = custom_action.on_failure.get("effects", [])
                messages.extend(self._apply_effects(effects))
                enemy_reaction = custom_action.on_failure.get("enemy_reaction")
                if enemy_reaction:
                    messages.append(enemy_reaction)

        return messages

    def _check_custom_action_requirements(self, action: CustomAction) -> bool:
        """Check if custom action requirements are met."""
        player = self.game_state.player

        for req in action.requirements:
            if req.type == "stat_check":
                actual = self._get_stat_value(req.stat)
                if not self._compare(actual, req.operator, req.value):
                    return False
            elif req.type == "item_check":
                count = player.inventory.get(req.item, 0)
                if count < req.count:
                    return False
            elif req.type == "flag_check":
                if player.flags.get(req.flag) != req.value:
                    return False

        # Check cost
        for stat, cost in action.cost.items():
            if stat == "mp" and player.combat_stats.mp < cost:
                return False
            elif stat == "hp" and player.combat_stats.hp < cost:
                return False

        return True

    def _check_custom_success(self, check: SuccessCheck | None) -> bool:
        """Check if a custom action succeeds."""
        if not check:
            return True

        if check.type == "fixed":
            return random.randint(1, 100) <= check.rate

        elif check.type == "stat_based":
            rate = check.base_rate
            if check.formula:
                rate += self._evaluate_formula(check.formula)

            # Apply modifiers
            for modifier in check.modifiers:
                mod_type = modifier.get("type")
                if mod_type == "flag_bonus":
                    flag = modifier.get("flag")
                    if self.game_state.player.flags.get(flag):
                        rate += modifier.get("bonus", 0)
                elif mod_type == "item_bonus":
                    item = modifier.get("item")
                    if self.game_state.player.inventory.get(item, 0) > 0:
                        rate += modifier.get("bonus", 0)
                elif mod_type == "status_penalty":
                    status = modifier.get("status")
                    for effect in self.game_state.player.status_effects:
                        if effect.get("id") == status:
                            rate += modifier.get("penalty", 0)
                            break

            rate = max(5, min(95, rate))
            return random.randint(1, 100) <= rate

        elif check.type == "formula":
            if check.expression:
                rate = self._evaluate_formula(check.expression)
                rate = max(5, min(95, rate))
                return random.randint(1, 100) <= rate

        return True

    def _evaluate_formula(self, formula: str) -> int:
        """Evaluate a stat-based formula. Supports Japanese stat names."""
        player = self.game_state.player

        # Replace stat names with values (both Japanese and English)
        stat_map = {
            # Japanese names
            "正気": player.ability_stats.sanity,
            "筋力": player.ability_stats.strength,
            "集中": player.ability_stats.focus,
            "知性": player.ability_stats.intelligence,
            "知識": player.ability_stats.knowledge,
            "器用": player.ability_stats.dexterity,
            # English names
            "sanity": player.ability_stats.sanity,
            "strength": player.ability_stats.strength,
            "focus": player.ability_stats.focus,
            "intelligence": player.ability_stats.intelligence,
            "knowledge": player.ability_stats.knowledge,
            "dexterity": player.ability_stats.dexterity,
        }

        result = formula
        for stat_name, value in stat_map.items():
            result = result.replace(stat_name, str(value))

        try:
            # Safely evaluate the expression
            return int(eval(result, {"__builtins__": {}}, {"min": min, "max": max}))
        except Exception:
            return 50

    def _apply_cost(self, cost: dict[str, int]) -> bool:
        """Apply action cost. Returns False if insufficient resources."""
        player = self.game_state.player

        for stat, amount in cost.items():
            if stat == "mp":
                if player.combat_stats.mp < amount:
                    return False
                player.combat_stats.mp -= amount
            elif stat == "hp":
                if player.combat_stats.hp < amount:
                    return False
                player.combat_stats.hp -= amount
            elif stat == "item":
                if player.inventory.get(amount, 0) < 1:
                    return False
                player.inventory[amount] -= 1

        return True

    def _apply_effects(self, effects: list[dict]) -> list[str]:
        """Apply a list of effects and return messages."""
        messages = []

        for effect_data in effects:
            effect_type = effect_data.get("type")

            if effect_type == "message":
                messages.append(effect_data.get("text", ""))

            elif effect_type == "stage_progress":
                amount = effect_data.get("amount", 1)
                self._progress_stage(amount)

            elif effect_type == "stage_regress":
                amount = effect_data.get("amount", 1)
                self._regress_stage(amount)

            elif effect_type == "escape_bind":
                self.bind_state.current_stage = -1

            elif effect_type == "deal_damage":
                target = effect_data.get("target")
                damage = effect_data.get("damage", 0)
                damage_type = effect_data.get("damage_type", "physical")

                if target == "enemy" and self.game_state.current_enemy:
                    self.game_state.current_enemy.current_hp -= damage
                    messages.append(f"敵に{damage}のダメージ！")
                elif target == "self":
                    if damage_type == "pt":
                        self._modify_pt(damage)
                    else:
                        self.game_state.player.combat_stats.hp -= damage
                        messages.append(f"{damage}のダメージを受けた！")

            elif effect_type == "modify_stat":
                stat = effect_data.get("stat")
                operator = effect_data.get("operator", "+")
                value = effect_data.get("value", 0)
                self._modify_stat(stat, operator, value)

            elif effect_type == "set_flag":
                flag = effect_data.get("flag")
                value = effect_data.get("value", True)
                self.game_state.player.flags[flag] = value

            elif effect_type == "switch_bind_sequence":
                target_seq = effect_data.get("target")
                start_stage = effect_data.get("stage", 0)
                # Signal to switch sequence
                self.game_state.current_bind_sequence = target_seq
                self.game_state.current_bind_stage = start_stage
                messages.extend(self.start_sequence(target_seq, start_stage))

        return messages

    def _apply_loop_effects(self, stage: BindStage) -> list[str]:
        """Apply loop effects when staying at max stage."""
        messages = []

        # Apply config loop damage
        loop_damage = self.bind_state.sequence.config.loop_damage
        if "pt" in loop_damage:
            self._modify_pt(loop_damage["pt"])
        if "hp" in loop_damage:
            self.game_state.player.combat_stats.hp -= loop_damage["hp"]

        # Apply stage-specific loop effects
        for effect_data in stage.loop_effects:
            effect_messages = self._apply_effects([{
                "type": effect_data.type,
                "text": effect_data.text,
                "stat": effect_data.stat,
                "operator": effect_data.operator,
                "value": effect_data.value,
                "target": effect_data.target,
                "damage": effect_data.damage,
                "damage_type": effect_data.damage_type
            }])
            messages.extend(effect_messages)

        return messages

    def _progress_stage(self, amount: int) -> None:
        """Progress to a later stage."""
        self.bind_state.current_stage += amount

    def _regress_stage(self, amount: int) -> None:
        """Regress to an earlier stage."""
        self.bind_state.current_stage -= amount

    def _modify_pt(self, amount: int) -> None:
        """Modify player's PT."""
        player = self.game_state.player
        player.combat_stats.pt = min(
            player.combat_stats.pt_max,
            player.combat_stats.pt + amount
        )

    def _modify_stat(self, stat: str, operator: str, value: int) -> None:
        """Modify a player stat."""
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

    def _get_stat_value(self, stat: str) -> int:
        """Get a stat value. Supports Japanese stat names."""
        # Normalize Japanese stat names to English
        stat = normalize_stat_name(stat)

        player = self.game_state.player
        combat = player.combat_stats
        ability = player.ability_stats

        stat_map = {
            "sp": combat.sp, "hp": combat.hp, "mp": combat.mp, "pt": combat.pt,
            "sanity": ability.sanity, "strength": ability.strength,
            "focus": ability.focus, "intelligence": ability.intelligence,
            "knowledge": ability.knowledge, "dexterity": ability.dexterity,
        }
        return stat_map.get(stat, 0)

    def _set_stat_value(self, stat: str, value: int) -> None:
        """Set a stat value."""
        player = self.game_state.player
        combat = player.combat_stats
        ability = player.ability_stats

        if stat == "sp":
            combat.sp = max(0, min(combat.sp_max, value))
        elif stat == "hp":
            combat.hp = max(0, min(combat.hp_max, value))
        elif stat == "mp":
            combat.mp = max(0, min(combat.mp_max, value))
        elif stat == "pt":
            combat.pt = max(0, min(combat.pt_max, value))
        elif stat == "sanity":
            ability.sanity = max(0, min(100, value))
        elif stat == "strength":
            ability.strength = max(0, min(100, value))

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare values."""
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
        }
        return ops.get(operator, lambda a, b: False)(actual, expected)

    def _get_player_text(self, stage: BindStage, key: str, default: str) -> str:
        """Get player text, handling random selection."""
        text_data = stage.player_texts.get(key)

        if not text_data:
            return default

        if isinstance(text_data, str):
            return text_data

        if isinstance(text_data, dict):
            if text_data.get("type") == "random_select":
                options = text_data.get("options", [default])
                return random.choice(options)

        return default

    def _end_sequence(self, escaped: bool = False) -> None:
        """End the bind sequence."""
        if self.bind_state:
            self.bind_state.escaped = escaped
            self.bind_state.failed = not escaped

        self.game_state.in_bind_sequence = False
        self.game_state.current_bind_sequence = None
        self.game_state.current_bind_stage = 0

        if self._on_sequence_end:
            self._on_sequence_end(escaped)

    def is_in_sequence(self) -> bool:
        """Check if currently in a bind sequence."""
        return self.bind_state is not None and self.bind_state.current_stage >= 0
