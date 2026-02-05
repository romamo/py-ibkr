from py_ibkr import parse


def test_smoke():
    print("Smoke test starting...")
    # Verify we can at least import and see the parse function
    assert callable(parse)
    print("Smoke test passed.")


if __name__ == "__main__":
    test_smoke()
