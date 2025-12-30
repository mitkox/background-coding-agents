# AGENTS.md

This file provides guidance to Coding Agents when working with code in this repository.

## Project Overview

This is a demonstration repository showing how to apply Spotify's background coding agent concepts to industrial manufacturing environments. It's based on Spotify's 3-part engineering blog series on their journey merging 1,500+ AI-generated PRs with 60-90% time savings.

The codebase demonstrates automated PLC/SCADA code transformations across multiple manufacturing sites with safety-critical verification layers.

## Key Commands

### Setup
```bash
# Initial setup
./setup.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate  # or . venv/Scripts/activate on Windows
pip install -r requirements.txt
```

### Running the Fleet Manager
```bash
# From root directory (using installed entry point)
fleet-manager --help

# Example: Dry-run migration
fleet-manager safety_interlock_update --dry-run

# Example: List configured sites
fleet-manager list-sites

# View migration status
fleet-manager status
```

### Development
```bash
# Run tests (if implemented)
pytest

# Format code
black .

# Type checking
mypy agents/ verifiers/ fleet-manager/
```

## Architecture Overview

This project implements a **Fleet Management Architecture** for automated code changes across manufacturing sites, analogous to Spotify's repository fleet management:

### Core Components

1. **Fleet Manager** (`fleet-manager/cli.py`)
   - Orchestrates migrations across multiple sites
   - Targets sites based on filters (PLC type, firmware version, etc.)
   - Manages verification loops and change requests
   - Configuration in `fleet-manager/config.yaml`

2. **Background Coding Agent** (`src/background_coding_agents/agents/plc_agent.py`)
   - Transforms PLC code based on natural language prompts
   - Uses iterative change-verify loops (max 10 turns)
   - **Supports local LLMs** (vLLM, llama.cpp) for air-gapped deployments
   - Cloud LLMs optional (Anthropic, OpenAI, MiniMax)
   - Limited tool access (verify, git diff, ripgrep)

3. **Verification Layers** (`src/background_coding_agents/verifiers/`)
   - **PLCCompilerVerifier**: Deterministic compilation checks
   - **SafetyVerifier**: CRITICAL - Safety-rated logic verification (emergency stops, interlocks, SIL compliance)
   - **SimulationVerifier**: Runtime simulation testing (coming soon)
   - All verifiers return `{'passed': bool, 'message': str, 'details': ...}`

4. **Migration Prompts** (`prompts/`)
   - Natural language prompts following Spotify's context engineering principles
   - Structured format: preconditions, examples, success criteria
   - Examples: `safety_interlock_update.md`, `protocol_migration.md`

### Key Architectural Patterns

**Verification Loop Strategy** (from Spotify Part 3):
- **Inner Loop**: Fast feedback during execution (compiler, syntax checks)
- **Outer Loop**: Comprehensive verification before PR/CAR (safety, simulation)
- **LLM Judge**: Reviews changes for scope creep and safety compliance
- Agent has max 10 turns to complete task with verification feedback

**Context Engineering** (from Spotify Part 2):
- Prompts tailored for goal-oriented agents (Claude Code)
- Clear preconditions (e.g., "ONLY if firmware v4.0+")
- Concrete before/after examples (3-5 variations)
- Defined success criteria (tests that must pass)
- One change at a time (avoids context exhaustion)
- Limited tool access (prevents unpredictability)

**Safety-First Adaptations**:
Unlike software where failed PRs are annoying, failed safety = catastrophic. Therefore:
- Safety verifier ALWAYS runs, never skipped
- Human safety review mandatory for safety-critical changes
- Simulation testing required before hardware deployment
- Staged rollouts: Test → Validate → Deploy
- Complete audit trail for regulatory compliance

## File Structure

```
.
├── README.md                          # Quick overview
├── GUIDE.md                          # Complete implementation guide
├── PROJECT_SUMMARY.md                # Quick summary
├── FILE_INDEX.md                     # Navigation by role
├── requirements.txt                  # Python dependencies
├── setup.sh                         # Setup script
│
├── fleet-manager/                    # Orchestration system
│   ├── cli.py                       # Main CLI (200 lines)
│   ├── config.yaml                  # Site configurations & agent settings
│   └── migrations/                  # Migration definitions (YAML)
│
├── agents/                           # Agent implementations
│   └── plc_agent.py                 # PLC transformation agent (216 lines)
│
├── verifiers/                        # Verification loops
│   ├── plc_compiler_verifier.py    # Compilation verification (182 lines)
│   └── safety_verifier.py          # Safety verification (256 lines)
│
├── prompts/                          # Migration prompts (Spotify-style)
│   ├── safety_interlock_update.md
│   └── protocol_migration.md
│
├── examples/                         # Example implementations
│   └── safety_interlock_update/
│       └── README.md                # Complete walkthrough
│
└── docs/                             # Documentation
    ├── spotify-insights.md          # All lessons from Spotify blogs
    ├── comparison-spotify-vs-manufacturing.md
    ├── implementation-roadmap.md    # Phased rollout plan
    └── diagrams.md                  # Visual architecture
```

## Important Concepts

### Agent Design Principles
From Spotify's experience:
1. **Focused**: Agent only does code changes, nothing else
2. **Sandboxed**: Limited permissions and tool access
3. **Guided**: Strong verification loops provide feedback
4. **Iterative**: Max turns limit prevents runaway execution
5. **Verifiable**: Every change passes through multiple verification layers

### Safety Verification is Non-Negotiable
When working with safety-critical code:
- Emergency stop logic must NEVER be modified by agents without explicit authorization
- Safety interlocks cannot be bypassed or disabled
- SIL (Safety Integrity Level) ratings must be maintained
- Certified safety logic requires re-certification if modified
- Patterns like `FORCE`, `DISABLE.*SAFETY`, `BYPASS.*GUARD` are forbidden

See `verifiers/safety_verifier.py` for complete checks.

### Configuration Files

**src/background_coding_agents/fleet_manager/config.yaml** structure:
- `llm`: **Local-first LLM configuration** (vLLM/llama.cpp default, cloud optional)
- `sites[]`: Manufacturing site definitions (PLC type, firmware, safety rating, repo path)
- `agent`: Agent configuration (max turns, available tools, timeouts)
- `verification`: Verifier settings and LLM judge configuration
- `change_management`: Approval and deployment requirements
- `logging`: Structured JSON logging and observability settings

### Dependencies

Core dependencies in `requirements.txt`:
- `pyyaml`: Configuration management
- `pydantic`, `pydantic-settings`: Type-safe configuration with .env support
- `httpx`: HTTP client for local vLLM/API communication
- `anthropic`: Optional cloud LLM support (Anthropic, MiniMax)
- `structlog`: Structured JSON logging
- `pytest`, `pytest-asyncio`: Testing framework

PLC-specific libraries (commented out, vendor-dependent):
- `pycomm3`: Allen-Bradley PLCs
- `snap7`: Siemens S7 PLCs
- `pymodbus`: Modbus communication

## Local LLM Deployment (Recommended)

This project prioritizes **local LLM deployment** for air-gapped industrial environments:

### Supported Local Providers

**vLLM (Recommended for Production)**:
```bash
# Start vLLM server with MiniMax M2.1
vllm serve minimax-m2.1 --port 8000

# Or with GLM-4.7
vllm serve THUDM/glm-4.7-chat --port 8000
```

**llama.cpp (Edge Deployment)**:
```bash
# Download GGUF model
llama-cpp-python serve /models/minimax-m2.1.Q4_K_M.gguf
```

### Configuration

**Environment Variables** (`.env` file):
```bash
# Local vLLM (no API key required)
LLM_PROVIDER=vllm
LLM_MODEL=minimax-m2.1
LLM_BASE_URL=http://localhost:8000
LLM_TEMPERATURE=0.0
```

**Supported Models**:
- `minimax-m2.1`: Multilingual, code generation (recommended)
- `THUDM/glm-4.7-chat`: Excellent reasoning and code
- `MiniMaxAI/MiniMax-M2.1`: HuggingFace format

**Cloud Providers** (optional, requires API keys):
- Anthropic Claude (claude-sonnet-4-20250514)
- OpenAI GPT (gpt-4o)
- MiniMax Cloud (via Anthropic-compatible API)

### Why Local First?

1. **Air-gapped environments**: Manufacturing requires offline capability
2. **Data privacy**: Sensitive PLC code stays on-premises
3. **Cost predictability**: No per-token charges
4. **Low latency**: Local inference faster than API calls
5. **Compliance**: Meets industrial security requirements

## Working with This Codebase

### When Making Changes

1. **Understand the safety context**: This code controls industrial equipment. Review safety implications before modifying verification logic.

2. **Follow Spotify's principles**:
   - Keep prompts focused on one change at a time
   - Add concrete examples to prompt templates
   - Ensure verification loops provide clear feedback
   - Limit agent tool access to prevent unpredictability

3. **Verification layers are sequential**:
   ```
   Compiler Check → Safety Check → Simulation Test → LLM Judge → Human Review
   ```
   Each layer must pass before proceeding to the next.

4. **Agent execution flow**:
   - Discovery: Find relevant files (don't overwhelm context)
   - Planning: Create step-by-step plan (Claude Code does this with todos)
   - Execution: Make changes iteratively with verification
   - Final verification: All checks before PR/CAR creation

### Common Tasks

**Adding a new migration**:
1. Create prompt in `prompts/new_migration.md` following existing format
2. Create migration config in `fleet-manager/migrations/new_migration.yaml`
3. Define target filters (PLC type, firmware version, etc.)
4. Specify required verifiers
5. Test with `--dry-run` flag first

**Adding a new verifier**:
1. Create class in `verifiers/` inheriting verification pattern
2. Implement `async def verify(changes: Dict, site_config: Dict) -> Dict`
3. Return `{'passed': bool, 'message': str, 'details': ...}`
4. Add to `verification.verifiers` in `config.yaml`
5. Update agent's verification loop in `plc_agent.py` if needed

**Updating site configurations**:
- Edit `fleet-manager/config.yaml`
- Each site requires: name, location, plc_type, firmware_version, repo_path, safety_rating
- Use filters in migration configs to target specific sites

## Recent Updates

### December 2025

**Local vLLM Integration** (commit 247254b):
- Switched to local vLLM as primary deployment target
- Updated default configuration to prioritize air-gapped deployments
- Cloud providers now optional (only needed when specified)
- No authentication required for local inference

**NoneType Error Fixes** (commit 661fc2a):
- Fixed "argument of type 'NoneType' is not iterable" errors
- Added None checks in `_discover_relevant_files`
- Added None check in `_extract_code` with graceful fallback
- Added None check in `_create_plan` with proper error handling
- Agent now handles empty/None LLM responses gracefully

**Entry Point Fix** (commit a210ce1):
- Fixed fleet-manager async entry point issue
- Renamed async main() to async_main() to avoid setuptools confusion
- Added proper sync wrapper for CLI execution

**Configuration Loading** (commits 7d465aa, 247254b):
- Added .env file support via pydantic-settings
- Environment variables now properly override YAML config
- Fixed base_url conditional passing in Anthropic provider
- Added SiteMigrationResult export

## Testing and Validation

This is a demonstration/example repository. In a production environment:
- All verifiers would connect to real PLC compilers (TIA Portal, Studio 5000)
- Simulation verifier would launch virtual PLCs (PLCSIM, Emulate 5000)
- Agent would use actual LLM APIs (Claude, GPT)
- Fleet manager would integrate with git hosting (GitHub, GitLab, Bitbucket)
- MLflow would track all migrations and results

For development in this repo:
- Verifiers simulate success/failure scenarios
- Agent planning is simplified
- Focus on architecture and patterns rather than live PLC integration

## References

This implementation is based on:
- [Spotify Part 1: The Journey](https://engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1) - 1,500+ PRs merged
- [Spotify Part 2: Context Engineering](https://engineering.atspotify.com/2025/11/context-engineering-background-coding-agents-part-2) - Prompt design principles
- [Spotify Part 3: Feedback Loops](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3) - Verification strategy

See `docs/spotify-insights.md` for complete breakdown of all concepts.

## Standards and Compliance

Industrial automation standards referenced:
- **ISO 13849-1**: Safety of machinery - Safety-related parts of control systems
- **IEC 61508**: Functional safety of electrical/electronic/programmable electronic safety-related systems
- **IEC 62443**: Industrial communication networks - Network and system security

These inform the safety verification requirements and compliance checks.
