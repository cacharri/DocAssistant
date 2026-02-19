import logging
import sys

LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "request_id=%(request_id)s %(message)s"
)
class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True

def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # evita duplicar handlers si se llama 2 veces
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)

    # ✅ CLAVE: defaults para que no explote si falta request_id
    formatter = logging.Formatter(
        LOG_FORMAT,
        defaults={"request_id": "-"},
    )
    handler.setFormatter(formatter)

    # ✅ CLAVE: filtro en el HANDLER (más fiable que solo en el root logger)
    handler.addFilter(RequestIdFilter())

    root.addHandler(handler)
