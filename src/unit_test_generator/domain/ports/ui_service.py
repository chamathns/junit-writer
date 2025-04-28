"""
Domain interfaces for UI components.
These interfaces define the contract for UI services in the application.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class LogLevel(Enum):
    """Log levels for UI messages."""
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class UIServicePort(ABC):
    """Interface for UI services."""
    
    @abstractmethod
    def log(self, message: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
        """
        Log a message with the specified level.
        
        Args:
            message: The message to log
            level: The log level
            **kwargs: Additional arguments for the specific implementation
        """
        pass
    
    @abstractmethod
    def progress(self, total: int, description: str = "", **kwargs) -> Any:
        """
        Create a progress bar.
        
        Args:
            total: The total number of steps
            description: A description of the progress
            **kwargs: Additional arguments for the specific implementation
            
        Returns:
            A progress bar object that can be updated
        """
        pass
    
    @abstractmethod
    def status(self, message: str, **kwargs) -> Any:
        """
        Display a status message that can be updated.
        
        Args:
            message: The initial status message
            **kwargs: Additional arguments for the specific implementation
            
        Returns:
            A status object that can be updated
        """
        pass
    
    @abstractmethod
    def table(self, columns: List[str], **kwargs) -> Any:
        """
        Create a table with the specified columns.
        
        Args:
            columns: The column headers
            **kwargs: Additional arguments for the specific implementation
            
        Returns:
            A table object that can be populated
        """
        pass
    
    @abstractmethod
    def panel(self, content: str, title: str = "", **kwargs) -> None:
        """
        Display content in a panel.
        
        Args:
            content: The content to display
            title: The panel title
            **kwargs: Additional arguments for the specific implementation
        """
        pass
    
    @abstractmethod
    def syntax(self, code: str, language: str, **kwargs) -> None:
        """
        Display code with syntax highlighting.
        
        Args:
            code: The code to display
            language: The programming language
            **kwargs: Additional arguments for the specific implementation
        """
        pass


class ProgressBarPort(ABC):
    """Interface for progress bars."""
    
    @abstractmethod
    def update(self, amount: int = 1, **kwargs) -> None:
        """
        Update the progress bar.
        
        Args:
            amount: The amount to increment
            **kwargs: Additional arguments for the specific implementation
        """
        pass
    
    @abstractmethod
    def set_description(self, description: str) -> None:
        """
        Set the description of the progress bar.
        
        Args:
            description: The new description
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the progress bar."""
        pass


class StatusPort(ABC):
    """Interface for status displays."""
    
    @abstractmethod
    def update(self, message: str, **kwargs) -> None:
        """
        Update the status message.
        
        Args:
            message: The new status message
            **kwargs: Additional arguments for the specific implementation
        """
        pass
    
    @abstractmethod
    def stop(self, **kwargs) -> None:
        """
        Stop the status display.
        
        Args:
            **kwargs: Additional arguments for the specific implementation
        """
        pass


class TablePort(ABC):
    """Interface for tables."""
    
    @abstractmethod
    def add_row(self, *values, **kwargs) -> None:
        """
        Add a row to the table.
        
        Args:
            *values: The values for the row
            **kwargs: Additional arguments for the specific implementation
        """
        pass
    
    @abstractmethod
    def render(self, **kwargs) -> None:
        """
        Render the table.
        
        Args:
            **kwargs: Additional arguments for the specific implementation
        """
        pass
