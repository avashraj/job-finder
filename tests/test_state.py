from job_finder.state import load_seen, save_seen


def test_load_missing_file_returns_empty(tmp_path):
    assert load_seen(str(tmp_path / "nope.json")) == set()


def test_save_then_load_round_trips(tmp_path):
    p = str(tmp_path / "seen.json")
    save_seen(p, {"b", "a", "c"})
    assert load_seen(p) == {"a", "b", "c"}


def test_saved_file_is_sorted_list(tmp_path):
    import json
    p = str(tmp_path / "seen.json")
    save_seen(p, {"b", "a"})
    with open(p) as f:
        assert json.load(f) == ["a", "b"]
