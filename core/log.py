import logging
import os
import sys


_log = None


def _base_dir():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get():
    global _log
    if _log:
        return _log

    log = logging.getLogger("clipqueue")
    log.setLevel(logging.INFO)

    if not log.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        try:
            fh = logging.FileHandler(os.path.join(_base_dir(), "clipqueue.log"), encoding="utf-8")
            fh.setFormatter(fmt)
            log.addHandler(fh)
        except Exception:
            pass

        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        log.addHandler(sh)

    _log = log
    return log

