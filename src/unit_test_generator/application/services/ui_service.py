"""
UI Service for coordinating UI rendering.
This service provides a high-level interface for UI operations.
"""
import logging
from typing import Any, Dict, List, Optional, Union

from unit_test_generator.domain.ports.ui_service import (
    LogLevel, UIServicePort, ProgressBarPort, StatusPort, TablePort
)

logger = logging.getLogger(__name__)


class UIService:
    """Service for coordinating UI rendering."""
    
    def __init__(self, ui_service: Optional[UIServicePort] = None):
        """
        Initialize the UI service.
        
        Args:
            ui_service: An implementation of UIServicePort
        """
        self.ui_service = ui_service
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
        """
        Log a message with the specified level.
        
        Args:
            message: The message to log
            level: The log level
            **kwargs: Additional arguments for the UI service
        """
        if self.ui_service:
            self.ui_service.log(message, level, **kwargs)
        else:
            # Fallback to standard logging
            log_level = {
                LogLevel.DEBUG: logging.DEBUG,
                LogLevel.INFO: logging.INFO,
                LogLevel.SUCCESS: logging.INFO,  # No direct equivalent
                LogLevel.WARNING: logging.WARNING,
                LogLevel.ERROR: logging.ERROR,
                LogLevel.CRITICAL: logging.CRITICAL,
            }.get(level, logging.INFO)
            
            logger.log(log_level, message)
    
    def progress(self, total: int, description: str = "", **kwargs) -> Any:
        """
        Create a progress bar.
        
        Args:
            total: The total number of steps
            description: A description of the progress
            **kwargs: Additional arguments for the UI service
            
        Returns:
            A progress bar object that can be updated
        """
        if self.ui_service:
            return self.ui_service.progress(total, description, **kwargs)
        else:
            # Return a dummy progress bar
            return DummyProgressBar()
    
    def status(self, message: str, **kwargs) -> Any:
        """
        Display a status message that can be updated.
        
        Args:
            message: The initial status message
            **kwargs: Additional arguments for the UI service
            
        Returns:
            A status object that can be updated
        """
        if self.ui_service:
            return self.ui_service.status(message, **kwargs)
        else:
            # Log the status message and return a dummy status
            logger.info(f"Status: {message}")
            return DummyStatus()
    
    def table(self, columns: List[str], **kwargs) -> Any:
        """
        Create a table with the specified columns.
        
        Args:
            columns: The column headers
            **kwargs: Additional arguments for the UI service
            
        Returns:
            A table object that can be populated
        """
        if self.ui_service:
            return self.ui_service.table(columns, **kwargs)
        else:
            # Return a dummy table
            return DummyTable(columns)
    
    def panel(self, content: str, title: str = "", **kwargs) -> None:
        """
        Display content in a panel.
        
        Args:
            content: The content to display
            title: The panel title
            **kwargs: Additional arguments for the UI service
        """
        if self.ui_service:
            self.ui_service.panel(content, title, **kwargs)
        else:
            # Fallback to standard logging
            if title:
                logger.info(f"=== {title} ===")
            logger.info(content)
    
    def syntax(self, code: str, language: str, **kwargs) -> None:
        """
        Display code with syntax highlighting.
        
        Args:
            code: The code to display
            language: The programming language
            **kwargs: Additional arguments for the UI service
        """
        if self.ui_service:
            self.ui_service.syntax(code, language, **kwargs)
        else:
            # Fallback to standard logging
            logger.info(f"--- {language} ---")
            logger.info(code)


class DummyProgressBar(ProgressBarPort):
    """Dummy implementation of a progress bar."""
    
    def update(self, amount: int = 1, **kwargs) -> None:
        """Update the progress bar."""
        pass
    
    def set_description(self, description: str) -> None:
        """Set the description of the progress bar."""
        pass
    
    def close(self) -> None:
        """Close the progress bar."""
        pass


class DummyStatus(StatusPort):
    """Dummy implementation of a status display."""
    
    def update(self, message: str, **kwargs) -> None:
        """Update the status message."""
        logger.info(f"Status update: {message}")
    
    def stop(self, **kwargs) -> None:
        """Stop the status display."""
        pass


class DummyTable(TablePort):
    """Dummy implementation of a table."""
    
    def __init__(self, columns: List[str]):
        """
        Initialize the dummy table.
        
        Args:
            columns: The column headers
        """
        self.columns = columns
        self.rows = []
    
    def add_row(self, *values, **kwargs) -> None:
        """Add a row to the table."""
        self.rows.append(values)
    
    def render(self, **kwargs) -> None:
        """Render the table."""
        logger.info(f"Table with columns: {', '.join(self.columns)}")
        for row in self.rows:
            logger.info(f"Row: {', '.join(str(v) for v in row)}")
