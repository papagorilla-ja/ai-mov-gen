# ナレーション原稿

index.html の `.slide` 要素(1始まり、出現順)と同じ数だけ `## Scene N` を用意する。
各シーンは ```yaml フェンスで `default_speaker` と `lines` を記述する。

- `lines` の要素が文字列なら `default_speaker` が話者になる。
- 話者を行ごとに変えたい場合(対話など)は `{speaker: ..., text: ...}` の形で書く。
- 利用可能な話者名の例: 玄野武宏、四国めたん、ずんだもん 等(VOICEVOXの /speakers で確認可能)。

## Scene 1
```yaml
default_speaker: 玄野武宏
lines:
  - "(ここにナレーションを記入)"
```
