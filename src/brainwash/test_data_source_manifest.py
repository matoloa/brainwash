from test_pipeline_fixtures import (
    characteristic_data_source_ids,
    data_source_entry,
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


def test_characteristic_entries_have_metadata():
    for cid in characteristic_data_source_ids():
        entry = data_source_entry(cid)
        assert entry is not None
        assert entry.get("n_sweeps") == 1080
        assert entry.get("n_stims") == 1