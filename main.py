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


class TextGameUI:
    """Simple text-based UI for the game engine."""

    def __init__(self):
        self.engine = GameEngine()
        self.running = False

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
                print(f"  {item_id}: {count}個")

    def run(self, mod_path: str) -> None:
        """Run the game."""
        print("=" * 50)
        print("  Text Game Engine v2.0")
        print("=" * 50)
        print()

        # Load MOD
        self.engine.set_message_callback(self.display_messages)

        if not self.engine.load_mod(mod_path):
            print("MODの読み込みに失敗しました。")
            return

        # Start new game
        self.engine.new_game()

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


def main():
    """Main entry point."""
    # Default MOD path
    mod_path = Path(__file__).parent / "mods" / "sample_mod"

    # Allow specifying MOD path as argument
    if len(sys.argv) > 1:
        mod_path = Path(sys.argv[1])

    ui = TextGameUI()
    ui.run(str(mod_path))


if __name__ == "__main__":
    main()
