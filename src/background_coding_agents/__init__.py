"""
Background Coding Agents for Industrial Manufacturing

A professional reference implementation for AI-powered automated code changes
across manufacturing sites, based on Spotify's proven approach.

This package provides:
- Fleet management for orchestrating migrations across multiple sites
- Background coding agents for PLC code transformations
- Verification systems for safety-critical industrial environments
- Multiple LLM backends including local models for air-gapped environments
- REST API for SCADA/MES system integration
- Comprehensive audit logging for regulatory compliance

Supported LLM Providers:
- Cloud: Anthropic Claude, OpenAI GPT
- Local: llama.cpp, vLLM, OpenAI-compatible endpoints
  - Recommended models: GLM-4.7, MiniMax-M2.1

Based on Spotify's engineering blog series:
- Part 1: The Journey (1,500+ PRs merged)
- Part 2: Context Engineering
- Part 3: Feedback Loops

Version: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "Background Coding Agents Team"
__license__ = "MIT"

# Core components
from background_coding_agents.agents.plc_agent import PLCAgent
from background_coding_agents.fleet_manager.cli import FleetManager
from background_coding_agents.verifiers.plc_compiler_verifier import PLCCompilerVerifier
from background_coding_agents.verifiers.safety_verifier import SafetyVerifier

# LLM providers
from background_coding_agents.llm import (
    BaseLLMProvider,
    LLMProviderFactory,
    ProviderType,
    create_provider,
)

# Models
from background_coding_agents.models import (
    AgentConfig,
    AgentResult,
    MigrationConfig,
    MigrationResult,
    PLCChange,
    SiteConfig,
    VerificationResult,
)

# Configuration
from background_coding_agents.config import AppSettings, get_settings

# Logging
from background_coding_agents.logging import AuditLogger, get_logger, setup_logging


__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Core components
    "FleetManager",
    "PLCAgent",
    "PLCCompilerVerifier",
    "SafetyVerifier",
    # LLM
    "BaseLLMProvider",
    "LLMProviderFactory",
    "ProviderType",
    "create_provider",
    # Models
    "AgentConfig",
    "AgentResult",
    "MigrationConfig",
    "MigrationResult",
    "PLCChange",
    "SiteConfig",
    "VerificationResult",
    # Config
    "AppSettings",
    "get_settings",
    # Logging
    "AuditLogger",
    "get_logger",
    "setup_logging",
]
