# Enhanced UI for JUnit Writer

This document describes the enhanced UI features added to JUnit Writer to improve the command line user experience.

## Overview

The enhanced UI provides:

1. **Colored Output**: Different colors for different log levels and message types
2. **Progress Bars**: Visual indicators of progress for long-running operations
3. **Status Displays**: Animated spinners with status messages
4. **Tables**: Formatted tables for displaying structured data
5. **Panels**: Bordered panels for grouping related information
6. **Syntax Highlighting**: Colored code snippets for better readability

## Architecture

The UI enhancements follow clean architecture principles:

1. **Domain Layer**: Defines interfaces for UI components in `unit_test_generator.domain.ports.ui_service`
2. **Application Layer**: Provides a service for coordinating UI rendering in `unit_test_generator.application.services.ui_service`
3. **Infrastructure Layer**: Implements concrete UI components using libraries in `unit_test_generator.infrastructure.adapters.ui`
4. **Presentation Layer**: Uses the UI service in CLI commands

## Configuration

UI settings can be configured in `config/application.yml`:

```yaml
# --- UI Settings ---
ui:
  # UI type: 'rich' (default) or 'tqdm'
  type: "rich"
  # Enable enhanced logging with colors and formatting
  enhanced_logging: true
  # Progress bar style (only for rich UI)
  progress_style: "bar"
  # Color theme: 'default', 'dark', 'light'
  theme: "default"
```

## Dependencies

The enhanced UI requires the following dependencies:

- **Rich**: A comprehensive library for rich text and beautiful formatting in the terminal
- **tqdm**: For progress bars and animations
- **colorama**: For cross-platform colored terminal text (as a fallback)

These dependencies are listed in `requirements.txt`.

## Usage

The enhanced UI is automatically used when running JUnit Writer commands:

```bash
# Index the repository with enhanced UI
python main.py index

# Generate tests with enhanced UI
python main.py generate path/to/source/file.kt
```

## Fallback Mechanism

If the required UI libraries are not available, the system will fall back to standard logging with basic formatting. This ensures that the application remains functional even without the enhanced UI dependencies.

## Implementation Details

### UI Service Port

The `UIServicePort` interface defines the contract for UI services:

- `log`: Log a message with a specified level
- `progress`: Create a progress bar
- `status`: Display a status message that can be updated
- `table`: Create a table with specified columns
- `panel`: Display content in a panel
- `syntax`: Display code with syntax highlighting

### Rich UI Adapter

The `RichUIAdapter` implements the UI service using the Rich library, providing:

- Colored and formatted logging
- Progress bars with spinners and elapsed time
- Status displays with spinners
- Tables with borders and styling
- Panels with borders and titles
- Syntax highlighting for code

### TQDM UI Adapter

The `TqdmUIAdapter` provides a simpler alternative using the tqdm library for:

- Basic colored output
- Simple progress bars
- Status displays
- Basic tables and panels

### UI Service

The `UIService` application service coordinates UI rendering and provides fallback mechanisms when UI adapters are not available.

## Testing

To test the enhanced UI:

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the index command:
   ```bash
   python main.py index
   ```

3. Run the generate command:
   ```bash
   python main.py generate path/to/source/file.kt
   ```

4. Try different UI types by changing the configuration:
   ```yaml
   ui:
     type: "tqdm"  # or "rich"
   ```
