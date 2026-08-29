"""Shim for backtester."""
from signal_engine.backtester import *
if __name__ == "__main__":
    import sys
    from signal_engine.backtester import main if 'main' in globals() else None
