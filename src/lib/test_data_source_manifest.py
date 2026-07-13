from test_pipeline_fixtures import (
    characteristic_data_source_ids,
    data_source_root,
    load_data_source_manifest,
)


def test_manifest_lists_fourteen_candidates():
    entries = load_data_source_manifest()
    assert len(entries) == 14
    assert entries[0]["id"] == "01"
    assert (data_source_root() / "manifest.json").is_file()


def test_characteristic_test_ids_are_subset():
    assert characteristic_data_source_ids() == ["01", "07", "14"]