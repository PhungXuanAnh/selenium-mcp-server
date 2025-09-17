import click
import logging
from logging.config import dictConfig
from .server import driver, mcp


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] [%(pathname)s:%(lineno)d] [%(funcName)s] %(levelname)s: %(message)s"
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
    },
}

dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)

@click.command()
@click.option("--user_data_dir", "user_data_dir_param", help="Chrome user data directory (default: /tmp/chrome-debug-{timestamp})")
@click.option("--port", "port_param", type=int, help="Port for Chrome remote debugging (default: 9222)")
@click.option("-v", "--verbose", count=True)
def main(user_data_dir_param: str, port_param: int, verbose: int) -> None:
    """Selenium MCP Server - Synchronous version"""
    global user_data_dir
    global debug_port
    
    # Setup logging based on verbosity
    if verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set global user_data_dir from command line argument
    if user_data_dir_param:
        user_data_dir = user_data_dir_param
        
    # Set global debug_port from command line argument
    if port_param:
        debug_port = port_param
    
    logger.info(f"Running MCP Selenium server with Chrome configured at 127.0.0.1:{debug_port}, user data dir: {user_data_dir}")
    try:
        # Run the MCP server
        logger.info("Starting MCP Selenium server")
        mcp.run(transport='stdio')
        
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
    
    finally:
        # Clean up the WebDriver when done, but don't close the browser
        # since we're connecting to an existing instance
        if driver is not None:
            logger.info("Disconnecting from Chrome instance (but leaving browser open)")
            driver.quit()


if __name__ == "__main__":
    main()