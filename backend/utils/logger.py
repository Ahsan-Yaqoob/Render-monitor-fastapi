import logging
import os
from datetime import datetime


class Logger:
    """Logger utility for the Render Monitor application."""
    
    def __init__(self, name='RenderMonitor'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            import sys
            console_handler = logging.StreamHandler(
                stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
            )
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'logs'
            )
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(
                log_dir,
                f'monitor_{datetime.now().strftime("%Y%m%d")}.log'
            )
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message):
        """Log error message."""
        self.logger.error(message)
    
    def debug(self, message):
        """Log debug message."""
        self.logger.debug(message)
    
    def critical(self, message):
        """Log critical message."""
        self.logger.critical(message)


logger = Logger()
