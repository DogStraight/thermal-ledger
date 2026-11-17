"""PyInstaller entry point (package-relative imports need a real launcher)."""

from thermal_ledger.app import main

if __name__ == "__main__":
    raise SystemExit(main())
