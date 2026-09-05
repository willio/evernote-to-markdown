"""Allow ``python -m enex2writer``."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
