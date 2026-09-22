def is_prime(n: int) -> bool:
    """Determine if an integer n is a prime number."""
    if not isinstance(n, int) or n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def run_tests():
    """Run comprehensive test cases including edge cases."""
    edge_cases = [
        (-10, False),
        (-1, False),
        (0, False),
        (1, False),
        (2, True),
        (3, True),
        (4, False),
        (5, True),
        (9, False),
        (13, True),
        (25, False),
        (29, True),
        (97, True),
        (100, False),
    ]
    for val, expected in edge_cases:
        result = is_prime(val)
        assert result == expected, f"Test failed for n={val}: expected {expected}, got {result}"
    print("All test cases passed successfully.")


if __name__ == "__main__":
    run_tests()
