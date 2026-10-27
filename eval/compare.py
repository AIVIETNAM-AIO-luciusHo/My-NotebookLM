"""So sánh ghép cặp hai report.json bằng McNemar chính xác hai phía.

Chạy: python -m eval.compare A.json B.json [--metric hit@4]
b = A đúng, B sai; c = A sai, B đúng. n=b+c; p = min(1, 2*P(X<=min(b,c))), X~Bin(n, 1/2).
"""
import argparse
import json
import sys
from math import comb


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2**n)


def load(path: str) -> dict[str, dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Không tìm thấy file: {path}")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        raise ValueError(f"File không phải JSON hợp lệ hoặc không đọc được: {path} ({e})")
    pq = data.get("per_question") if isinstance(data, dict) else None
    if not isinstance(pq, list) or not pq or not all(isinstance(q, dict) and "id" in q for q in pq):
        raise ValueError(f"Thiếu 'per_question' (danh sách có 'id') trong: {path}")
    return {q["id"]: q for q in pq}


def compare(a: dict, b: dict, metrics: list[str] | None = None) -> list[tuple[str, int, int, float]]:
    if set(a) != set(b):
        raise ValueError(f"Hai tập id khác nhau: chỉ ở A={sorted(set(a) - set(b))}, chỉ ở B={sorted(set(b) - set(a))}")
    first = next(iter(a.values()))
    metrics = metrics or [k for k, v in first.items() if k.startswith("hit@") and isinstance(v, bool)]
    if not metrics:
        raise ValueError("Report không có metric hit@k kiểu đúng/sai nào.")
    for m in metrics:
        if any(not isinstance(r.get(m), bool) for r in (*a.values(), *b.values())):
            raise ValueError(f"Metric '{m}' thiếu hoặc không phải đúng/sai trong per_question.")
    rows = []
    for m in metrics:
        bb = sum(a[i][m] and not b[i][m] for i in a)
        cc = sum(b[i][m] and not a[i][m] for i in a)
        rows.append((m, bb, cc, mcnemar_exact(bb, cc)))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--metric", action="append")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:  # argparse thoát 2 với thông báo của nó; giữ nhất quán
        return int(e.code or 0)
    try:
        rows = compare(load(args.a), load(args.b), args.metric)
    except ValueError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        return 2
    print(f"{'metric':<8} {'b(A+,B-)':>9} {'c(A-,B+)':>9} {'p':>8}")
    for m, b, c, p in rows:
        print(f"{m:<8} {b:>9} {c:>9} {p:>8.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
