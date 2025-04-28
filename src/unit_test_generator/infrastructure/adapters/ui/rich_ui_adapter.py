"""
Rich-based implementation of the UI service.
"""
import logging
import sys
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme

from unit_test_generator.domain.ports.ui_service import (
    LogLevel, UIServicePort, ProgressBarPort, StatusPort, TablePort
)


class RichProgressBar(ProgressBarPort):
    """Rich implementation of a progress bar."""

    def __init__(self, progress: Progress, task_id: int):
        """
        Initialize the progress bar.

        Args:
            progress: The Rich Progress object
            task_id: The task ID in the Progress object
        """
        self.progress = progress
        self.task_id = task_id

    def update(self, amount: int = 1, **kwargs) -> None:
        """
        Update the progress bar.

        Args:
            amount: The amount to increment
            **kwargs: Additional arguments for Rich
        """
        self.progress.update(self.task_id, advance=amount, **kwargs)

    def set_description(self, description: str) -> None:
        """
        Set the description of the progress bar.

        Args:
            description: The new description
        """
        self.progress.update(self.task_id, description=description)

    def close(self) -> None:
        """Close the progress bar."""
        self.progress.stop_task(self.task_id)


class RichStatus(StatusPort):
    """Rich implementation of a status display."""

    def __init__(self, progress: Progress, task_id: int):
        """
        Initialize the status display.

        Args:
            progress: The Rich Progress object
            task_id: The task ID in the Progress object
        """
        self.progress = progress
        self.task_id = task_id

    def update(self, message: str, **kwargs) -> None:
        """
        Update the status message.

        Args:
            message: The new status message
            **kwargs: Additional arguments for Rich
        """
        self.progress.update(self.task_id, description=message, **kwargs)

    def stop(self, **kwargs) -> None:
        """
        Stop the status display.

        Args:
            **kwargs: Additional arguments for Rich
        """
        self.progress.stop_task(self.task_id)


class RichTable(TablePort):
    """Rich implementation of a table."""

    def __init__(self, table: Table, console: Console):
        """
        Initialize the table.

        Args:
            table: The Rich Table object
            console: The Rich Console object
        """
        self.table = table
        self.console = console

    def add_row(self, *values, **kwargs) -> None:
        """
        Add a row to the table.

        Args:
            *values: The values for the row
            **kwargs: Additional arguments for Rich
        """
        self.table.add_row(*values, **kwargs)

    def render(self, **kwargs) -> None:
        """
        Render the table.

        Args:
            **kwargs: Additional arguments for Rich
        """
        self.console.print(self.table, **kwargs)


class RichUIAdapter(UIServicePort):
    """Rich implementation of the UI service."""

    def __init__(self, config: dict = None):
        """Initialize the Rich UI adapter."""
        # Get configuration
        config = config or {}
        ui_config = config.get('ui', {})
        progress_style = ui_config.get('progress_style', 'bar').lower()

        # Define a custom theme
        self.theme = Theme({
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "critical": "red bold",
            "debug": "dim",
            "progress.description": "cyan",
            "progress.percentage": "green",
            "progress.elapsed": "cyan",
            "panel.border": "cyan",
            "panel.title": "cyan bold",
            "syntax.keyword": "bright_blue",
            "syntax.string": "bright_green",
            "syntax.number": "bright_magenta",
            "syntax.comment": "bright_black",
        })

        # Create a console with the theme
        self.console = Console(theme=self.theme)

        # Create progress columns based on style
        progress_columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}")
        ]

        # Add appropriate columns based on style
        if progress_style == 'bar':
            progress_columns.extend([
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn()
            ])
        elif progress_style == 'spinner':
            progress_columns.append(TimeElapsedColumn())
        elif progress_style == 'text':
            # Just spinner and text, no additional columns
            pass

        # Create a progress context for status and progress bars
        self.progress = Progress(
            *progress_columns,
            console=self.console,
            transient=True,
        )

        # Store the progress style for later use
        self.progress_style = progress_style

        # Start the progress context
        self.progress.start()

    def log(self, message: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
        """
        Log a message with the specified level.

        Args:
            message: The message to log
            level: The log level
            **kwargs: Additional arguments for Rich
        """
        style = level.value
        self.console.print(f"[{style}]{message}[/{style}]", **kwargs)

    def progress(self, total: int, description: str = "", **kwargs) -> RichProgressBar:
        """
        Create a progress bar.

        Args:
            total: The total number of steps
            description: A description of the progress
            **kwargs: Additional arguments for Rich

        Returns:
            A RichProgressBar object
        """
        task_id = self.progress.add_task(description, total=total, **kwargs)
        return RichProgressBar(self.progress, task_id)

    def status(self, message: str, **kwargs) -> RichStatus:
        """
        Display a status message that can be updated.

        Args:
            message: The initial status message
            **kwargs: Additional arguments for Rich

        Returns:
            A RichStatus object
        """
        # For status displays, we want to use a different approach than progress bars
        # We'll create a task with no total to indicate it's a status display
        # and use a different visual style

        # If we're using the 'bar' style for progress, use 'spinner' for status
        # to differentiate them visually
        if self.progress_style == 'bar':
            kwargs['total'] = None  # Ensure no progress bar for status

        task_id = self.progress.add_task(message, total=None, **kwargs)
        return RichStatus(self.progress, task_id)

    def table(self, columns: List[str], **kwargs) -> RichTable:
        """
        Create a table with the specified columns.

        Args:
            columns: The column headers
            **kwargs: Additional arguments for Rich

        Returns:
            A RichTable object
        """
        table = Table(**kwargs)
        for column in columns:
            table.add_column(column)
        return RichTable(table, self.console)

    def panel(self, content: str, title: str = "", **kwargs) -> None:
        """
        Display content in a panel.

        Args:
            content: The content to display
            title: The panel title
            **kwargs: Additional arguments for Rich
        """
        panel = Panel(content, title=title, **kwargs)
        self.console.print(panel)

    def syntax(self, code: str, language: str, **kwargs) -> None:
        """
        Display code with syntax highlighting.

        Args:
            code: The code to display
            language: The programming language
            **kwargs: Additional arguments for Rich
        """
        syntax = Syntax(code, language, theme="monokai", line_numbers=True, **kwargs)
        self.console.print(syntax)


class RichLoggingHandler(RichHandler):
    """Custom Rich logging handler with improved formatting."""

    def __init__(self, *args, **kwargs):
        """Initialize the Rich logging handler."""
        super().__init__(*args, **kwargs)

    def emit(self, record):
        """
        Emit a log record.

        Args:
            record: The log record
        """
        # Add custom styling based on log level
        if record.levelno >= logging.CRITICAL:
            record.levelname = f"[critical]{record.levelname}[/critical]"
        elif record.levelno >= logging.ERROR:
            record.levelname = f"[error]{record.levelname}[/error]"
        elif record.levelno >= logging.WARNING:
            record.levelname = f"[warning]{record.levelname}[/warning]"
        elif record.levelno >= logging.INFO:
            record.levelname = f"[info]{record.levelname}[/info]"
        else:
            record.levelname = f"[debug]{record.levelname}[/debug]"

        super().emit(record)
