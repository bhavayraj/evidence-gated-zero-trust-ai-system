from prime_checker import is_prime


def test_prime_numbers():
    assert is_prime(2) == True
    assert is_prime(7) == True
    assert is_prime(13) == True


def test_non_prime_numbers():
    assert is_prime(1) == False
    assert is_prime(0) == False
    assert is_prime(4) == False
