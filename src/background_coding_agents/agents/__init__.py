"""
Background coding agents for autonomous code transformations.

This module contains agent implementations that can understand natural language prompts
and autonomously modify PLC code across multiple manufacturing sites.

Key components:
- PLCAgent: Main agent for PLC code transformations
- Base classes and protocols for extensibility
"""

from background_coding_agents.agents.plc_agent import PLCAgent, PLCChange


__all__ = ["PLCAgent", "PLCChange"]
