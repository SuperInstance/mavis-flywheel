"""Test runner for mavis-flywheel."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/workspace/repos/mavis-flywheel")

from mavis_flywheel.flywheel import (
    Flywheel, Experiment, polyformality_score, hash_response,
    fnv1a_64, call_mock, call_deepinfra, FLYWHEEL_BASE,
)

results = []
failures = []


def test(name, func):
    try:
        func()
        results.append((name, "PASS"))
    except AssertionError as e:
        results.append((name, f"FAIL: {e}"))
        failures.append(name)
    except Exception as e:
        results.append((name, f"ERROR: {type(e).__name__}: {e}"))
        failures.append(name)


def t_fnv1a():
    assert f"0x{fnv1a_64('café Δ 日本語'):016x}" == "0x24a555471370b18d"


def t_polyformality_identical():
    """Identical responses → score 1.0."""
    r = ["the substrate walker counts refusals as map",
         "the substrate walker counts refusals as map"]
    score = polyformality_score(r)
    assert score == 1.0


def t_polyformality_different():
    """Different responses → low score."""
    r = ["the substrate walker counts refusals as map",
         "an entirely different sentence about quantum physics"]
    score = polyformality_score(r)
    assert 0 <= score <= 1.0
    assert score < 0.5


def t_polyformality_empty():
    assert polyformality_score([]) == 0.0


def t_hash_response():
    h = hash_response("question", "answer")
    assert len(h) == 16


def t_mock_voice():
    z = call_mock("topic", voice="zai")
    assert "substrate walker" in z.lower()
    q = call_mock("topic", voice="qwen")
    assert "z" in q.lower() or "cartography" in q.lower()
    k = call_mock("topic", voice="kimi")
    assert len(k) > 0


def test_flywheel_init():
    """Flywheel creates directories."""
    with tempfile.TemporaryDirectory() as td:
        fw = Flywheel(base=Path(td), use_real_apis=False)
        assert (Path(td) / "experiments").exists()
        assert (Path(td) / "results").exists()
        assert (Path(td) / "queue").exists()


def test_flywheel_queue():
    with tempfile.TemporaryDirectory() as td:
        fw = Flywheel(base=Path(td), use_real_apis=False)
        fw.add_to_queue("what is canon?")
        fw.add_to_queue("what is a witness log?")
        questions = fw.load_queue()
        assert len(questions) == 2


def test_flywheel_run_one():
    with tempfile.TemporaryDirectory() as td:
        fw = Flywheel(base=Path(td), use_real_apis=False)
        result = fw.run_one("the cell refuses to open")
        assert result["question"] == "the cell refuses to open"
        assert "polyformality" in result
        assert "zai" in result["responses"]
        # Saves to results dir
        assert any(Path(td).glob("results/*.json"))


def test_flywheel_run_queue():
    with tempfile.TemporaryDirectory() as td:
        fw = Flywheel(base=Path(td), use_real_apis=False)
        fw.add_to_queue("Q1")
        fw.add_to_queue("Q2")
        fw.add_to_queue("Q3")
        results = fw.run_queue(limit=2)
        assert len(results) == 2
        # Queue cleared after processing
        assert len(fw.load_queue()) == 0


def test_flywheel_stats():
    with tempfile.TemporaryDirectory() as td:
        fw = Flywheel(base=Path(td), use_real_apis=False)
        fw.run_one("test question")
        stats = fw.stats()
        assert stats["runs"] == 1
        assert "canon_worthy" in stats


def test_experiment_id_format():
    exp = Experiment("test", ["zai", "qwen"])
    assert exp.experiment_id.startswith("exp-")
    assert len(exp.experiment_id) > 10


def test_experiment_run_with_mocks():
    exp = Experiment("question", ["zai", "qwen", "kimi"], use_real_apis=False)
    result = exp.run()
    assert len(result["responses"]) == 3
    # All mocks should produce content
    for m, r in result["responses"].items():
        assert r is not None
        assert len(r) > 20


test("test_fnv1a", t_fnv1a)
test("test_polyformality_identical", t_polyformality_identical)
test("test_polyformality_different", t_polyformality_different)
test("test_polyformality_empty", t_polyformality_empty)
test("test_hash_response", t_hash_response)
test("test_mock_voice", t_mock_voice)
test("test_flywheel_init", test_flywheel_init)
test("test_flywheel_queue", test_flywheel_queue)
test("test_flywheel_run_one", test_flywheel_run_one)
test("test_flywheel_run_queue", test_flywheel_run_queue)
test("test_flywheel_stats", test_flywheel_stats)
test("test_experiment_id_format", test_experiment_id_format)
test("test_experiment_run_with_mocks", test_experiment_run_with_mocks)

print("\n=== mavis-flywheel test results ===")
for name, status in results:
    print(f"  {status:60} {name}")

print(f"\n{len(results) - len(failures)}/{len(results)} passed")
if failures:
    sys.exit(1)
