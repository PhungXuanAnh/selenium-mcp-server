import click
import logging
from logging.config import dictConfig
from .server import driver_instance, mcp, quit_driver

# NOTE: Import tools to register them with FastMCP
from .tools import navigate
from .tools import screenshot
from .tools import page_ready
from .tools import logs
from .tools import local_storage
from .tools import element_interaction
from .tools import script
from .tools import style


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
            "handlers": ["app.DEBUG"],
            "propagate": False,
            "level": "DEBUG",
        },
    },
}

dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)

@click.command()
@click.option("--user_data_dir", "user_data_dir_param", help="Chrome user data directory (default: /tmp/chrome-debug-{timestamp})")
@click.option("--port", "port_param", type=int, help="Port for Chrome remote debugging (default: 9222)")
@click.option("--driver", "driver_param", default="normal_chromedriver", 
              type=click.Choice(["normal_chromedriver", "undetected_chrome_driver"]),
              help="Type of Chrome driver to use (default: normal_chromedriver)")
@click.option("--profile", "profile_param", default="Default", help="Chrome profile to use (default: Default)")
@click.option("-v", "--verbose", count=True)
def main(user_data_dir_param: str, port_param: int, driver_param: str, profile_param: str, verbose: int) -> None:
    """Selenium MCP Server - Synchronous version"""
    # Import server module to access global variables
    from . import server
    
    # Setup logging based on verbosity
    if verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set global user_data_dir from command line argument
    if user_data_dir_param:
        server.user_data_dir = user_data_dir_param
        
    # Set global debug_port from command line argument
    if port_param:
        server.debug_port = port_param
        
    # Set global driver_type from command line argument
    server.driver_type = driver_param
    
    # Set global profile from command line argument
    server.profile = profile_param
    
    # Validate driver availability early
    try:
        server.get_driver_factory(driver_param)
    except (ImportError, ValueError) as e:
        logger.error(f"Driver validation failed: {str(e)}")
        raise e
    
    logger.info(f"Running MCP Selenium server with {driver_param} configured at 127.0.0.1:{server.debug_port}, user data dir: {server.user_data_dir}, profile: {server.profile}")
    
    # Initialize driver and start browser
    try:
        logger.info("Initializing driver and starting browser...")
        driver_instance = server.initialize_driver_instance()
        # Ensure the actual selenium driver is initialized (this starts the browser)
        driver_instance.ensure_driver_initialized()
        logger.info("Driver initialized and browser started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize driver: {str(e)}")
        raise e
    
    try:
        # Run the MCP server
        logger.info("Starting MCP Selenium server")
        mcp.run(transport='stdio')
        
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
    
    finally:
        # Clean up the WebDriver when done
        quit_driver()


if __name__ == "__main__":
    main()