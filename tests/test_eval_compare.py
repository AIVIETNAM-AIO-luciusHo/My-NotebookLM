import json
import math

import pytest

from eval.compare import compare, main, mcnemar_exact


def test_hand_calc_b5_c1():
    # n=6, P(X<=1)=(C(6,0)+C(6,1))/2^6=7/64; p=2*7/64=14/64=0.21875
    assert mcnemar_exact(5, 1) == pytest.approx(0.21875)


def test_hand_calc_b6_c0():
    # n=6, P(X<=0)=1/64; p=2/64=0.03125
    assert mcnemar_exact(6, 0) == pytest.approx(0.03125)


def test_symmetric():
    assert mcnemar_exact(2, 7) == mcnemar_exact(7, 2)


def test_zero_discordant_is_one():
    assert mcnemar_exact(0, 0) == 1.0


def test_tie_capped_at_one():
    assert mcnemar_exact(3, 3) == 1.0


def test_matches_binomial_sum():
    b, c = 4, 12
    n = b + c
    exp = 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    assert mcnemar_exact(b, c) == pytest.approx(exp)


def _q(vals):
    return {f"q{i}": {"id": f"q{i}", "hit@4": v} for i, v in enumerate(vals)}


def test_compare_counts():
    a = _q([True, True, False, False])
    b = _q([True, False, True, True])
    assert compare(a, b) == [("hit@4", 1, 2, mcnemar_exact(1, 2))]


def test_different_ids_raise():
    with pytest.raises(ValueError, match="khác nhau"):
        compare(_q([True]), _q([True, False]))


def test_cli_same_file_p_one(tmp_path, capsys):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"per_question": list(_q([True, False]).values())}))
    assert main([str(f), str(f)]) == 0
    assert "1.0000" in capsys.readouterr().out


def test_cli_id_mismatch_exit_2(tmp_path):
    f, g = tmp_path / "a.json", tmp_path / "b.json"
    f.write_text(json.dumps({"per_question": list(_q([True]).values())}))
    g.write_text(json.dumps({"per_question": list(_q([True, True]).values())}))
    assert main([str(f), str(g)]) == 2


def _w(tmp_path, name, text):
    f = tmp_path / name
    f.write_text(text)
    return str(f)


def test_cli_missing_file(tmp_path, capsys):
    ok = _w(tmp_path, "a.json", json.dumps({"per_question": list(_q([True]).values())}))
    assert main([ok, str(tmp_path / "none.json")]) == 2
    assert "Không tìm thấy file" in capsys.readouterr().err


def test_cli_broken_json(tmp_path, capsys):
    bad = _w(tmp_path, "b.json", "{khong phai json")
    assert main([bad, bad]) == 2
    assert "không phải JSON" in capsys.readouterr().err


def test_cli_no_per_question(tmp_path, capsys):
    bad = _w(tmp_path, "c.json", json.dumps({"metrics": {}}))
    assert main([bad, bad]) == 2
    assert "per_question" in capsys.readouterr().err


def test_cli_bad_metric(tmp_path, capsys):
    ok = _w(tmp_path, "a.json", json.dumps({"per_question": list(_q([True]).values())}))
    assert main([ok, ok, "--metric", "hit@99"]) == 2
    assert "hit@99" in capsys.readouterr().err
