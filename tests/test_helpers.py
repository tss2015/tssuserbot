from utils.helpers import human_seconds

def test_human_seconds():
    assert human_seconds(5) == "5s"
    assert human_seconds(65) == "1m 5s"
