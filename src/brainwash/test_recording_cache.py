from brainwash_ui import recording_cache


def test_output_cache_key():
    assert recording_cache.output_cache_key(bin_active=False) == "output"
    assert recording_cache.output_cache_key(bin_active=True) == "output_bin"


def test_output_parquet_path():
    path = recording_cache.output_parquet_path("/cache", "rec1", bin_active=False)
    assert path == "/cache/rec1_output.parquet"
    assert recording_cache.output_parquet_path("/cache", "rec1", bin_active=True) == "/cache/rec1_output_bin.parquet"


def test_mean_and_filter_paths():
    assert recording_cache.mean_parquet_path("/cache", "rec1") == "/cache/rec1_mean.parquet"
    assert recording_cache.filter_parquet_path("/cache", "rec1") == "/cache/rec1_filter.parquet"


def test_timepoints_and_data_paths():
    assert recording_cache.timepoints_parquet_path("/tp", "rec1") == "/tp/rec1.parquet"
    assert recording_cache.data_parquet_path("/data", "rec1") == "/data/rec1.parquet"


def test_group_mean_parquet_path():
    assert recording_cache.group_mean_parquet_path("/cache", "G1") == "/cache/group_G1_mean.parquet"
    assert (
        recording_cache.group_mean_parquet_path("/cache", "G1", level_suffix="_subject")
        == "/cache/group_G1_subject_mean.parquet"
    )


def test_timepoints_cache_key_constant():
    assert recording_cache.TIMEPOINTS_CACHE_KEY == "timepoints"