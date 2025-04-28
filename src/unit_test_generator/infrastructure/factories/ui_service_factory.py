"""
Factory for creating UI service instances.
"""
from typing import Dict, Any, Optional

from unit_test_generator.domain.ports.ui_service import UIServicePort
from unit_test_generator.infrastructure.adapters.ui.rich_ui_adapter import RichUIAdapter
from unit_test_generator.infrastructure.adapters.ui.tqdm_ui_adapter import TqdmUIAdapter


def create_ui_service(config: Dict[str, Any]) -> UIServicePort:
    """
    Create a UI service based on configuration.
    
    Args:
        config: The application configuration
        
    Returns:
        An implementation of UIServicePort
    """
    ui_config = config.get("ui", {})
    ui_type = ui_config.get("type", "rich").lower()
    
    if ui_type == "rich":
        return RichUIAdapter()
    elif ui_type == "tqdm":
        return TqdmUIAdapter()
    else:
        # Default to Rich
        return RichUIAdapter()
