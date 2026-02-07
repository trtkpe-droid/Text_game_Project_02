"""
Shared fixtures for testing the game engine.
"""

import pytest
from engine.models import (
    GameState, Player, CombatStats, AbilityStats,
    Enemy, EnemyStats, EnemyRewards, EnemyText,
    Spell, SpellEffect, SpellText, Brand
)
from engine.battle import BattleSystem, BattleState


@pytest.fixture
def default_player() -> Player:
    """Create a player with default stats."""
    return Player(
        combat_stats=CombatStats(
            sp=100, sp_max=100,
            hp=80, hp_max=80,
            mp=50, mp_max=50,
            pt=0, pt_max=100
        ),
        ability_stats=AbilityStats(
            sanity=70, strength=50, focus=60,
            intelligence=65, knowledge=55, dexterity=45
        )
    )


@pytest.fixture
def game_state(default_player) -> GameState:
    """Create a game state with default player."""
    return GameState(
        current_node="test_node",
        player=default_player
    )


@pytest.fixture
def test_enemy() -> Enemy:
    """Create a basic test enemy."""
    return Enemy(
        id="test_enemy",
        name="Test Enemy",
        description="A test enemy",
        stats=EnemyStats(
            hp=100, atk=20, defense=10, matk=15, initiative=10
        ),
        rewards=EnemyRewards(exp=50),
        text=EnemyText(
            encounter="Test enemy appeared!",
            defeat="Test enemy defeated!",
            victory="You were defeated!"
        ),
        attack_texts=["Test enemy attacks!"]
    )


@pytest.fixture
def battle_system(game_state) -> BattleSystem:
    """Create a battle system with default game state."""
    return BattleSystem(
        game_state=game_state,
        spells={},
        items={},
        status_effects={},
        spell_pools={}
    )


@pytest.fixture
def battle_system_with_spells(game_state) -> BattleSystem:
    """Create a battle system with spells for testing."""
    spells = {
        "test_damage": Spell(
            id="test_damage",
            name="Test Damage",
            description="Deals 30 damage",
            cost={"mp": 10},
            effects=[
                SpellEffect(
                    type="deal_damage",
                    damage_type="magic",
                    base=30
                )
            ],
            text=SpellText(cast="Casting test damage!")
        ),
        "test_pt_damage": Spell(
            id="test_pt_damage",
            name="Test PT Damage",
            description="Deals 30 PT damage",
            cost={"mp": 10},
            effects=[
                SpellEffect(
                    type="deal_damage",
                    damage_type="pt",
                    base=30
                )
            ],
            text=SpellText(cast="Casting pleasure attack!")
        )
    }
    return BattleSystem(
        game_state=game_state,
        spells=spells,
        items={},
        status_effects={},
        spell_pools={}
    )


@pytest.fixture
def active_battle(battle_system, test_enemy) -> BattleSystem:
    """Create a battle system with an active battle."""
    battle_system.start_battle(test_enemy)
    return battle_system
