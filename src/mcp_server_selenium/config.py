
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] [%(filename)s:%(lineno)d] %(levelname)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
    },
    "handlers": {
        "app.DEBUG": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": "/tmp/selenium-mcp.log",
            "maxBytes": 100000 * 1024,  # 100MB
            "backupCount": 3,
        },
        "app.INFO": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": "/tmp/selenium-mcp.log",
            "maxBytes": 100000 * 1024,  # 100MB
            "backupCount": 3,
        },
    },
    "loggers": {
        "root": {
            "handlers": ["app.INFO"],
            "propagate": False,
            "level": "INFO",
        },
        # "selenium": {
        #     "handlers": ["app.DEBUG"],
        #     "propagate": False,
        #     "level": "DEBUG",
        # },
    },
}