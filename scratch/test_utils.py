from utils import is_palindrome


def test_basic():
    assert is_palindrome("racecar") == True


def test_case_and_spaces():
    assert is_palindrome("Nurses Run") == True
