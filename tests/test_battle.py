"""
Tests for battle system mechanics.
Covers SP shield, PT/climax, and brand systems.
"""

import pytest
from engine.battle import BattleSystem, BattleAction
from engine.models import GameState, Player, CombatStats, Enemy, EnemyStats, SpellEffect


class TestSPShield:
    """Tests for SP shield damage absorption system."""

    def test_damage_absorbed_by_sp_when_sp_positive(self, active_battle):
        """Damage should be absorbed by SP when SP > 0."""
        player = active_battle.game_state.player
        player.combat_stats.sp = 50
        player.combat_stats.hp = 80

        shield_dmg, hp_dmg = active_battle._deal_damage_to_player(30)

        assert shield_dmg == 30
        assert hp_dmg == 0
        assert player.combat_stats.sp == 20
        assert player.combat_stats.hp == 80

    def test_overflow_damage_goes_to_hp(self, active_battle):
        """Damage exceeding SP should overflow to HP."""
        player = active_battle.game_state.player
        player.combat_stats.sp = 20
        player.combat_stats.hp = 80

        shield_dmg, hp_dmg = active_battle._deal_damage_to_player(50)

        assert shield_dmg == 20
        assert hp_dmg == 30
        assert player.combat_stats.sp == 0
        assert player.combat_stats.hp == 50

    def test_damage_goes_directly_to_hp_when_sp_zero(self, active_battle):
        """Damage should go directly to HP when SP is 0."""
        player = active_battle.game_state.player
        player.combat_stats.sp = 0
        player.combat_stats.hp = 80

        shield_dmg, hp_dmg = active_battle._deal_damage_to_player(30)

        assert shield_dmg == 0
        assert hp_dmg == 30
        assert player.combat_stats.sp == 0
        assert player.combat_stats.hp == 50

    def test_bypass_shield_ignores_sp(self, active_battle):
        """Bypass shield should ignore SP and damage HP directly."""
        player = active_battle.game_state.player
        player.combat_stats.sp = 100
        player.combat_stats.hp = 80

        shield_dmg, hp_dmg = active_battle._deal_damage_to_player(30, bypass_shield=True)

        assert shield_dmg == 0
        assert hp_dmg == 30
        assert player.combat_stats.sp == 100
        assert player.combat_stats.hp == 50


class TestPTDamage:
    """Tests for PT (pleasure) damage and climax system."""

    def test_pt_damage_increases_pt_only(self, active_battle):
        """PT damage should only increase PT, not deal HP damage."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 0
        player.combat_stats.hp = 80

        messages, hp_damage = active_battle._deal_pt_damage(30)

        assert player.combat_stats.pt == 30
        assert player.combat_stats.hp == 80
        assert hp_damage == 0
        assert "PTが30上昇した！" in messages

    def test_pt_accumulates_over_multiple_attacks(self, active_battle):
        """PT should accumulate with multiple attacks."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 0

        active_battle._deal_pt_damage(30)
        active_battle._deal_pt_damage(25)

        assert player.combat_stats.pt == 55

    def test_pt_capped_at_max(self, active_battle):
        """PT should not exceed pt_max."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 90
        player.combat_stats.pt_max = 100

        messages, _ = active_battle._deal_pt_damage(20)

        # Should cap at 100, then trigger climax which resets to 0
        # But first check message for actual gain
        assert "PTが10上昇した！" in messages

    def test_climax_triggers_at_pt_max(self, active_battle):
        """Climax should trigger when PT reaches pt_max."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 80
        player.combat_stats.pt_max = 100
        player.combat_stats.hp = 80

        messages, hp_damage = active_battle._deal_pt_damage(25)

        assert "絶頂した！" in messages
        assert player.combat_stats.pt == 0  # Reset after climax

    def test_climax_deals_hp_damage(self, active_battle):
        """Climax should deal HP damage based on pt_max."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 90
        player.combat_stats.pt_max = 100
        player.combat_stats.hp = 80

        messages, hp_damage = active_battle._deal_pt_damage(15)

        # Damage = 10 (base) + 100 // 5 (20% of pt_max) = 30
        expected_damage = 10 + 100 // 5
        assert hp_damage == expected_damage
        assert player.combat_stats.hp == 80 - expected_damage

    def test_climax_defeat_sets_flag(self, active_battle):
        """Climax causing HP <= 0 should set climax_defeat flag."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 90
        player.combat_stats.pt_max = 100
        player.combat_stats.hp = 20  # Less than climax damage (30)

        active_battle._deal_pt_damage(15)

        assert active_battle.battle_state.climax_defeat is True

    def test_pt_resets_after_climax(self, active_battle):
        """PT should reset to 0 after climax."""
        player = active_battle.game_state.player
        player.combat_stats.pt = 99
        player.combat_stats.pt_max = 100
        player.combat_stats.hp = 80

        active_battle._deal_pt_damage(5)

        assert player.combat_stats.pt == 0


class TestBrandSystem:
    """Tests for brand/mark system."""

    def test_player_has_no_brand_initially(self, game_state):
        """Player should have no brands initially."""
        player = game_state.player

        assert len(player.brands) == 0
        assert player.has_brand("test_enemy") is False

    def test_add_brand_to_player(self, game_state):
        """Adding a brand should work correctly."""
        player = game_state.player

        player.add_brand("succubus", "サキュバス", 0.2)

        assert player.has_brand("succubus") is True
        assert len(player.brands) == 1

    def test_brand_debuff_ratio(self, game_state):
        """Brand should provide correct debuff ratio."""
        player = game_state.player
        player.add_brand("succubus", "サキュバス", 0.3)

        debuff = player.get_brand_debuff("succubus")

        assert debuff == 0.3

    def test_no_debuff_without_brand(self, game_state):
        """No debuff when player doesn't have brand from that enemy."""
        player = game_state.player

        debuff = player.get_brand_debuff("unknown_enemy")

        assert debuff == 0.0

    def test_cannot_add_duplicate_brand(self, game_state):
        """Cannot add duplicate brand from same enemy."""
        player = game_state.player
        player.add_brand("succubus", "サキュバス", 0.2)
        player.add_brand("succubus", "サキュバス", 0.3)

        assert len(player.brands) == 1
        assert player.get_brand_debuff("succubus") == 0.2

    def test_remove_brand(self, game_state):
        """Removing a brand should work correctly."""
        player = game_state.player
        player.add_brand("succubus", "サキュバス", 0.2)

        result = player.remove_brand("succubus")

        assert result is True
        assert player.has_brand("succubus") is False

    def test_remove_nonexistent_brand(self, game_state):
        """Removing nonexistent brand should return False."""
        player = game_state.player

        result = player.remove_brand("unknown")

        assert result is False


class TestPlayerDefeat:
    """Tests for player defeat detection."""

    def test_defeat_when_hp_zero(self, active_battle):
        """Player should be defeated when HP reaches 0."""
        player = active_battle.game_state.player
        player.combat_stats.hp = 0

        assert active_battle._check_player_defeat() is True

    def test_defeat_when_hp_negative(self, active_battle):
        """Player should be defeated when HP is negative."""
        player = active_battle.game_state.player
        player.combat_stats.hp = -10

        assert active_battle._check_player_defeat() is True

    def test_not_defeated_when_hp_positive(self, active_battle):
        """Player should not be defeated when HP is positive."""
        player = active_battle.game_state.player
        player.combat_stats.hp = 1

        assert active_battle._check_player_defeat() is False


class TestBattleIntegration:
    """Integration tests for battle mechanics."""

    def test_battle_start_sets_flags(self, battle_system, test_enemy):
        """Starting battle should set in_battle flag."""
        battle_system.start_battle(test_enemy)

        assert battle_system.game_state.in_battle is True
        assert battle_system.battle_state is not None
        assert battle_system.battle_state.enemy.id == "test_enemy"

    def test_battle_escape(self, active_battle):
        """Successful escape should end battle."""
        # Force escape success by mocking random
        import random
        random.seed(42)  # Set seed for reproducibility

        # Try escape multiple times to get at least one success
        escaped = False
        for _ in range(20):
            messages = active_battle.execute_player_action(BattleAction.ESCAPE)
            if "逃げ出した！" in messages:
                escaped = True
                break
            # Reset battle state for next try
            if active_battle.game_state.in_battle:
                continue

        # At least one escape should succeed
        assert escaped or active_battle.game_state.in_battle is False

    def test_player_attack_damages_enemy(self, active_battle):
        """Player attack should deal damage to enemy."""
        enemy = active_battle.battle_state.enemy
        initial_hp = enemy.current_hp

        messages = active_battle.execute_player_action(BattleAction.ATTACK)

        # Enemy HP should decrease (unless enemy defeated player first)
        if not active_battle.game_state.game_over:
            assert enemy.current_hp < initial_hp or enemy.current_hp <= 0
