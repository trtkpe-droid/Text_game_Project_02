#!/usr/bin/env python3
"""
Text Game Engine - Main Entry Point
YAML-based text adventure game with state machine support.
"""

import sys
import os
from pathlib import Path

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent))

from engine.core import GameEngine
from engine.models import CombatStats, AbilityStats


class TextGameUI:
    """Simple text-based UI for the game engine."""

    def __init__(self):
        self.engine = GameEngine()
        self.running = False
        self.mod_path: Path | None = None

    def display_messages(self, messages: list[str]) -> None:
        """Display messages to the console."""
        for msg in messages:
            print(msg)

    def display_status(self) -> None:
        """Display player status."""
        status = self.engine.get_player_status()
        combat = status["combat"]

        print("\n" + "=" * 40)
        print(f"SP: {combat['SP']}  HP: {combat['HP']}  MP: {combat['MP']}  PT: {combat['PT']}")
        print("=" * 40)

    def display_actions(self) -> list[dict]:
        """Display available actions and return them."""
        actions = self.engine.get_available_actions()

        if not actions:
            print("\n利用可能なアクションがありません。")
            return []

        print("\n【選択肢】")
        for i, action in enumerate(actions):
            label = action.get("label", "???")
            print(f"  {i + 1}. {label}")

        return actions

    def get_player_input(self, actions: list[dict]) -> int | str:
        """Get player input."""
        print()
        while True:
            try:
                user_input = input("> ").strip().lower()

                # Special commands
                if user_input == "status" or user_input == "s":
                    return "status"
                elif user_input == "save":
                    return "save"
                elif user_input == "load":
                    return "load"
                elif user_input == "quit" or user_input == "q":
                    return "quit"
                elif user_input == "help" or user_input == "h":
                    return "help"
                elif user_input == "inventory" or user_input == "i":
                    return "inventory"

                # Action selection
                choice = int(user_input)
                if 1 <= choice <= len(actions):
                    return choice - 1
                else:
                    print("無効な選択です。もう一度入力してください。")

            except ValueError:
                print("数字を入力してください。(help でコマンド一覧)")

    def show_help(self) -> None:
        """Show help message."""
        print("\n【コマンド一覧】")
        print("  数字     - アクションを選択")
        print("  status/s - ステータス表示")
        print("  inventory/i - インベントリ表示")
        print("  save     - ゲームをセーブ")
        print("  load     - ゲームをロード")
        print("  help/h   - このヘルプを表示")
        print("  quit/q   - ゲームを終了")

    def show_inventory(self) -> None:
        """Show player inventory."""
        status = self.engine.get_player_status()
        inventory = status["inventory"]

        print("\n【インベントリ】")
        if not inventory:
            print("  (空)")
        else:
            for item_id, count in inventory.items():
                # Try to get item name
                item = self.engine.items.get(item_id)
                name = item.name if item else item_id
                print(f"  {name}: {count}個")

    def game_loop(self) -> None:
        """Main game loop."""
        self.running = True
        while self.running:
            # Check game state
            if self.engine.is_game_over():
                print("\nゲームオーバー")
                break
            if self.engine.is_game_clear():
                print("\nゲームクリア！おめでとうございます！")
                break

            # Display status bar
            self.display_status()

            # Display actions
            actions = self.display_actions()
            if not actions:
                # No actions available, might be end of content
                print("\n続きはまだ実装されていません。")
                break

            # Get input
            choice = self.get_player_input(actions)

            if choice == "quit":
                print("\nゲームを終了します。")
                break
            elif choice == "status":
                status = self.engine.get_player_status()
                print("\n【詳細ステータス】")
                print("戦闘:")
                for k, v in status["combat"].items():
                    print(f"  {k}: {v}")
                print("能力:")
                for k, v in status["abilities"].items():
                    print(f"  {k}: {v}")
                # Show brands if any
                if self.engine.game_state.player.brands:
                    print("烙印:")
                    for brand in self.engine.game_state.player.brands:
                        print(f"  {brand.enemy_name}: 攻撃力-{int(brand.debuff_ratio * 100)}%")
            elif choice == "save":
                save_path = Path("save.json")
                if self.engine.save_game(save_path):
                    print("セーブしました。")
            elif choice == "load":
                save_path = Path("save.json")
                if save_path.exists():
                    self.engine.load_game(save_path)
                else:
                    print("セーブデータがありません。")
            elif choice == "help":
                self.show_help()
            elif choice == "inventory":
                self.show_inventory()
            elif isinstance(choice, int):
                print()
                self.engine.execute_action(choice)

    def run_normal_game(self) -> None:
        """Run normal game mode."""
        self.engine.new_game()
        self.game_loop()

    def run_battle_test(self) -> None:
        """Run battle test mode."""
        if not self.engine.enemies:
            print("敵が定義されていません。")
            return

        # List available enemies
        print("\n【敵戦闘テスト】")
        print("戦闘する敵を選択してください:\n")

        enemies = list(self.engine.enemies.items())
        for i, (enemy_id, enemy) in enumerate(enemies):
            print(f"  {i + 1}. {enemy.name} (HP:{enemy.stats.hp} ATK:{enemy.stats.atk})")

        print(f"\n  0. 戻る")

        while True:
            try:
                choice = int(input("\n> "))
                if choice == 0:
                    return
                if 1 <= choice <= len(enemies):
                    break
                print("無効な選択です。")
            except ValueError:
                print("数字を入力してください。")

        enemy_id, enemy = enemies[choice - 1]

        # Initialize player for test
        self.engine.new_game()
        print(f"\n{enemy.name}との戦闘を開始します！\n")

        # Start battle
        self.engine._start_battle(enemy_id)
        self.game_loop()

    def run_sequence_test(self) -> None:
        """Run bind sequence test mode."""
        if not self.engine.bind_sequences:
            print("拘束シーケンスが定義されていません。")
            return

        # List available sequences
        print("\n【拘束シーケンステスト】")
        print("テストするシーケンスを選択してください:\n")

        sequences = list(self.engine.bind_sequences.items())
        for i, (seq_id, seq) in enumerate(sequences):
            print(f"  {i + 1}. {seq.metadata.name}")

        print(f"\n  0. 戻る")

        while True:
            try:
                choice = int(input("\n> "))
                if choice == 0:
                    return
                if 1 <= choice <= len(sequences):
                    break
                print("無効な選択です。")
            except ValueError:
                print("数字を入力してください。")

        seq_id, seq = sequences[choice - 1]

        # Initialize player for test
        self.engine.new_game()
        print(f"\n{seq.metadata.name}を開始します！\n")

        # Start bind sequence
        self.engine._start_bind_sequence(seq_id)
        self.game_loop()

    def run_node_test(self) -> None:
        """Run node test mode (start from any node)."""
        if not self.engine.nodes:
            print("ノードが定義されていません。")
            return

        # List available nodes
        print("\n【ノードテスト】")
        print("開始ノードを選択してください:\n")

        nodes = list(self.engine.nodes.items())
        for i, (node_id, node) in enumerate(nodes):
            print(f"  {i + 1}. {node.metadata.display_name} ({node_id})")

        print(f"\n  0. 戻る")

        while True:
            try:
                choice = int(input("\n> "))
                if choice == 0:
                    return
                if 1 <= choice <= len(nodes):
                    break
                print("無効な選択です。")
            except ValueError:
                print("数字を入力してください。")

        node_id, node = nodes[choice - 1]

        # Initialize player for test
        self.engine.new_game()
        self.engine.game_state.current_node = node_id
        print(f"\n{node.metadata.display_name}から開始します！\n")

        self.engine._show_current_location()
        self.game_loop()

    def show_test_menu(self) -> bool:
        """Show test play menu. Returns True to continue, False to go back."""
        while True:
            print("\n【テストプレイモード】")
            print("  1. 敵戦闘テスト")
            print("  2. 拘束シーケンステスト")
            print("  3. ノードテスト")
            print("  0. メインメニューに戻る")

            try:
                choice = int(input("\n> "))
                if choice == 0:
                    return False
                elif choice == 1:
                    self.run_battle_test()
                    return True
                elif choice == 2:
                    self.run_sequence_test()
                    return True
                elif choice == 3:
                    self.run_node_test()
                    return True
                else:
                    print("無効な選択です。")
            except ValueError:
                print("数字を入力してください。")

    def find_mods(self) -> list[Path]:
        """Find available MODs."""
        mods_dir = Path(__file__).parent / "mods"
        if not mods_dir.exists():
            return []

        mods = []
        for path in mods_dir.iterdir():
            if path.is_dir() and (path / "mod.yaml").exists():
                mods.append(path)
            elif path.is_dir() and (path / "data").exists():
                # Also accept MODs without mod.yaml
                mods.append(path)

        return sorted(mods)

    def show_mod_menu(self) -> Path | None:
        """Show MOD selection menu. Returns selected MOD path or None."""
        mods = self.find_mods()

        if not mods:
            print("MODが見つかりません。mods/ ディレクトリにMODを配置してください。")
            return None

        print("\n【MOD選択】")
        for i, mod_path in enumerate(mods):
            mod_name = mod_path.name
            print(f"  {i + 1}. {mod_name}")

        print(f"\n  0. 戻る")

        while True:
            try:
                choice = int(input("\n> "))
                if choice == 0:
                    return None
                if 1 <= choice <= len(mods):
                    return mods[choice - 1]
                print("無効な選択です。")
            except ValueError:
                print("数字を入力してください。")

    def show_main_menu(self) -> str:
        """Show main menu and return selected action."""
        print("\n" + "=" * 50)
        print("  Text Game Engine v2.0")
        print("=" * 50)
        print("\n【メインメニュー】")
        print("  1. ゲームを始める")
        print("  2. 続きから")
        print("  3. テストプレイモード")
        print("  0. 終了")

        while True:
            try:
                choice = int(input("\n> "))
                if choice == 0:
                    return "quit"
                elif choice == 1:
                    return "new_game"
                elif choice == 2:
                    return "continue"
                elif choice == 3:
                    return "test"
                else:
                    print("無効な選択です。")
            except ValueError:
                print("数字を入力してください。")

    def run(self, mod_path: str | Path | None = None) -> None:
        """Run the game with main menu."""
        # If mod_path is specified, use it directly
        if mod_path:
            self.mod_path = Path(mod_path)
            self.engine.set_message_callback(self.display_messages)
            if not self.engine.load_mod(self.mod_path):
                print("MODの読み込みに失敗しました。")
                return
            self.run_normal_game()
            return

        # Main menu loop
        while True:
            action = self.show_main_menu()

            if action == "quit":
                print("\nさようなら！")
                break

            elif action == "new_game":
                mod = self.show_mod_menu()
                if mod:
                    self.mod_path = mod
                    self.engine = GameEngine()
                    self.engine.set_message_callback(self.display_messages)
                    if self.engine.load_mod(self.mod_path):
                        self.run_normal_game()
                    else:
                        print("MODの読み込みに失敗しました。")

            elif action == "continue":
                save_path = Path("save.json")
                if not save_path.exists():
                    print("\nセーブデータがありません。")
                    continue

                # Try to load save to get mod info
                mod = self.show_mod_menu()
                if mod:
                    self.mod_path = mod
                    self.engine = GameEngine()
                    self.engine.set_message_callback(self.display_messages)
                    if self.engine.load_mod(self.mod_path):
                        if self.engine.load_game(save_path):
                            self.game_loop()
                    else:
                        print("MODの読み込みに失敗しました。")

            elif action == "test":
                mod = self.show_mod_menu()
                if mod:
                    self.mod_path = mod
                    self.engine = GameEngine()
                    self.engine.set_message_callback(self.display_messages)
                    if self.engine.load_mod(self.mod_path):
                        self.show_test_menu()
                    else:
                        print("MODの読み込みに失敗しました。")


def main():
    """Main entry point."""
    ui = TextGameUI()

    # Allow specifying MOD path as argument for direct play
    if len(sys.argv) > 1:
        mod_path = Path(sys.argv[1])
        ui.run(mod_path)
    else:
        # Show main menu
        ui.run()


if __name__ == "__main__":
    main()
