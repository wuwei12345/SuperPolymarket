"""User interface entrypoints."""

from polymarket_quant.ui.operator_console_app import main as operator_console_main
from polymarket_quant.ui.simulation_dashboard_app import main as simulation_dashboard_main

__all__ = ["operator_console_main", "simulation_dashboard_main"]
