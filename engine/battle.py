"""
Battle system for the game engine.
Implements turn-based combat with behavior trees for enemy AI.
"""

import random
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .models import (
    GameState, Enemy, Player, BehaviorNode,
    Spell, SpellEffect
)


class BattleAction(Enum):
    """Types of battle actions."""
    ATTACK = "attack"
    DEFEND = "defend"
    SPELL = "spell"
    ITEM = "item"
    ESCAPE = "escape"


@dataclass
class BattleState:
    """State of the current battle."""
    enemy: Enemy
    turn: int = 1
    player_defending: bool = False
    enemy_defending: bool = False
    battle_log: list[str] = field(default_factory=list)
    is_over: bool = False
    player_won: bool = False


class BattleSystem:
    """Handles combat mechanics."""

    def __init__(self, game_state: GameState, spells: dict[str, Spell]):
        self.game_state = game_state
        self.spells = spells
        self.battle_state: BattleState | None = None
        self._on_battle_end: Callable | None = None

    def set_battle_end_callback(self, callback: Callable) -> None:
        """Set callback for when battle ends."""
        self._on_battle_end = callback

    def start_battle(self, enemy: Enemy) -> list[str]:
        """Start a battle with an enemy."""
        # Create a copy of the enemy for this battle
        battle_enemy = Enemy(
            id=enemy.id,
            name=enemy.name,
            description=enemy.description,
            stats=enemy.stats,
            current_hp=enemy.stats.hp,
            rewards=enemy.rewards,
            text=enemy.text,
            attack_texts=enemy.attack_texts,
            spells=enemy.spells,
            behavior_tree=enemy.behavior_tree,
            events=enemy.events,
            cooldowns={}
        )

        self.battle_state = BattleState(enemy=battle_enemy)
        self.game_state.in_battle = True
        self.game_state.current_enemy = battle_enemy

        messages = []
        if battle_enemy.text.encounter:
            messages.append(battle_enemy.text.encounter)
        messages.append(f"戦闘開始！ {battle_enemy.name}が現れた！")

        return messages

    def get_player_actions(self) -> list[dict]:
        """Get available player actions."""
        actions = [
            {"type": BattleAction.ATTACK, "label": "攻撃"},
            {"type": BattleAction.DEFEND, "label": "防御"},
        ]

        # Add available spells
        player = self.game_state.player
        for spell_id in player.spells:
            spell = self.spells.get(spell_id)
            if spell:
                mp_cost = spell.cost.get("mp", 0)
                if player.combat_stats.mp >= mp_cost:
                    actions.append({
                        "type": BattleAction.SPELL,
                        "spell_id": spell_id,
                        "label": f"{spell.name} (MP: {mp_cost})"
                    })

        # Add escape option
        actions.append({"type": BattleAction.ESCAPE, "label": "逃げる"})

        return actions

    def execute_player_action(self, action_type: BattleAction,
                              spell_id: str | None = None,
                              item_id: str | None = None) -> list[str]:
        """Execute a player action and return battle log."""
        if not self.battle_state:
            return ["戦闘が開始されていません。"]

        messages = []
        player = self.game_state.player
        enemy = self.battle_state.enemy

        # Reset defending status
        self.battle_state.player_defending = False

        if action_type == BattleAction.ATTACK:
            messages.extend(self._player_attack())

        elif action_type == BattleAction.DEFEND:
            self.battle_state.player_defending = True
            messages.append("防御態勢をとった！")

        elif action_type == BattleAction.SPELL:
            if spell_id:
                messages.extend(self._cast_spell(spell_id, is_player=True))

        elif action_type == BattleAction.ESCAPE:
            if random.random() < 0.5:
                messages.append("逃げ出した！")
                self._end_battle(player_won=False, escaped=True)
                return messages
            else:
                messages.append("逃げられなかった！")

        # Check if enemy is defeated
        if enemy.current_hp <= 0:
            messages.extend(self._handle_enemy_defeat())
            return messages

        # Enemy turn
        messages.extend(self._enemy_turn())

        # Check if player is defeated
        if player.combat_stats.hp <= 0:
            messages.extend(self._handle_player_defeat())
            return messages

        # Check for PT limit
        if player.combat_stats.pt >= player.combat_stats.pt_max:
            messages.append("快楽に屈した……！")
            messages.extend(self._handle_player_defeat())
            return messages

        self.battle_state.turn += 1
        return messages

    def _player_attack(self) -> list[str]:
        """Execute player's normal attack."""
        player = self.game_state.player
        enemy = self.battle_state.enemy

        # Calculate damage
        base_damage = 20 + player.ability_stats.strength // 5
        defense = enemy.stats.defense
        damage = max(1, base_damage - defense // 2)

        # Apply randomness
        damage = int(damage * random.uniform(0.9, 1.1))

        enemy.current_hp -= damage
        return [f"攻撃！ {enemy.name}に{damage}のダメージ！"]

    def _cast_spell(self, spell_id: str, is_player: bool = True) -> list[str]:
        """Cast a spell."""
        spell = self.spells.get(spell_id)
        if not spell:
            return ["その魔法は使えない。"]

        messages = []
        player = self.game_state.player
        enemy = self.battle_state.enemy

        if is_player:
            caster_name = "あなた"
            target_name = enemy.name
            target = enemy

            # Check and consume MP
            mp_cost = spell.cost.get("mp", 0)
            if player.combat_stats.mp < mp_cost:
                return ["MPが足りない！"]
            player.combat_stats.mp -= mp_cost
        else:
            caster_name = enemy.name
            target_name = "あなた"
            target = player

        # Cast message
        cast_text = spell.text.cast.replace("{{caster}}", caster_name)
        messages.append(cast_text)

        # Apply effects
        for effect in spell.effects:
            effect_messages = self._apply_spell_effect(
                effect, is_player, target, target_name
            )
            messages.extend(effect_messages)

        return messages

    def _apply_spell_effect(self, effect: SpellEffect, is_player: bool,
                            target: Any, target_name: str) -> list[str]:
        """Apply a spell effect."""
        messages = []
        player = self.game_state.player
        enemy = self.battle_state.enemy

        if effect.type == "deal_damage":
            # Calculate damage
            base = effect.base
            if effect.scaling and is_player:
                stat_name = effect.scaling.get("stat", "intelligence")
                ratio = effect.scaling.get("ratio", 0.5)
                stat_value = self._get_ability_stat(stat_name)
                base += int(stat_value * ratio)

            # Check for miss
            if random.random() > 0.9:
                messages.append(f"{target_name}は避けた！")
                return messages

            # Apply defense
            if isinstance(target, Enemy):
                defense = target.stats.defense // 2
                damage = max(1, base - defense)
                target.current_hp -= damage
            else:
                defending = self.battle_state.player_defending
                defense = 5 if defending else 0
                damage = max(1, base - defense)
                if defending:
                    damage //= 2
                player.combat_stats.hp -= damage

            messages.append(f"{target_name}に{damage}のダメージ！")

        elif effect.type == "inflict_status":
            if random.randint(1, 100) <= effect.chance:
                messages.append(f"{target_name}は{effect.status}状態になった！")
                # Add status effect to target
                if isinstance(target, Player):
                    player.status_effects.append({
                        "id": effect.status,
                        "duration": effect.duration
                    })
            else:
                messages.append(f"{target_name}は状態異常を防いだ！")

        return messages

    def _get_ability_stat(self, stat_name: str) -> int:
        """Get an ability stat value."""
        stats = self.game_state.player.ability_stats
        stat_map = {
            "intelligence": stats.intelligence,
            "strength": stats.strength,
            "sanity": stats.sanity,
            "focus": stats.focus,
            "knowledge": stats.knowledge,
            "dexterity": stats.dexterity,
        }
        return stat_map.get(stat_name, 50)

    def _enemy_turn(self) -> list[str]:
        """Execute enemy's turn using behavior tree."""
        enemy = self.battle_state.enemy
        messages = []

        # Reset enemy defending
        self.battle_state.enemy_defending = False

        # Update cooldowns
        for skill in list(enemy.cooldowns.keys()):
            enemy.cooldowns[skill] -= 1
            if enemy.cooldowns[skill] <= 0:
                del enemy.cooldowns[skill]

        # Evaluate behavior tree
        if enemy.behavior_tree:
            action = self._evaluate_behavior_tree(enemy.behavior_tree)
            if action:
                messages.extend(self._execute_enemy_action(action))
                return messages

        # Default: normal attack
        messages.extend(self._enemy_attack())
        return messages

    def _evaluate_behavior_tree(self, node: BehaviorNode) -> dict | None:
        """Evaluate a behavior tree node and return an action."""
        if node.type == "priority_selector":
            # Try children in order until one succeeds
            for child in node.children:
                result = self._evaluate_behavior_tree(child)
                if result:
                    return result
            return None

        elif node.type == "sequence":
            # Check all conditions
            for condition in node.conditions:
                if not self._check_behavior_condition(condition):
                    return None
            return node.action

        elif node.type == "weighted_random":
            # Select random option based on weights
            total_weight = sum(opt.get("weight", 1) for opt in node.options)
            roll = random.randint(1, total_weight)
            cumulative = 0
            for opt in node.options:
                cumulative += opt.get("weight", 1)
                if roll <= cumulative:
                    return opt.get("action")
            return None

        return None

    def _check_behavior_condition(self, condition: dict) -> bool:
        """Check a behavior condition."""
        cond_type = condition.get("type")
        player = self.game_state.player
        enemy = self.battle_state.enemy

        if cond_type == "check_player_stat":
            stat = condition.get("stat")
            operator = condition.get("operator", "==")
            value = condition.get("value")

            actual = getattr(player.combat_stats, stat, 0)
            return self._compare(actual, operator, value)

        elif cond_type == "check_self_stat":
            stat = condition.get("stat")
            operator = condition.get("operator", "==")
            value = condition.get("value")

            if stat == "hp":
                actual = enemy.current_hp
            else:
                actual = getattr(enemy.stats, stat, 0)
            return self._compare(actual, operator, value)

        elif cond_type == "cooldown_ready":
            skill = condition.get("skill")
            return skill not in enemy.cooldowns

        return True

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare two values."""
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

    def _execute_enemy_action(self, action: dict) -> list[str]:
        """Execute an enemy action from behavior tree."""
        action_type = action.get("type")
        enemy = self.battle_state.enemy
        messages = []

        if action_type == "normal_attack":
            messages.extend(self._enemy_attack())

        elif action_type == "defend":
            self.battle_state.enemy_defending = True
            text = action.get("text", f"{enemy.name}は防御している。")
            messages.append(text)

        elif action_type == "cast_spell":
            spell_id = action.get("spell")
            if spell_id:
                text = action.get("text")
                if text:
                    messages.append(text)
                messages.extend(self._cast_spell(spell_id, is_player=False))

        elif action_type == "bind_attack":
            sequence = action.get("sequence")
            cooldown = action.get("cooldown", 5)
            enemy.cooldowns["bind_attack"] = cooldown
            messages.append(f"{enemy.name}が拘束攻撃を仕掛けてきた！")
            # Signal to start bind sequence
            self.game_state.in_bind_sequence = True
            self.game_state.current_bind_sequence = sequence
            self.game_state.current_bind_stage = 0

        return messages

    def _enemy_attack(self) -> list[str]:
        """Execute enemy's normal attack."""
        player = self.game_state.player
        enemy = self.battle_state.enemy

        # Calculate damage
        base_damage = enemy.stats.atk
        defending = self.battle_state.player_defending
        shield_damage = 0
        hp_damage = 0

        if player.combat_stats.sp > 0:
            # Damage goes to shield first
            shield_damage = min(base_damage, player.combat_stats.sp)
            player.combat_stats.sp -= shield_damage
            hp_damage = base_damage - shield_damage
        else:
            hp_damage = base_damage

        if defending:
            hp_damage //= 2

        if hp_damage > 0:
            player.combat_stats.hp -= hp_damage

        # Get attack text
        if enemy.attack_texts:
            text = random.choice(enemy.attack_texts)
        else:
            text = f"{enemy.name}の攻撃！"

        messages = [text]

        if shield_damage > 0:
            messages.append(f"シールドが{shield_damage}ダメージを吸収した！")
        if hp_damage > 0:
            messages.append(f"{hp_damage}のダメージを受けた！")

        return messages

    def _handle_enemy_defeat(self) -> list[str]:
        """Handle enemy defeat."""
        enemy = self.battle_state.enemy
        messages = []

        if enemy.text.defeat:
            messages.append(enemy.text.defeat)
        messages.append(f"{enemy.name}を倒した！")

        # Award rewards
        exp = enemy.rewards.exp
        if exp > 0:
            messages.append(f"{exp}の経験値を獲得！")

        self._end_battle(player_won=True)
        return messages

    def _handle_player_defeat(self) -> list[str]:
        """Handle player defeat."""
        enemy = self.battle_state.enemy
        messages = []

        if enemy.text.victory:
            messages.append(enemy.text.victory)
        messages.append("敗北した……")

        self._end_battle(player_won=False)
        return messages

    def _end_battle(self, player_won: bool, escaped: bool = False) -> None:
        """End the battle."""
        if self.battle_state:
            self.battle_state.is_over = True
            self.battle_state.player_won = player_won

        self.game_state.in_battle = False
        self.game_state.current_enemy = None

        if self._on_battle_end:
            self._on_battle_end(player_won, escaped)

    def is_in_battle(self) -> bool:
        """Check if currently in battle."""
        return self.battle_state is not None and not self.battle_state.is_over
