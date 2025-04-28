"""
TQDM-based implementation of the UI service.
This is a simpler alternative to the Rich UI adapter.
"""
import logging
import sys
from typing import Any, Dict, List, Optional, Union

import colorama
from tqdm import tqdm

from unit_test_generator.domain.ports.ui_service import (
    LogLevel, UIServicePort, ProgressBarPort, StatusPort, TablePort
)

# Initialize colorama for cross-platform color support
colorama.init()


class TqdmProgressBar(ProgressBarPort):
    """TQDM implementation of a progress bar."""
    
    def __init__(self, progress_bar: tqdm):
        """
        Initialize the progress bar.
        
        Args:
            progress_bar: The TQDM progress bar
        """
        self.progress_bar = progress_bar
    
    def update(self, amount: int = 1, **kwargs) -> None:
        """
        Update the progress bar.
        
        Args:
            amount: The amount to increment
            **kwargs: Additional arguments for TQDM
        """
        self.progress_bar.update(amount)
    
    def set_description(self, description: str) -> None:
        """
        Set the description of the progress bar.
        
        Args:
            description: The new description
        """
        self.progress_bar.set_description(description)
    
    def close(self) -> None:
        """Close the progress bar."""
        self.progress_bar.close()


class TqdmStatus(StatusPort):
    """TQDM implementation of a status display."""
    
    def __init__(self, progress_bar: tqdm):
        """
        Initialize the status display.
        
        Args:
            progress_bar: The TQDM progress bar
        """
        self.progress_bar = progress_bar
    
    def update(self, message: str, **kwargs) -> None:
        """
        Update the status message.
        
        Args:
            message: The new status message
            **kwargs: Additional arguments for TQDM
        """
        self.progress_bar.set_description(message)
        self.progress_bar.refresh()
    
    def stop(self, **kwargs) -> None:
        """
        Stop the status display.
        
        Args:
            **kwargs: Additional arguments for TQDM
        """
        self.progress_bar.close()


class TqdmTable(TablePort):
    """Simple table implementation for TQDM UI."""
    
    def __init__(self, columns: List[str]):
        """
        Initialize the table.
        
        Args:
            columns: The column headers
        """
        self.columns = columns
        self.rows = []
    
    def add_row(self, *values, **kwargs) -> None:
        """
        Add a row to the table.
        
        Args:
            *values: The values for the row
            **kwargs: Additional arguments (ignored)
        """
        self.rows.append(values)
    
    def render(self, **kwargs) -> None:
        """
        Render the table.
        
        Args:
            **kwargs: Additional arguments (ignored)
        """
        # Calculate column widths
        col_widths = [len(col) for col in self.columns]
        for row in self.rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print header
        header = " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(self.columns))
        print(colorama.Fore.CYAN + header + colorama.Style.RESET_ALL)
        print("-" * len(header))
        
        # Print rows
        for row in self.rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row) if i < len(col_widths))
            print(row_str)


class TqdmUIAdapter(UIServicePort):
    """TQDM implementation of the UI service."""
    
    def __init__(self):
        """Initialize the TQDM UI adapter."""
        # Define color mappings
        self.colors = {
            LogLevel.DEBUG: colorama.Fore.WHITE + colorama.Style.DIM,
            LogLevel.INFO: colorama.Fore.CYAN,
            LogLevel.SUCCESS: colorama.Fore.GREEN,
            LogLevel.WARNING: colorama.Fore.YELLOW,
            LogLevel.ERROR: colorama.Fore.RED,
            LogLevel.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
        }
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
        """
        Log a message with the specified level.
        
        Args:
            message: The message to log
            level: The log level
            **kwargs: Additional arguments (ignored)
        """
        color = self.colors.get(level, "")
        print(f"{color}{message}{colorama.Style.RESET_ALL}")
    
    def progress(self, total: int, description: str = "", **kwargs) -> TqdmProgressBar:
        """
        Create a progress bar.
        
        Args:
            total: The total number of steps
            description: A description of the progress
            **kwargs: Additional arguments for TQDM
            
        Returns:
            A TqdmProgressBar object
        """
        progress_bar = tqdm(total=total, desc=description, **kwargs)
        return TqdmProgressBar(progress_bar)
    
    def status(self, message: str, **kwargs) -> TqdmStatus:
        """
        Display a status message that can be updated.
        
        Args:
            message: The initial status message
            **kwargs: Additional arguments for TQDM
            
        Returns:
            A TqdmStatus object
        """
        # Create a fake progress bar with no total
        progress_bar = tqdm(total=0, desc=message, bar_format='{desc}', **kwargs)
        return TqdmStatus(progress_bar)
    
    def table(self, columns: List[str], **kwargs) -> TqdmTable:
        """
        Create a table with the specified columns.
        
        Args:
            columns: The column headers
            **kwargs: Additional arguments (ignored)
            
        Returns:
            A TqdmTable object
        """
        return TqdmTable(columns)
    
    def panel(self, content: str, title: str = "", **kwargs) -> None:
        """
        Display content in a panel.
        
        Args:
            content: The content to display
            title: The panel title
            **kwargs: Additional arguments (ignored)
        """
        width = kwargs.get("width", 80)
        
        # Print the top border with title
        if title:
            title_str = f" {title} "
            padding = (width - len(title_str)) // 2
            print(colorama.Fore.CYAN + "=" * padding + title_str + "=" * (width - padding - len(title_str)) + colorama.Style.RESET_ALL)
        else:
            print(colorama.Fore.CYAN + "=" * width + colorama.Style.RESET_ALL)
        
        # Print the content
        for line in content.split("\n"):
            print(line)
        
        # Print the bottom border
        print(colorama.Fore.CYAN + "=" * width + colorama.Style.RESET_ALL)
    
    def syntax(self, code: str, language: str, **kwargs) -> None:
        """
        Display code with syntax highlighting.
        
        Args:
            code: The code to display
            language: The programming language (ignored in this implementation)
            **kwargs: Additional arguments (ignored)
        """
        # Simple implementation without syntax highlighting
        print(colorama.Fore.YELLOW + f"--- {language} ---" + colorama.Style.RESET_ALL)
        print(code)
        print(colorama.Fore.YELLOW + "-" * 20 + colorama.Style.RESET_ALL)
