"""Shim for backtester."""
from signal_engine.backtester import *

if __name__ == "__main__":
    import sys

    try:
        from signal_engine.backtester import main
    except ImportError:
        main = None

    if main is not None:
        main()
