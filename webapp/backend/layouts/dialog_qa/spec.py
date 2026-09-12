from layouts._registry import Capacity, LayoutSpec


def _prepare(content: dict, ctx: dict) -> dict:
    """発言を「質問と回答の組」にまとめる。

    A を質問、B を回答として順に組にする。吹き出しの往復ではなく
    Q&A の一覧として読ませるため、組の単位で 1 ブロックにする。
    """
    pairs, current = [], None
    for line in content.get("lines") or []:
        if (line.get("speaker") or "A").upper() == "A":
            if current:
                pairs.append(current)
            current = {"q": line.get("text") or "", "a": ""}
        else:
            if current is None:
                # 回答から始まっている場合も落とさず拾う
                current = {"q": "", "a": ""}
            current["a"] = (current["a"] + " " + (line.get("text") or "")).strip()
    if current:
        pairs.append(current)
    return {"pairs": pairs}


SPEC = LayoutSpec(
    id="dialog_qa",
    label="Q&A",
    type_id="dialog",
    when_to_use=(
        "よくある質問に答える形で整理するとき。掛け合いの流れではなく、"
        "質問と答えの組を一覧で読ませたい場面に使う。A に質問、B に回答を書く。"
    ),
    capacity=Capacity(min=2, max=6, ideal=(2, 4)),
    veil=0.85, orbs=1, phase="P1", prepare=_prepare,
    sample={"lines": [
        {"speaker": "A", "text": "手順書を作る時間が取れません。どうすればいいですか？"},
        {"speaker": "B", "text": "まず 1 工程だけ、写真 3 枚で作ってみてください。全部を一度に作らないのがコツです。"},
        {"speaker": "A", "text": "作っても読まれない気がします。"},
        {"speaker": "B", "text": "読ませる前提をやめて、迷ったときだけ開く場所に置くと使われ始めます。"},
    ]},
)
