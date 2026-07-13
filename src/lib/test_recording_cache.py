from brainwash_ui import recording_cache


def test_output_cache_key():
    assert recording_cache.output_cache_key(bin_active=False) == "output"
    assert recording_cache.output_cache_key(bin_active=True) == "output_bin"


def test_output_parquet_path():
    path = recording_cache.output_parquet_path("/cache", "rec1", bin_active=False)
    assert path == "/cache/rec1_output.parquet"
    assert recording_cache.output_parquet_path("/cache", "rec1", bin_active=True) == "/cache/rec1_output_bin.parquet"