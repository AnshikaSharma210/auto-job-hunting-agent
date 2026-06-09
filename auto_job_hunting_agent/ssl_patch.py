"""
Inject the Windows/macOS/Linux system certificate store into Python's SSL context
so that corporate HTTPS-inspection proxies are trusted automatically.
Call this once at the very start of the process, before any HTTPS calls are made.
"""
from __future__ import annotations


def patch() -> None:
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass  # Not installed — may still work on non-proxied networks
    except Exception:
        pass  # Non-fatal; worst case is SSL errors surface naturally
