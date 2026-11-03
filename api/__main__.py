"""Allow ``python -m api``; prefer ``python -m api.cli``."""

from api.cli import main

raise SystemExit(main())
