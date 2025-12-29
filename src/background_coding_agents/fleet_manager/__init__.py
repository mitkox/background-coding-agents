"""
Fleet management for orchestrating migrations across manufacturing sites.

This module handles the orchestration of automated code changes across multiple
manufacturing sites, similar to Spotify's fleet management system.

Key components:
- FleetManager: Main orchestrator for multi-site migrations
- CLI interface for command-line operations
"""

from background_coding_agents.fleet_manager.cli import FleetManager


__all__ = ["FleetManager"]
