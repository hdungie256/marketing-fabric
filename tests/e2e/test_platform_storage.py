from scripts import check_storage


def test_delta_operations_on_seaweedfs():
    assert check_storage.main() == 0
