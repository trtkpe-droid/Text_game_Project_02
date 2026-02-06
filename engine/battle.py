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
    Spell, SpellEffect, Item, StatusEffectInstance,
    normalize_stat_name, ItemPool, WeightedOption, Brand
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
    player_turn_first: bool = True  # Determined by initiative
    climax_defeat: bool = False  # True if defeat was due to PT overflow


class BattleSystem:
    """Handles combat mechanics."""

    def __init__(self, game_state: GameState, spells: dict[str, Spell],
                 items: dict[str, Item] | None = None,
                 status_effects: dict[str, Any] | None = None,
                 spell_pools: dict[str, ItemPool] | None = None):
        self.game_state = game_state
        self.spells = spells
        self.items = items or {}
        self.status_effects = status_effects or {}
        self.spell_pools = spell_pools or {}
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

        # Determine turn order based on initiative
        player_initiative = self.game_state.player.ability_stats.dexterity
        enemy_initiative = enemy.stats.initiative
        player_first = player_initiative >= enemy_initiative

        self.battle_state = BattleState(
            enemy=battle_enemy,
            player_turn_first=player_first
        )
        self.game_state.in_battle = True
        self.game_state.current_enemy = battle_enemy

        messages = []
        if battle_enemy.text.encounter:
            messages.append(battle_enemy.text.encounter)
        messages.append(f"戦闘開始！ {battle_enemy.name}が現れた！")

        # Show turn order
        if player_first:
            messages.append("先手を取った！")
        else:
            messages.append(f"{battle_enemy.name}に先手を取られた！")
            # Enemy attacks first
            messages.extend(self._enemy_turn())
            # Check if player is defeated after enemy's first turn
            if self._check_player_defeat():
                messages.extend(self._handle_player_defeat())

        return messages

    def get_player_actions(self) -> list[dict]:
        """Get available player actions."""
        player = self.game_state.player

        # Check if player is action-prevented
        if player.is_action_prevented():
            return [{"type": "prevented", "label": "（行動不能）"}]

        actions = [
            {"type": BattleAction.ATTACK, "label": "攻撃"},
            {"type": BattleAction.DEFEND, "label": "防御"},
        ]

        # Add available spells
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

        # Add usable items
        for item_id, count in player.inventory.items():
            if count > 0:
                item = self.items.get(item_id)
                if item and item.type in ["consumable", "usable"]:
                    actions.append({
                        "type": BattleAction.ITEM,
                        "item_id": item_id,
                        "label": f"{item.name} x{count}"
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

        # Process status effect ticks at turn start
        messages.extend(self._process_status_ticks())

        # Check if player is action-prevented
        if player.is_action_prevented():
            messages.append("行動できない……！")
            # Still need to do enemy turn
            messages.extend(self._enemy_turn())
            if self._check_player_defeat():
                messages.extend(self._handle_player_defeat())
                return messages
            self._advance_turn()
            return messages

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

        elif action_type == BattleAction.ITEM:
            if item_id:
                messages.extend(self._use_item(item_id))

        elif action_type == BattleAction.ESCAPE:
            escape_chance = 0.5 + (player.ability_stats.dexterity - enemy.stats.initiative) * 0.01
            escape_chance = max(0.1, min(0.9, escape_chance))
            if random.random() < escape_chance:
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
        if self._check_player_defeat():
            messages.extend(self._handle_player_defeat())
            return messages

        self._advance_turn()
        return messages

    def _check_player_defeat(self) -> bool:
        """Check if player is defeated."""
        player = self.game_state.player
        combat = player.combat_stats

        # Check for climax defeat (PT overflow causing HP damage)
        if combat.pt >= combat.pt_max:
            # Climax causes HP damage
            climax_damage = 20  # Fixed damage from climax
            combat.hp -= climax_damage
            combat.pt = 0  # Reset PT after climax
            if self.battle_state:
                self.battle_state.battle_log.append(f"絶頂！ HPに{climax_damage}のダメージ！")

            if combat.hp <= 0:
                # Climax caused game over - mark for branding
                if self.battle_state:
                    self.battle_state.climax_defeat = True
                return True

        # Check for HP defeat
        return combat.hp <= 0

    def _deal_damage_to_player(self, damage: int, bypass_shield: bool = False) -> tuple[int, int]:
        """
        Deal damage to player with SP shield system.

        Args:
            damage: Amount of damage to deal
            bypass_shield: If True, damage goes directly to HP (e.g., PT climax damage)

        Returns:
            Tuple of (shield_damage, hp_damage)
        """
        player = self.game_state.player
        combat = player.combat_stats

        if bypass_shield or combat.sp <= 0:
            # Damage goes directly to HP
            combat.hp -= damage
            return (0, damage)

        # SP absorbs damage first
        shield_damage = min(damage, combat.sp)
        combat.sp -= shield_damage
        remaining_damage = damage - shield_damage

        if remaining_damage > 0:
            combat.hp -= remaining_damage

        return (shield_damage, remaining_damage)

    def _advance_turn(self) -> None:
        """Advance to next turn and update status effects."""
        self.battle_state.turn += 1
        self._update_status_durations()

    def _process_status_ticks(self) -> list[str]:
        """Process status effect tick effects."""
        messages = []
        player = self.game_state.player

        for status in player.status_effects:
            for tick_effect in status.tick_effects:
                effect_type = tick_effect.get("type")
                if effect_type == "deal_damage":
                    damage = tick_effect.get("amount", 10)
                    player.combat_stats.hp -= damage
                    text = status.text.get("tick", f"{status.name}のダメージを受けた！")
                    text = self._apply_template(text, damage=damage)
                    messages.append(text)

        return messages

    def _update_status_durations(self) -> None:
        """Update status effect durations and remove expired ones."""
        player = self.game_state.player
        expired = []

        for i, status in enumerate(player.status_effects):
            status.remaining_turns -= 1
            if status.remaining_turns <= 0:
                expired.append(i)

        # Remove expired status effects (in reverse order)
        for i in reversed(expired):
            player.status_effects.pop(i)

    def _player_attack(self) -> list[str]:
        """Execute player's normal attack."""
        player = self.game_state.player
        enemy = self.battle_state.enemy
        messages = []

        # Calculate damage
        base_damage = 20 + player.ability_stats.strength // 5

        # Apply brand debuff if player has a brand from this enemy
        brand_debuff = player.get_brand_debuff(enemy.id)
        if brand_debuff > 0:
            base_damage = int(base_damage * (1.0 - brand_debuff))
            messages.append(f"烙印の影響で攻撃力が低下している……")

        # Apply enemy defense (reduced if enemy is defending)
        defense = enemy.stats.defense
        if self.battle_state.enemy_defending:
            defense *= 2  # Enemy takes less damage when defending

        damage = max(1, base_damage - defense // 2)

        # Apply randomness
        damage = int(damage * random.uniform(0.9, 1.1))

        enemy.current_hp -= damage
        messages.append(f"攻撃！ {enemy.name}に{damage}のダメージ！")
        return messages

    def _use_item(self, item_id: str) -> list[str]:
        """Use an item in battle."""
        messages = []
        player = self.game_state.player

        # Check if player has the item
        if player.inventory.get(item_id, 0) <= 0:
            return ["そのアイテムを持っていません。"]

        # Get item definition
        item = self.items.get(item_id)
        if not item:
            return ["不明なアイテムです。"]

        # Consume the item
        player.inventory[item_id] -= 1
        if player.inventory[item_id] <= 0:
            del player.inventory[item_id]

        messages.append(f"{item.name}を使った！")

        # Execute item effects
        for effect in item.effects:
            effect_messages = self._apply_item_effect(effect)
            messages.extend(effect_messages)

        return messages

    def _apply_item_effect(self, effect) -> list[str]:
        """Apply an item effect."""
        messages = []
        player = self.game_state.player
        effect_type = effect.type

        if effect_type == "modify_stat":
            stat = normalize_stat_name(effect.stat)
            operator = effect.operator
            value = effect.value

            current = self._get_player_stat(stat)
            if operator == "+":
                new_value = current + value
            elif operator == "-":
                new_value = current - value
            elif operator == "=":
                new_value = value
            else:
                new_value = current

            self._set_player_stat(stat, new_value)

        elif effect_type == "message":
            messages.append(effect.text)

        elif effect_type == "cure_status":
            status_id = effect.value if hasattr(effect, 'value') else None
            if status_id:
                player.status_effects = [
                    s for s in player.status_effects if s.id != status_id
                ]
            else:
                # Cure all status effects
                player.status_effects.clear()

        return messages

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

        # Cast message with template
        cast_text = self._apply_template(spell.text.cast, caster=caster_name, target=target_name)
        if cast_text:
            messages.append(cast_text)

        # Apply effects
        for effect in spell.effects:
            effect_messages = self._apply_spell_effect(
                effect, is_player, target, target_name, caster_name
            )
            messages.extend(effect_messages)

        return messages

    def _apply_spell_effect(self, effect: SpellEffect, is_player: bool,
                            target: Any, target_name: str,
                            caster_name: str = "") -> list[str]:
        """Apply a spell effect."""
        messages = []
        player = self.game_state.player
        enemy = self.battle_state.enemy

        if effect.type == "deal_damage":
            # Calculate damage
            base = effect.base
            if effect.scaling:
                stat_name = normalize_stat_name(effect.scaling.get("stat", "intelligence"))
                ratio = effect.scaling.get("ratio", 0.5)
                if is_player:
                    stat_value = self._get_ability_stat(stat_name)
                else:
                    stat_value = enemy.stats.matk
                base += int(stat_value * ratio)

            # Check for miss (10% chance)
            if random.random() > 0.9:
                messages.append(f"{target_name}は避けた！")
                return messages

            # Apply defense
            if isinstance(target, Enemy):
                defense = target.stats.defense // 2
                if self.battle_state.enemy_defending:
                    defense *= 2
                damage = max(1, base - defense)
                target.current_hp -= damage
                messages.append(f"{target_name}に{damage}のダメージ！")
            else:
                # Player is target - use SP shield
                defending = self.battle_state.player_defending
                defense = 5 if defending else 0
                damage = max(1, base - defense)
                if defending:
                    damage //= 2

                shield_dmg, hp_dmg = self._deal_damage_to_player(damage)

                if shield_dmg > 0:
                    messages.append(f"シールドが{shield_dmg}ダメージを吸収した！")
                if hp_dmg > 0:
                    messages.append(f"{hp_dmg}のダメージを受けた！")

        elif effect.type == "heal":
            # Healing effect
            base = effect.base
            if effect.scaling and is_player:
                stat_name = normalize_stat_name(effect.scaling.get("stat", "intelligence"))
                ratio = effect.scaling.get("ratio", 0.3)
                stat_value = self._get_ability_stat(stat_name)
                base += int(stat_value * ratio)

            if is_player:
                old_hp = player.combat_stats.hp
                player.combat_stats.hp = min(
                    player.combat_stats.hp_max,
                    player.combat_stats.hp + base
                )
                healed = player.combat_stats.hp - old_hp
                messages.append(f"HPが{healed}回復した！")

        elif effect.type == "inflict_status":
            if random.randint(1, 100) <= effect.chance:
                # Create status effect instance
                status_def = self.status_effects.get(effect.status)
                if status_def:
                    status_instance = StatusEffectInstance(
                        id=effect.status,
                        name=status_def.name if hasattr(status_def, 'name') else effect.status,
                        remaining_turns=effect.duration,
                        effects=status_def.effects if hasattr(status_def, 'effects') else [],
                        tick_effects=status_def.tick_effects if hasattr(status_def, 'tick_effects') else [],
                        text=status_def.text if hasattr(status_def, 'text') else {}
                    )
                else:
                    status_instance = StatusEffectInstance(
                        id=effect.status,
                        name=effect.status,
                        remaining_turns=effect.duration,
                        effects=[{"type": "prevent_action"}] if effect.status == "charm" else [],
                        tick_effects=[],
                        text={}
                    )

                if isinstance(target, Player):
                    player.status_effects.append(status_instance)
                    messages.append(f"{target_name}は{status_instance.name}状態になった！")
            else:
                messages.append(f"{target_name}は状態異常を防いだ！")

        return messages

    def _get_ability_stat(self, stat_name: str) -> int:
        """Get an ability stat value."""
        stat_name = normalize_stat_name(stat_name)
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

    def _get_player_stat(self, stat: str) -> int:
        """Get a player stat value."""
        stat = normalize_stat_name(stat)
        player = self.game_state.player
        combat = player.combat_stats
        ability = player.ability_stats

        stat_map = {
            "sp": combat.sp, "hp": combat.hp, "mp": combat.mp, "pt": combat.pt,
            "sp_max": combat.sp_max, "hp_max": combat.hp_max,
            "mp_max": combat.mp_max, "pt_max": combat.pt_max,
            "sanity": ability.sanity, "strength": ability.strength,
            "focus": ability.focus, "intelligence": ability.intelligence,
            "knowledge": ability.knowledge, "dexterity": ability.dexterity,
        }
        return stat_map.get(stat, 0)

    def _set_player_stat(self, stat: str, value: int) -> None:
        """Set a player stat value."""
        stat = normalize_stat_name(stat)
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
        elif stat == "focus":
            ability.focus = max(0, min(100, value))
        elif stat == "intelligence":
            ability.intelligence = max(0, min(100, value))
        elif stat == "knowledge":
            ability.knowledge = max(0, min(100, value))
        elif stat == "dexterity":
            ability.dexterity = max(0, min(100, value))

    def _apply_template(self, text: str, **kwargs) -> str:
        """Apply template variables to text."""
        if not text:
            return text

        replacements = {
            "{{caster}}": kwargs.get("caster", ""),
            "{{target}}": kwargs.get("target", ""),
            "{{damage}}": str(kwargs.get("damage", "")),
        }

        for key, value in replacements.items():
            text = text.replace(key, value)

        return text

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
            if total_weight == 0:
                return None
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
            stat = normalize_stat_name(condition.get("stat"))
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
            spell_pool_id = action.get("spell_pool")

            # Handle spell_pool
            if spell_pool_id and not spell_id:
                spell_id = self._select_from_spell_pool(spell_pool_id)

            if spell_id:
                text = action.get("text")
                if text:
                    messages.append(text)
                messages.extend(self._cast_spell(spell_id, is_player=False))

        elif action_type == "bind_attack":
            player = self.game_state.player
            # Bind attack only works when SP is 0
            if player.combat_stats.sp > 0:
                messages.append(f"{enemy.name}が拘束を試みたが、シールドに阻まれた！")
            else:
                sequence = action.get("sequence")
                cooldown = action.get("cooldown", 5)
                enemy.cooldowns["bind_attack"] = cooldown
                messages.append(f"{enemy.name}が拘束攻撃を仕掛けてきた！")
                # Signal to start bind sequence
                self.game_state.in_bind_sequence = True
                self.game_state.current_bind_sequence = sequence
                self.game_state.current_bind_stage = 0

        return messages

    def _select_from_spell_pool(self, pool_id: str) -> str | None:
        """Select a spell from a spell pool."""
        pool = self.spell_pools.get(pool_id)
        if not pool or not pool.options:
            return None

        total_weight = sum(opt.weight for opt in pool.options)
        if total_weight == 0:
            return random.choice(pool.options).value

        roll = random.randint(1, total_weight)
        cumulative = 0
        for opt in pool.options:
            cumulative += opt.weight
            if roll <= cumulative:
                return opt.value

        return pool.options[-1].value

    def _enemy_attack(self) -> list[str]:
        """Execute enemy's normal attack."""
        player = self.game_state.player
        enemy = self.battle_state.enemy

        # Calculate damage
        base_damage = enemy.stats.atk
        defending = self.battle_state.player_defending

        if defending:
            base_damage //= 2

        # Use SP shield system
        shield_damage, hp_damage = self._deal_damage_to_player(base_damage)

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
        player = self.game_state.player
        enemy = self.battle_state.enemy
        messages = []

        # Check if this was a climax defeat (PT overflow caused HP to reach 0)
        if self.battle_state.climax_defeat:
            messages.append("快楽に屈した……！")

            # Add brand from this enemy
            if not player.has_brand(enemy.id):
                player.add_brand(enemy.id, enemy.name)
                messages.append(f"{enemy.name}の烙印が刻まれた……")
                messages.append("この敵に対する攻撃力が低下する。")

        if enemy.text.victory:
            messages.append(enemy.text.victory)
        messages.append("敗北した……")

        # Set game over
        self.game_state.game_over = True

        self._end_battle(player_won=False)
        return messages

    def _end_battle(self, player_won: bool, escaped: bool = False) -> None:
        """End the battle."""
        if self.battle_state:
            self.battle_state.is_over = True
            self.battle_state.player_won = player_won

        self.game_state.in_battle = False
        self.game_state.current_enemy = None

        # Clear temporary status effects after battle
        # (Keep persistent ones if needed)

        if self._on_battle_end:
            self._on_battle_end(player_won, escaped)

    def is_in_battle(self) -> bool:
        """Check if currently in battle."""
        return self.battle_state is not None and not self.battle_state.is_over
