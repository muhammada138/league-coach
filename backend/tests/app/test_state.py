from app.state import get_routing

def test_get_routing_americas():
    assert get_routing("na1") == "americas"
    assert get_routing("br1") == "americas"
    assert get_routing("la1") == "americas"
    assert get_routing("la2") == "americas"

def test_get_routing_europe():
    assert get_routing("euw1") == "europe"
    assert get_routing("eun1") == "europe"
    assert get_routing("tr1") == "europe"
    assert get_routing("ru") == "europe"

def test_get_routing_asia():
    assert get_routing("kr") == "asia"
    assert get_routing("jp1") == "asia"

def test_get_routing_sea():
    assert get_routing("oc1") == "sea"
    assert get_routing("ph2") == "sea"
    assert get_routing("sg2") == "sea"
    assert get_routing("th2") == "sea"
    assert get_routing("tw2") == "sea"
    assert get_routing("vn2") == "sea"

def test_get_routing_case_insensitivity():
    assert get_routing("NA1") == "americas"
    assert get_routing("EuW1") == "europe"
    assert get_routing("KR") == "asia"
    assert get_routing("oH2") == "americas" # because oh2 doesn't exist, it defaults to americas. Wait let's just test a known valid region in caps.
    assert get_routing("pH2") == "sea"

def test_get_routing_default():
    assert get_routing("unknown_region") == "americas"
    assert get_routing("") == "americas"
    assert get_routing("12345") == "americas"
