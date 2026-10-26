"""Sinh eval/review_sample.md: 6 câu phân tầng (2/type), seed cố định random.Random(1)."""

import random
from pathlib import Path

from eval.check_quotes import SEP, load_golden

TYPES = ("fact", "number", "multi-hop")


def pick(rows: list[dict]) -> list[dict]:
    rng = random.Random(1)
    return [r for t in TYPES for r in rng.sample([x for x in rows if x["type"] == t], 2)]


if __name__ == "__main__":
    out = ["# Mẫu duyệt golden (6/30)", "",
           "Đánh dấu [x] nếu đáp án đúng VÀ trích dẫn/trang đúng. Cần >= 5/6 để coi số đo là mốc gốc (AC-9).", ""]
    for r in pick(load_golden()):
        out += [f"## {r['id']} ({r['type']}) — `{r['doc']}`", "",
                f"- [ ] **Câu hỏi:** {r['question']}",
                f"- **Đáp án:** {r['answer']}",
                f"- **Trang (đánh số từ 1):** {', '.join(map(str, r['gold_pages']))}"]
        out += [f"- **Trích dẫn:** \"{q}\"" for q in r["gold_quote"].split(SEP)] + [""]
    Path(__file__).with_name("review_sample.md").write_text("\n".join(out), encoding="utf-8")
