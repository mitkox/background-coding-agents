"""
Background Coding Agents for Industrial Manufacturing

A reference implementation demonstrating AI-powered automated code changes
across manufacturing sites, based on Spotify's proven approach.

This package provides:
- Fleet management for orchestrating migrations across multiple sites
- Background coding agents for PLC code transformations
- Verification systems for safety-critical industrial environments
- Modern Python best practices for production-quality code

Based on Spotify's engineering blog series:
- Part 1: The Journey (1,500+ PRs merged)
- Part 2: Context Engineering
- Part 3: Feedback Loops

Version: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "Background Coding Agents Team"
__license__ = "MIT"

from background_coding_agents.agents.plc_agent import PLCAgent, PLCChange
from background_coding_agents.fleet_manager.cli import FleetManager
from background_coding_agents.verifiers.plc_compiler_verifier import PLCCompilerVerifier
from background_coding_agents.verifiers.safety_verifier import SafetyVerifier


__all__ = [
    "FleetManager",
    "PLCAgent",
    "PLCChange",
    "PLCCompilerVerifier",
    "SafetyVerifier",
    "__version__",
]
