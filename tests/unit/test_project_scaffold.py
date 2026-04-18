from pathlib import Path


def test_tmp_db_path_fixture_shape(tmp_db_path: Path) -> None:
    assert tmp_db_path.name == "market_universe.sqlite"
