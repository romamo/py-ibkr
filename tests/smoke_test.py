from py_ibkr import parse
from py_ibkr.cli import app


def test_smoke():
    print("Smoke test starting...")
    # Verify we can at least import and see the parse function
    assert callable(parse)
    # The CLI (and its treaty dependency) must import and register its command
    assert "download" in {str(path) for path in app.commands}
    print("Smoke test passed.")


if __name__ == "__main__":
    test_smoke()
