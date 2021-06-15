import logging
import logging.config

DEFAULT_LOG_LEVEL = "INFO"


def init_logging(log_level: str):
    """Initializes logging."""
    logging_config = {
        "version": 1,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "default",
                "stream": "ext://sys.stdout",
            }
        },
        "formatters": {
            "default": {"format": "%(asctime)s:%(levelname)s:%(module)s:%(funcName)s:%(message)s"}
        },
        "root": {"level": log_level, "handlers": ["console"]},
        "disable_existing_loggers": True,
    }

    logging.config.dictConfig(logging_config)
