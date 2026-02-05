--- START OF FILE 企画書_v8_カスタム拘束選択肢対応.txt ---

【マップ・イベントデータの記述方式】
MOD作成の敷居を下げ、かつデータの堅牢性・拡張性を確保するため、業界標準のデータシリアライズ形式である YAML を採用する。
従来の文字列タグベース（`[go_to:場所]`等）から、**構造化オブジェクト記述**へと全面刷新。
インデント（字下げ）による階層構造で記述するため可読性が高く、Pythonの標準ライブラリ（PyYAML等）およびデータクラスでの型安全な解析が容易である。

【新システムの利点】
1. **型安全性**: データクラスによる静的検証で、実行前にエラーを検出
2. **拡張性**: プラグインシステムにより、カスタムアクションを簡単に追加可能
3. **再利用性**: 共通パターンをテンプレート化・継承可能
4. **可読性**: オブジェクト指向的な記述で、意図が明確
5. **ツール対応**: GUI MOD Creatorアプリでの編集・バリデーションが容易

基本ルール:
1. 階層構造: インデント（スペース2つ推奨）で親子関係を表現する。
2. キーと値: `key: value` の形式で記述。
3. リスト表現: `-` を頭につけることで、リストを表現する。
4. 長文テキスト: `|` 記号を使うことで、改行を含んだ文章を見たまま記述できる。
5. コメント: `#` を使用して注釈や仕様説明を記述できる。
6. オブジェクト構造: `type` フィールドで種類を指定し、エンジンが適切に処理する。

---

【確率セレクター（Weight-Based Selection）】
アイテムドロップ、敵の行動選択、テキストバリエーションなど、確率抽選が必要な箇所で使用する統一記法。

基本形式:
```yaml
options:
  - weight: 50
    value: "候補A"
  - weight: 30
    value: "候補B"
  - weight: 20
    value: "候補C"
```

ルール:
- `weight`: その選択肢が選ばれる重み（合計に対する比率で計算）
- `weight` 省略時: 残りの選択肢で均等配分
- 複数アイテムのセット: `value` をリスト形式で記述

記述例:
```yaml
# 50%で薬草、30%で毒消し、20%で何も出ない
loot:
  type: weighted_random
  options:
    - weight: 50
      value: herb
    - weight: 30
      value: antidote
    - weight: 20
      value: null

# 剣と盾をセットで10%、金貨を90%
treasure:
  type: weighted_random
  options:
    - weight: 10
      value: [sword, shield]  # セット
    - weight: 90
      value: gold_coin
```

【アイテムプール】
よく使う抽選パターンを「プール」として定義し、参照するシステム。

```yaml
# pools.yaml
item_pools:
  daily_items:
    type: weighted_random
    options:
      - weight: 40
        value: herb
      - weight: 30
        value: bandage
      - weight: 20
        value: antidote
      - weight: 10
        value: null
  
  rare_items:
    type: weighted_random
    options:
      - weight: 50
        value: magic_stone
      - weight: 30
        value: elixir
      - weight: 20
        value: legendary_sword
```

使用例:
```yaml
actions:
  - id: search_chest
    type: interaction
    label: "宝箱を開ける"
    effects:
      - type: item_roll
        pool: rare_items
        count: 1
```

---

【ノード定義（新スキーマ）】

ノード（場所・イベント地点）の記述方式。状態機械（ステートマシン）として管理する。

```yaml
node:
  id: bedroom
  type: location
  
  # メタ情報
  metadata:
    display_name: "寝室"
    description: "プレイヤーの私室"
  
  # 状態機械の定義
  state_machine:
    initial_state: normal  # 初期状態
    
    states:
      # ▼通常状態
      normal:
        description: |
          あなたはベッドルームにいる。
          部屋は整然として、清潔に保たれている。
        
        # このノードで実行可能なアクション
        actions:
          - id: search_drawer
            type: interaction
            label: "タンスを探る"
            
            effects:
              - type: item_roll
                pool: daily_items
                count: 1
          
          - id: search_drawer_deep
            type: interaction
            label: "タンスの裏を探る"
            
            # 条件付きアクション（条件を満たさないと表示されない）
            requirements:
              - type: stat_check
                stat: 集中
                operator: ">="
                value: 40
            
            effects:
              - type: get_item
                item: key
              - type: message
                text: "何かを見つけた！"
          
          - id: go_hallway
            type: navigation
            label: "廊下へ出る"
            target: hallway
      
      # ▼火災状態（条件付き状態）
      on_fire:
        # この状態に遷移する条件
        trigger:
          type: flag_check
          flag: fire_started
          value: true
        
        description: |
          ベッドルームでは火が燃え盛っている！
          悠長に探索している場合ではない。
        
        actions:
          - id: escape
            type: navigation
            label: "廊下へ脱出する"
            target: hallway
            
            effects:
              - type: message
                text: "炎をかいくぐって脱出した！"
  
  # オブジェクト（部屋内の相互作用可能な物）
  objects:
    candle:
      id: candle
      type: interactive_object
      
      state_machine:
        initial_state: lit
        
        states:
          lit:
            description: "サイドテーブルでは、キャンドルの上に小さな灯が揺れている。"
            
            actions:
              - id: take_candle
                type: interaction
                label: "キャンドルをとる"
                effects:
                  - type: get_item
                    item: candle
                  - type: change_object_state
                    object: candle
                    new_state: taken
              
              - id: extinguish
                type: interaction
                label: "灯を消す"
                effects:
                  - type: message
                    text: "息を吹きかけて消した。"
                  - type: change_object_state
                    object: candle
                    new_state: extinguished
          
          extinguished:
            description: "サイドテーブルには、火の消えたキャンドルが置かれている。"
            
            actions:
              - id: take_candle
                type: interaction
                label: "キャンドルをとる"
                effects:
                  - type: get_item
                    item: candle
                  - type: change_object_state
                    object: candle
                    new_state: taken
              
              - id: light
                type: interaction
                label: "灯をつける"
                requirements:
                  - type: item_check
                    item: lighter
                effects:
                  - type: message
                    text: "再び火をつけた。"
                  - type: change_object_state
                    object: candle
                    new_state: lit
          
          taken:
            description: "サイドテーブルには何も置かれていない。"
            # アクションなし
    
    door_to_study:
      id: study_door
      type: interactive_object
      
      state_machine:
        initial_state: locked
        
        states:
          locked:
            description: "部屋の隅には書斎へと続くと思しきドアがある。"
            
            actions:
              - id: examine
                type: interaction
                label: "書斎のドアを調べる"
                effects:
                  - type: message
                    text: "ドアには鍵がかかっている。"
              
              - id: unlock
                type: interaction
                label: "鍵を使ってドアを開ける"
                requirements:
                  - type: item_check
                    item: key
                effects:
                  - type: message
                    text: "鍵を使ってドアを開けた。"
                  - type: navigation
                    target: study
```

---

【アクションタイプ一覧】

エフェクト（effects）として使用できるアクションの種類:

**基本アクション:**
- `navigation`: 別ノードへ移動
  - `target`: 移動先ノードID
- `message`: メッセージ表示
  - `text`: 表示テキスト
- `get_item`: アイテム入手
  - `item`: アイテムID
  - `count`: 個数（省略時1）
- `item_roll`: アイテムプールから抽選
  - `pool`: プールID
  - `count`: 抽選回数

**状態変更:**
- `set_flag`: フラグを設定
  - `flag`: フラグ名
  - `value`: 値（true/false/数値）
- `modify_stat`: ステータス変更
  - `stat`: ステータス名
  - `operator`: "+", "-", "=", "*", "/"
  - `value`: 変更量
- `change_node_state`: ノード状態遷移
  - `node`: ノードID（省略時は現在ノード）
  - `new_state`: 遷移先状態名
- `change_object_state`: オブジェクト状態遷移
  - `object`: オブジェクトID
  - `new_state`: 遷移先状態名

**戦闘関連:**
- `battle`: 戦闘開始
  - `enemy`: 敵ID
  - または `enemy_pool`: 敵プールID
- `run_bind_sequence`: 拘束シーケンス開始
  - `sequence`: シーケンスID
- `switch_bind_sequence`: 拘束シーケンス切替
  - `target`: 切替先シーケンスID
  - `stage`: 開始ステージ（省略時0）

**特殊:**
- `game_over`: ゲームオーバー
  - `reason`: 理由テキスト（省略可）
- `game_clear`: ゲームクリア
  - `ending`: エンディングID（省略可）

**条件（requirements）の種類:**
- `stat_check`: ステータス判定
  - `stat`: ステータス名
  - `operator`: "==", "!=", ">=", "<=", ">", "<"
  - `value`: 比較値
- `flag_check`: フラグ判定
  - `flag`: フラグ名
  - `value`: 期待値
- `item_check`: アイテム所持判定
  - `item`: アイテムID
  - `count`: 必要個数（省略時1以上）

---

【敵キャラクター定義（新スキーマ）】

敵キャラクターは**ビヘイビアツリー**（行動木）により、柔軟なAIを実装する。

```yaml
enemy:
  id: succubus
  
  metadata:
    name: "サキュバス"
    description: "夢魔の女性。魅惑的な外見で獲物を誘い込む。"
  
  # 基本ステータス
  stats:
    hp: 200
    atk: 25
    def: 15
    matk: 40
    initiative: 12  # イニシアチブ（行動順）
  
  # 報酬
  rewards:
    exp: 150
    drops:
      type: weighted_random
      options:
        - weight: 60
          value: succubus_feather
        - weight: 30
          value: [succubus_feather, magic_stone]  # セット
        - weight: 10
          value: rare_essence
  
  # 出現・撃破時のテキスト
  text:
    encounter: "妖艶なサキュバスが現れた！"
    defeat: "サキュバスは悲鳴を上げて消え去った。"
    victory: "サキュバスの魔法に屈した……。"
  
  # 通常攻撃テキスト（ランダム選択）
  attack_texts:
    type: random_select
    options:
      - "サキュバスが爪で引っ掻いてきた！"
      - "サキュバスが尻尾を振り回してきた！"
  
  # 使用可能な魔法
  spells:
    - fire_ball
    - charm_touch
    - energy_drain
  
  # AI行動木（ビヘイビアツリー）
  behavior_tree:
    type: priority_selector  # 上から順に評価、条件を満たした最初の行動を実行
    
    children:
      # 最優先: 拘束攻撃（シールド0かつクールダウン完了時）
      - type: sequence
        name: binding_attack
        
        conditions:
          - type: check_player_stat
            stat: sp
            operator: "=="
            value: 0
          - type: cooldown_ready
            skill: bind_drain
        
        action:
          type: bind_attack
          sequence: succubus_drain
          cooldown: 5  # 5ターン再使用不可
      
      # 優先: HP50%以下で全体攻撃
      - type: sequence
        name: desperate_attack
        
        conditions:
          - type: check_self_stat
            stat: hp
            operator: "<="
            value: 100  # HP50%
        
        action:
          type: cast_spell
          spell: dark_explosion
          text: "サキュバスが絶叫し、暗黒の爆発を放った！"
      
      # 通常: ランダム行動（重み付き）
      - type: weighted_random
        name: normal_combat
        
        options:
          - weight: 50
            action:
              type: normal_attack
          
          - weight: 30
            action:
              type: cast_spell
              spell_pool: succubus_basic_spells
          
          - weight: 15
            action:
              type: cast_spell
              spell: charm_touch
              text: "サキュバスが魅惑的な微笑みを浮かべた……。"
          
          - weight: 5
            action:
              type: defend
              text: "サキュバスは翼で身を守っている。"
  
  # 勝敗イベント
  events:
    on_victory: bedroom  # プレイヤー勝利時のノード
    on_defeat: succubus_defeat_scene  # プレイヤー敗北時のノード
```

---

【拘束シーケンス定義（新スキーマ）】

拘束イベントを「段階的な攻防」として表現する。

**システム概要:**
- 複数のステージ（段階）で構成
- ステージ0から後退（-1）で脱出成功
- 最終ステージで留まるとダメージループ
- **3つの基本コマンド**（システムが自動生成）:
  1. **抵抗**: 成功率高、1段階改善
  2. **全力抵抗**: 成功率低、成功で即脱出、失敗でPT大幅上昇
  3. **抵抗しない**: 判定なしで1段階進行、次ターンボーナス
- **カスタムアクション**: 各ステージで追加の選択肢を定義可能
  - 基本コマンドの動作を上書き可能（例: 確定失敗にする）
  - ステータス参照による動的成功率
  - 別シーケンスへの分岐
  - 即座脱出、ダメージ、アイテム使用など自由に設定

```yaml
bind_sequence:
  id: succubus_drain
  
  metadata:
    name: "サキュバスの精気吸収"
    description: "キスにより精気を吸い取られる拘束"
  
  # 基礎設定
  config:
    base_difficulty: 50  # 抵抗の基礎難易度（0-100）
    escape_target: battle_resume  # 脱出成功時の戻り先
    loop_damage:
      pt: 20  # ループ時の快楽ダメージ
      hp: 5   # ループ時のHP減少
  
  # 各段階の定義
  stages:
    # ▼第1段階
    - stage: 0
      description: |
        甘い香りが思考を鈍らせる。
        サキュバスはあなたの耳元で何かを囁き、魔法的な力で動きを封じてくる。
      
      # プレイヤー行動時のテキスト（省略時はデフォルト）
      player_texts:
        on_resist_success:
          type: random_select
          options:
            - "必死に抵抗した！"
            - "なんとか振りほどいた！"
        
        on_resist_fail:
          type: random_select
          options:
            - "抵抗できない……"
            - "体が言うことを聞かない……"
        
        on_wait: "力を溜めている……。"
      
      # 敵の反応テキスト
      enemy_reactions:
        on_player_resist_success: "「あら、意外と元気なのね？」"
        on_player_resist_fail: "「ふふ、いい子ね……♡」"
        on_player_wait: "「そう、そのままで……」"
    
    # ▼第2段階
    - stage: 1
      description: |
        「暴れないで……いい夢を見せてあげる」
        柔らかな翼が視界を覆い、強烈な眠気が襲ってくる。
      
      enemy_reactions:
        on_player_resist_success: "「きゃっ！？ ……乱暴な人ね」"
    
    # ▼第3段階（カスタムアクション使用例）
    - stage: 2
      description: |
        サキュバスがあなたの顔を覗き込む。
        その瞳には怪しい光が宿っており、見つめているだけで吸い込まれそうだ。
        彼女の唇がゆっくりと近づいてくる……。
      
      player_texts:
        on_resist_success: "誘惑を振り切り、サキュバスを引き剥がした！"
        on_wait: "抵抗を諦め、その瞳を見つめ返す……。"
      
      enemy_reactions:
        on_player_resist_success: "「きゃっ！？ ……乱暴な人ね」"
        on_player_resist_fail: |
          「ふふ、いい子ね。力を抜いて……♡」
          サキュバスの顔がゆっくりと近づいてくる。
        on_player_wait: "「そう、そのままで……」"
      
      # ▼基本コマンドの動作上書き
      default_choices_override:
        resist:
          enabled: false  # この段階では「抵抗」は選択不可（グレーアウト）
          override_result: auto_fail  # または強制失敗させる
          reason: "唇が触れる直前、体が動かない……！"
        
        resist_hard:
          enabled: true  # 「全力抵抗」は有効
          success_rate_modifier: -30  # ただし成功率-30%（より困難に）
        
        wait:
          enabled: false  # 「抵抗しない」も選択不可
          override_result: auto_fail
          reason: "このまま受け入れるわけにはいかない……！"
      
      # ▼カスタムアクション（この段階独自の選択肢）
      custom_actions:
        # 選択肢1: 唇をかたく閉じる（確定失敗だが、次ターンにボーナス）
        - id: seal_lips
          label: "唇をかたく閉じる"
          description: "キスを防ごうと唇を固く結ぶ。"
          
          # 成功判定の設定
          success_check:
            type: fixed  # 固定確率
            rate: 0  # 0% = 確定失敗
          
          # 失敗時の効果（確定で発動）
          on_failure:
            effects:
              - type: message
                text: |
                  唇を固く閉じるが、サキュバスは構わず唇に吸い付いてくる。
                  「んー……可愛い抵抗ね♡」
              - type: stage_progress
                amount: 1  # 1段階進行
              - type: set_flag
                flag: lips_sealed_bonus
                value: true  # 次ターンにボーナスフラグ
            
            enemy_reaction: "「固くしても無駄よ……すぐに蕩けちゃうんだから♡」"
        
        # 選択肢2: 顔を背ける（別ルートに分岐）
        - id: turn_away
          label: "顔を背けて拒絶する"
          description: "唇が触れる寸前、顔を横に向けて避ける。"
          
          success_check:
            type: fixed
            rate: 100  # 確定成功（分岐用）
          
          on_success:
            effects:
              - type: message
                text: |
                  唇が触れる寸前、必死に顔を背けた。
                  サキュバスは不満げに頬を膨らませると、冷徹な目で見下ろしてくる。
                  「……あら、私の愛を受け取れないの？
                  　いいわ。なら、力ずくで大人しくさせてあげる」
              
              # 別のシーケンスへ分岐
              - type: switch_bind_sequence
                target: succubus_tail_bind
                stage: 0  # 新シーケンスの最初から
            
            enemy_reaction: "「……そう。なら別の方法で愛してあげるわ」"
        
        # 選択肢3: 唇が触れる瞬間魔法を放つ（魔力参照、高リスク高リターン）
        - id: cast_counter_spell
          label: "魔法で反撃する"
          description: "至近距離から魔法を放ち、押し返す。"
          
          # この選択肢の表示条件
          requirements:
            - type: stat_check
              stat: mp
              operator: ">="
              value: 20  # MP20以上必要
          
          success_check:
            type: stat_based  # ステータス参照
            formula: "知性 * 0.8 + 正気 * 0.2"  # 知性80%、正気20%で計算
            # 例: 知性60、正気50なら → 60*0.8 + 50*0.2 = 58%の成功率
          
          # コスト
          cost:
            mp: 20
          
          on_success:
            effects:
              - type: message
                text: |
                  唇が触れる瞬間、魔法の光が爆ぜた！
                  サキュバスは悲鳴を上げて吹き飛び、体が自由になる！
              - type: deal_damage
                target: enemy
                damage: 30  # 敵にダメージ
              - type: escape_bind  # 拘束から即座脱出
            
            enemy_reaction: "「きゃああっ！？ こ、この……っ！」"
          
          on_failure:
            effects:
              - type: message
                text: |
                  魔法を放とうとしたが、サキュバスの唇が先に触れた。
                  魔力が乱れ、何も起こらない……！
              - type: modify_stat
                stat: pt
                operator: "+"
                value: 30  # 失敗でPT大幅上昇
              - type: stage_progress
                amount: 2  # 2段階進行（ペナルティ）
            
            enemy_reaction: "「あらあら、焦っちゃって♡ そんなに私のキスが欲しかったの？」"
        
        # 選択肢4: フラグがあれば成功率上昇
        - id: desperate_push
          label: "渾身の力で押し返す"
          description: "全身全霊で拘束を振りほどこうとする。"
          
          success_check:
            type: stat_based
            base_rate: 30  # 基礎成功率30%
            formula: "筋力 * 0.5 + 正気 * 0.3"
            modifiers:
              # フラグによるボーナス
              - type: flag_bonus
                flag: lips_sealed_bonus
                bonus: 25  # 前ターンで唇を閉じていたら+25%
          
          on_success:
            effects:
              - type: message
                text: "渾身の力で拘束を振りほどいた！"
              - type: stage_regress
                amount: 2  # 2段階改善
            
            enemy_reaction: "「ちょ、ちょっと！ そんなに嫌なの！？」"
          
          on_failure:
            effects:
              - type: message
                text: "力を振り絞るが、拘束は解けない……。"
              - type: modify_stat
                stat: pt
                operator: "+"
                value: 15
              - type: stage_progress
                amount: 1
            
            enemy_reaction: "「無駄よ……観念しなさい♡」"
    
    # ▼最終段階（ループ）
    - stage: 3
      description: |
        サキュバスの唇があなたの唇に重なる。
        柔らかく、甘く、そして恐ろしいほど心地よい感触。
        触れた場所から、急速に力が抜けていく……。
      
      # ループ時の追加効果
      loop_effects:
        - type: modify_stat
          stat: pt
          operator: "+"
          value: 20
        - type: modify_stat
          stat: hp
          operator: "-"
          value: 5
        - type: message
          text: "精気を吸い取られている……！"
      
      # 最終段階でもカスタムアクション可能
      custom_actions:
        - id: bite_lip
          label: "唇を噛んで抵抗する"
          description: "サキュバスの唇を噛んで怯ませる。"
          
          success_check:
            type: stat_based
            formula: "正気 * 0.6 + 筋力 * 0.2"
          
          on_success:
            effects:
              - type: message
                text: |
                  思い切り唇を噛んだ！
                  サキュバスが悲鳴を上げて離れた！
              - type: deal_damage
                target: enemy
                damage: 15
              - type: stage_regress
                amount: 2
            
            enemy_reaction: "「いったぁい！ ひどい……！」"
          
          on_failure:
            effects:
              - type: message
                text: "噛もうとしたが、唇が柔らかすぎて力が入らない……。"
              - type: modify_stat
                stat: pt
                operator: "+"
                value: 25
            
            enemy_reaction: "「んふふ……可愛い抵抗♡」"


# 派生シーケンス例
bind_sequence:
  id: succubus_tail_bind
  
  metadata:
    name: "サキュバスの尻尾拘束"
    description: "尻尾で締め上げられる"
  
  config:
    base_difficulty: 80  # 前より難易度上昇
    escape_target: battle_resume
    loop_damage:
      hp: 15  # 物理ダメージ主体
      pt: 5
  
  stages:
    - stage: 0
      description: "サキュバスの尻尾がしなやかに伸び、足元に巻き付いてきた！"
      enemy_reactions:
        on_player_resist_fail: "「逃がさないわよ……」"
    
    - stage: 1
      description: |
        尻尾がずるりと這い上がり、腰のあたりまでを強く締め付ける。
        万力のような力で、身動きが取れない！
      enemy_reactions:
        on_player_resist_success: "「あら、まだ抵抗するの？」"
    
    - stage: 2
      description: "肩口まで完全に巻き付かれた。サキュバスは愉悦の表情で、捕らえた獲物を撫で回している。"
      player_texts:
        on_resist_success: "全身の骨が軋む音を聞きながら、必死に拘束を解こうともがく！"
      enemy_reactions:
        on_player_resist_success: "「いやっ！ 私の尻尾を引っ張らないで！」"
    
    - stage: 3
      description: |
        全身を尻尾に締め上げられ、呼吸すらままならない。
        意識が遠のく中、サキュバスの高笑いだけが響いている。
      
      loop_effects:
        - type: modify_stat
          stat: hp
          operator: "-"
          value: 15
        - type: message
          text: "締め付けられて苦しい……！"
```

---

【カスタムアクション詳細仕様】

カスタムアクションは、拘束シーケンスの各ステージに固有の選択肢を追加する機能。

**基本構造:**
```yaml
custom_actions:
  - id: unique_action_id
    label: "選択肢のラベル"
    description: "選択肢の説明文"
    
    # 表示条件（省略可）
    requirements: [...]
    
    # コスト（省略可）
    cost:
      mp: 値
      hp: 値
      item: アイテムID
    
    # 成功判定
    success_check:
      type: fixed | stat_based | formula
      # 各種パラメータ
    
    # 成功時
    on_success:
      effects: [...]
      enemy_reaction: "テキスト"
    
    # 失敗時
    on_failure:
      effects: [...]
      enemy_reaction: "テキスト"
```

**成功判定の種類:**

1. **固定確率（fixed）**
```yaml
success_check:
  type: fixed
  rate: 75  # 75%で成功
```

2. **ステータス参照（stat_based）**
```yaml
success_check:
  type: stat_based
  base_rate: 30  # 基礎成功率
  formula: "筋力 * 0.6 + 正気 * 0.4"  # ステータスから計算
  # 上記の例: 筋力50、正気60なら → 50*0.6 + 60*0.4 = 54%
  
  # 修正値（省略可）
  modifiers:
    - type: flag_bonus
      flag: some_flag
      bonus: 20  # フラグがあれば+20%
    - type: item_bonus
      item: magic_charm
      bonus: 15  # アイテム所持で+15%
    - type: status_penalty
      status: weakened
      penalty: -25  # 状態異常で-25%
```

3. **複雑な計算式（formula）**
```yaml
success_check:
  type: formula
  expression: "min(95, max(5, (知性 + 正気) / 2 + 器用 * 0.3))"
  # 複雑な計算も可能（最小5%、最大95%）
```

**エフェクトの種類:**

拘束シーケンス内で使える特殊エフェクト:
- `stage_progress`: ステージ進行
  - `amount`: 進行段階数（負数で後退）
- `stage_regress`: ステージ後退（stage_progressの別名）
  - `amount`: 後退段階数
- `escape_bind`: 拘束から即座脱出
- `deal_damage`: ダメージを与える
  - `target`: enemy | self
  - `damage`: ダメージ量
  - `type`: physical | magic | pt
- `modify_stat`: ステータス変更
- `set_flag`: フラグ設定
- `switch_bind_sequence`: 別シーケンスへ切替
  - `target`: シーケンスID
  - `stage`: 開始ステージ（省略時0）
- `message`: メッセージ表示

**基本コマンドの上書き:**

`default_choices_override` セクションで、3つの基本コマンドの動作を変更可能:

```yaml
default_choices_override:
  resist:  # 通常の「抵抗」
    enabled: true | false  # 選択可能かどうか
    override_result: auto_success | auto_fail  # 結果を上書き
    success_rate_modifier: +10 | -20  # 成功率の補正
    reason: "上書き時の理由テキスト"
  
  resist_hard:  # 「全力抵抗」
    # 同上
  
  wait:  # 「抵抗しない」
    # 同上
```

使用例:
```yaml
# 特定ステージで通常抵抗を無効化
default_choices_override:
  resist:
    enabled: false
    reason: "体が痺れて動けない……！"
  
  resist_hard:
    enabled: true
    success_rate_modifier: -30  # より困難に
```

---

【プレイヤーキャラクター】

プレイヤーの基本ステータス:

```yaml
player:
  # 戦闘ステータス
  combat_stats:
    sp: 100  # シールドポイント（マジックシールドの耐久値）
    sp_max: 100
    hp: 80   # ヒットポイント（体力、0でゲームオーバー）
    hp_max: 80
    mp: 50   # マジックポイント（魔法のリソース）
    mp_max: 50
    pt: 0    # Pleasure Tolerance（快楽許容値、上限を超えると絶頂）
    pt_max: 100
  
  # 判定用ステータス（1-100）
  ability_stats:
    正気: 70
    筋力: 50
    集中: 60
    知性: 65
    知識: 55
    器用: 45
  
  # 初期装備・スキル
  equipment:
    weapon: iron_sword
    armor: leather_vest
  
  spells:
    - fire_ball
    - ice_shard
```

---

【魔法・スキル定義】

```yaml
spell:
  id: fire_ball
  
  metadata:
    name: "ファイアボール"
    description: "炎の球を放つ基本魔法"
  
  cost:
    mp: 15
  
  effects:
    - type: deal_damage
      damage_type: magic
      element: fire
      base: 30
      scaling:
        stat: 知性
        ratio: 0.5
  
  text:
    cast: "{{caster}}は火の玉を放った！"
    hit: "{{target}}に{{damage}}のダメージ！"
    miss: "{{target}}は避けた！"


spell:
  id: charm_touch
  
  metadata:
    name: "魅了の接触"
    description: "触れた相手を魅了する"
  
  cost:
    mp: 20
  
  effects:
    - type: inflict_status
      status: charm
      duration: 1
      chance: 70  # 70%の確率で成功
  
  text:
    cast: "{{caster}}が妖しい光を放った……。"
    success: "{{target}}は魅了された！"
    resist: "{{target}}は誘惑を振り切った！"
```

---

【状態異常定義】

```yaml
status_effect:
  id: charm
  
  metadata:
    name: "魅了"
    description: "行動不能状態"
  
  effects:
    - type: prevent_action
      duration: 1  # 1ターン
  
  tick_effects: []  # ターン経過時の効果なし
  
  text:
    inflict: "{{target}}は魅了された！"
    expire: "{{target}}の魅了が解けた。"


status_effect:
  id: poison
  
  metadata:
    name: "毒"
    description: "継続ダメージを受ける"
  
  duration: 3  # 3ターン継続
  
  tick_effects:
    - type: deal_damage
      damage_type: poison
      amount: 10
  
  text:
    inflict: "{{target}}は毒を受けた！"
    tick: "{{target}}は毒のダメージを受けた！"
    expire: "{{target}}の毒が抜けた。"
```

---

【プラグインシステム】

カスタムアクションやロジックを追加するためのプラグイン機構。

**プラグイン配置場所:**
```
mods/
  your_mod/
    plugins/
      custom_teleport.py
      special_battle.py
    data/
      nodes.yaml
      enemies.yaml
```

**プラグイン記述例:**

```python
# plugins/custom_teleport.py

from engine.core import ActionPlugin

class CustomTeleportAction(ActionPlugin):
    """カスタムテレポート動作"""
    
    # YAMLで指定する type 名
    action_type = "custom_teleport"
    
    def execute(self, context, params):
        """
        実行メソッド
        
        Args:
            context: ゲームコンテキスト（プレイヤー状態、現在ノード等）
            params: YAMLから渡されたパラメータ辞書
        
        Returns:
            実行結果（メッセージ等）
        """
        target = params.get("target")
        cost = params.get("mp_cost", 20)
        
        # MP不足チェック
        if context.player.mp < cost:
            return context.message("MPが足りない！")
        
        # コスト消費
        context.player.mp -= cost
        
        # エフェクト再生
        context.add_effect("teleport_flash")
        
        # ノード移動
        context.navigate_to(target)
        
        return context.message(f"{target}へテレポートした！")


# 自動登録（エンジンがロード時に認識）
```

**YAMLでの使用:**

```yaml
actions:
  - id: emergency_teleport
    type: custom_teleport  # プラグインのaction_type
    label: "緊急脱出"
    
    # プラグインへ渡すパラメータ
    params:
      target: town_square
      mp_cost: 30
    
    requirements:
      - type: stat_check
        stat: mp
        operator: ">="
        value: 30
```

---

【ファイル構成】

MODは以下のディレクトリ構造で構成される:

```
mods/
  your_mod_name/
    mod.yaml           # MODメタ情報
    
    data/
      nodes/           # ノード定義（場所ごとにファイル分割可）
        bedroom.yaml
        hallway.yaml
        boss_room.yaml
      
      enemies/         # 敵定義
        common.yaml
        bosses.yaml
      
      items/           # アイテム定義
        consumables.yaml
        equipment.yaml
      
      spells/          # 魔法・スキル定義
        player_spells.yaml
        enemy_spells.yaml
      
      sequences/       # 拘束シーケンス定義
        succubus.yaml
        slime.yaml
      
      pools/           # アイテム・敵プール定義
        loot_pools.yaml
        enemy_pools.yaml
    
    assets/
      images/          # 画像ファイル
      audio/           # 音声ファイル
    
    plugins/           # カスタムプラグイン（Python）
      __init__.py
      custom_actions.py
      custom_conditions.py
    
    scripts/           # 複雑なイベントスクリプト
      special_event.py
```

**mod.yaml 例:**

```yaml
mod:
  id: dungeon_of_lust
  version: "1.0.0"
  
  metadata:
    name: "欲望のダンジョン"
    author: "YourName"
    description: "魔物に囚われし探索者の物語"
    tags: [fantasy, adult, dungeon_crawler]
  
  dependencies:
    engine_version: ">=2.0.0"
    required_mods: []
  
  entry_point: bedroom  # 開始ノード
```

---

【ゲームフロー】

```
メインメニュー
├─ MOD選択
│   ├─ はじめから（新規セーブ作成）
│   ├─ 続きから（セーブロード）
│   └─ 設定
│
└─ テストプレイモード
    ├─ 敵戦闘テスト（任意の敵と戦闘）
    ├─ シーケンステスト（任意の拘束シーケンス）
    └─ ノードテスト（任意のノードから開始）
```

---

【MOD Creator アプリケーション（GUI）】

MOD作成を支援する専用GUIツール。YAMLを直接編集しなくても、視覚的にMODを作成できる。

**主な機能:**
1. **ノードエディタ**
   - ドラッグ&ドロップでノード作成
   - フローチャート形式でノード間の繋がりを可視化
   - アクション・条件をフォームで入力

2. **敵エディタ**
   - ステータス設定
   - ビヘイビアツリーの視覚的構築
   - テキストバリエーション管理

3. **シーケンスエディタ**
   - ステージごとの設定
   - カスタムアクションの追加・編集
   - 基本コマンド上書きの設定
   - テキスト・分岐の管理
   - プレビュー機能

4. **バリデーション**
   - リアルタイムエラーチェック
   - 参照整合性の検証（存在しないノードIDへのリンク等）
   - 型チェック
   - 成功率計算式の検証

5. **プレビュー・テスト**
   - エディタ内でMODを即座にテストプレイ
   - デバッグログ表示
   - ステータス・フラグの状態確認

6. **エクスポート**
   - 完成したMODをYAML形式でエクスポート
   - 配布用パッケージング

**アプリは裏でYAMLを生成。上級者は生成されたYAMLを直接編集して、より複雑なロジックを実装可能。**

---
