import logging
import sys


def configure_logging(level: str) -> None:
    logger = logging.getLogger()
    logger.setLevel(level.upper())

    # Avoid duplicate handlers (hot reload / repeated imports)
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s msg=%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True
