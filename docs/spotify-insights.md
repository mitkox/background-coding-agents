# Key Insights from Spotify's Background Coding Agent Blog Series

## Overview

This document extracts the most important lessons from Spotify's 3-part blog series on background coding agents, organized by topic for easy reference when implementing manufacturing solutions.

---

## Part 1: The Journey (1,500+ PRs)

### Core Achievement
- **1,500+ PRs merged** into production via AI agents
- **50% of all PRs** now automated via Fleet Management
- **60-90% time savings** on complex migrations

### The Problem They Solved

**Quote from Blog:**
> "While it [Fleet Management] is great for simple, repeatable tasks, making complex code changes is a challenge we've never fully solved. Defining source code transformations programmatically, by manipulating a program's abstract syntax tree (AST) or using regular expressions, requires a high degree of specialized expertise."

**Key Example:**
- Maven dependency updater: Started simple, grew to **20,000 lines of code** handling edge cases
- Only a few teams had expertise to implement sophisticated transformations
- This is why they turned to AI

### Architecture Decision

**What Changed:**
```
Before: Deterministic migration script → Fleet Management
After:  Natural language prompt → AI Agent → Fleet Management
```

**What Stayed the Same:**
- Targeting repositories
- Opening pull requests
- Getting reviews
- Merging to production

**Manufacturing Lesson:** Keep proven infrastructure, replace the hard part (transformation logic) with AI.

### Use Cases Unlocked
1. **Language modernization** (Java value types → records)
2. **Breaking upgrades** (Scio pipeline migrations)
3. **UI migrations** (Backstage frontend system)
4. **Config changes** (YAML/JSON with schema validation)

### Beyond Migrations

**Quote:**
> "What if you could also trigger the same agent from your IDE or chat, give it a task, and then go to lunch?"

They exposed the agent via Model Context Protocol (MCP) to:
- Slack (interactive task gathering)
- GitHub Enterprise
- IDEs

**Manufacturing Application:** Expose to MES, CMMS, or maintenance scheduling systems.

### Key Success Factor

**Quote:**
> "Crucially, having that CLI allows us to seamlessly switch between different agents and LLMs. In the fast-moving environment that is GenAI, being flexible and pluggable this way has already allowed us to swap out pieces multiple times."

**Manufacturing Lesson:** Build abstraction layer. Don't lock into one LLM provider.

---

## Part 2: Context Engineering

### Agent Evolution

**1. Early Open Source Agents (Goose, Aider)**
- Amazing at first
- But: "difficult to get them to reliably produce mergeable PRs"
- Problem: "writing good prompts... becomes significantly more difficult if you want to apply a change over thousands of repos"

**2. Homegrown Agentic Loop**
- 3-step process: prompt → turns with build feedback → done
- Worked for small changes
- Problems:
  - Users had to pick exact files (git-grep)
  - Too broad = overwhelm context window
  - Too limited = agent lacks context
  - Multi-file changes ran out of turns
  - Agent got lost in long sessions

**3. Claude Code (Current)**
- Task-oriented prompts (not step-by-step)
- Built-in todo list management
- Subagent spawning
- Better context management

**Endorsement from Anthropic:**
> "What Spotify's team has built here is remarkable—not just in the outcomes, but in how they got there."

### The 6 Prompt Engineering Principles

#### 1. Tailor Prompts to Agent Type

**Homegrown agent:**
```markdown
Step 1: Find all pom.xml files
Step 2: Parse dependency versions
Step 3: Update to version X.Y.Z
```

**Claude Code:**
```markdown
Update all Maven dependencies to version X.Y.Z.
Ensure compatibility with Java 17.
All tests must pass.
```

**Manufacturing Application:**
```markdown
❌ Bad (step-by-step for Claude Code):
  Step 1: Open safety_interlocks.st
  Step 2: Find IF Guard_Sensor patterns
  Step 3: Replace with SAFETY_GUARD_MONITOR

✓ Good (goal-oriented):
  Update all safety guard monitoring to use SAFETY_GUARD_MONITOR
  function block per ISO 13849-1:2023. Maintain existing sensor
  assignments. All safety tests must pass.
```

#### 2. State Preconditions

**Spotify's Pattern:**
```markdown
ONLY proceed if:
- Java version supports records
- AutoValue is being used
- Tests exist for affected classes

DO NOT proceed if:
- Already using records
- Code is in maintenance mode
```

**Manufacturing Application:**
```markdown
ONLY proceed if:
- Firmware version 3.0+ (supports new safety library)
- Backup verified in version control
- Safety test equipment available

DO NOT proceed if:
- Already using SAFETY_GUARD_MONITOR
- Certified safety PLC (requires manual certification)
- Production line currently running
```

#### 3. Use Concrete Examples

**Spotify's Approach:**
- Show exact before/after code
- Include 3-5 variations
- Cover common edge cases

**Quote:**
> "Having a handful of concrete code examples heavily influences the outcome."

**Manufacturing Example:**
```iec61131
Example 1: Single guard sensor
Before:
  IF Guard = TRUE THEN Safety_OK := TRUE; END_IF;
After:
  SAFETY_GUARD_MONITOR(Guard_1 := Guard, Guard_2 := Guard_Redundant, 
                       => Safety_OK := Safety_OK);

Example 2: Light curtain
Before:
  IF Curtain = TRUE THEN Zone_Safe := TRUE; END_IF;
After:
  SAFETY_GUARD_MONITOR(Guard_1 := Curtain_OSSD1, Guard_2 := Curtain_OSSD2,
                       => Safety_OK := Zone_Safe);
```

#### 4. Define Desired End State

**Quote:**
> "'Make this code better' is not a good prompt. The agent needs a verifiable goal so it can iterate on a solution as it goes."

**Spotify's Pattern:**
```markdown
Success Criteria:
- All AutoValue classes converted to records
- Code compiles without warnings
- All existing tests pass
- No runtime behavior changes
```

**Manufacturing Application:**
```markdown
Success Criteria:
✓ All guard monitoring uses SAFETY_GUARD_MONITOR
✓ Redundant sensor inputs configured
✓ Diagnostic outputs connected
✓ Code compiles without errors
✓ Safety verifier passes (ALL checks)
✓ Simulation tests confirm safe operation
```

#### 5. Do One Change at a Time

**Quote:**
> "It can be convenient for users to combine several related changes into one elaborate prompt, but it's more likely to get the agent in trouble because it will exhaust its context window or it will deliver a partial result."

**Anti-pattern:**
```markdown
❌ Combined prompt:
Update safety interlocks AND migrate to OPC UA AND
update HMI screens AND standardize tag names
```

**Better approach:**
```markdown
✓ Migration 1: Update safety interlocks (this prompt)
✓ Migration 2: Migrate to OPC UA (separate)
✓ Migration 3: Update HMI screens (separate)
✓ Migration 4: Standardize tags (separate)
```

#### 6. Ask Agent for Feedback

**Quote:**
> "After a session, the agent itself is in a surprisingly good position to tell you what was missing in the prompt. Use that feedback to refine future prompts."

**Manufacturing Application:**
```python
# After migration session
agent.request_feedback()

# Agent response:
# "Prompt was clear on pattern to apply, but lacked guidance on:
#  - What to do when redundant sensor not available
#  - How to handle guard sensors with existing diagnostics
#  - Whether to update comments/documentation
#  Suggest adding these edge cases to prompt."
```

### Tool Philosophy: Less is More

**Quote:**
> "We keep our background coding agent very limited in terms of tools and hooks so it can focus on generating the right code change from a prompt. This limits the information in the agent context and removes sources of unpredictable failures."

**Spotify's Tools (Minimal Set):**
1. **Verify tool** - Runs formatters, linters, tests (abstracted)
2. **Git tool** - Limited (no push, standardized commits)
3. **Bash tool** - Strict allowlist (e.g., ripgrep)

**What They DON'T Give:**
- Code search tools (include in prompt instead)
- Documentation tools (include in prompt instead)
- Network access
- File system write (except through edit tools)

**Manufacturing Application:**
```python
# Minimal tool set
tools = [
    'verify',    # Compile + safety checks (abstracted)
    'git',       # Limited (no push to production)
    'ripgrep',   # Code search only
]

# Don't add unless necessary:
# - documentation_search
# - network_access  
# - plc_connection (too dangerous)
```

### Example Prompt Structure

**Spotify's AutoValue → Record Migration:**
```markdown
# Context
[Site/project information]

# Safety Requirements
[What must not break]

# Examples
[3-5 before/after examples]

# Task
[Clear description of change]

# Success Criteria
[Verifiable outcomes]
```

See `prompts/safety_interlock_update.md` for manufacturing adaptation.

---

## Part 3: Feedback Loops

### The Three Failure Modes

**Quote:**
> "When we run agentic code changes across thousands of different software components, we worry about three primary failure modes."

**1. Agent Fails to Produce PR**
- Severity: Minor annoyance
- Impact: Manual work required
- Spotify: Can live with small failure rate

**2. Agent Produces PR That Fails CI**
- Severity: Frustrating
- Impact: Half-broken code, engineer must decide to fix or reject
- Spotify: Major time sink for reviewers

**3. Agent Produces PR That Passes CI But Is Wrong**
- Severity: **CRITICAL**
- Impact: Breaks production, erodes trust, hard to spot in reviews
- Spotify: Most serious error mode

**Manufacturing Equivalent:**
- Mode 1: Agent fails → Manual work (annoying)
- Mode 2: Agent produces code that won't compile → Wasted time
- Mode 3: Agent produces code that compiles but is unsafe → **CATASTROPHIC**

### Solution: Strong Verification Loops

#### Inner Loop (Fast Feedback)

**Spotify's Approach:**
```python
while not done and turns < max_turns:
    agent.make_change()
    result = verify()  # compile + format + lint
    if result.failed:
        agent.incorporate_feedback(result)
```

**Key Principle:**
> "The verification loop allows the agent and its underlying LLM to gradually confirm it is on the right track before committing to a change."

**Manufacturing Inner Loop:**
```python
while not done and turns < max_turns:
    agent.make_change()
    result = quick_verify()  # compile + quick safety patterns
    if result.failed:
        agent.incorporate_feedback(result)
```

#### Outer Loop (Comprehensive)

**Runs Before PR Creation:**
- Full test suite
- All verifiers
- LLM judge

**Spotify Uses Stop Hook:**
> "In the case of Claude Code, we do this with the stop hook. If one of the verifiers fails, the PR isn't opened and the user is presented with an error message."

#### Verifier Design Pattern

**Key Insight:**
> "One of the key design principles with this verification loop is that the agent doesn't know what the verification does and how, it just knows that it can (and in certain cases must) call it to verify its changes."

**Abstraction Example:**
```python
# Agent sees:
verify()  # -> {'passed': True, 'message': 'All checks passed'}

# Behind the scenes:
def verify():
    if is_maven_project():
        return MavenVerifier().verify()
    elif is_gradle_project():
        return GradleVerifier().verify()
    # etc...
```

**Benefits:**
1. **Incremental feedback** - Agent learns from each check
2. **Abstracted complexity** - Agent doesn't need to understand build systems
3. **Concise results** - Only relevant info returned
4. **Parsed output** - Complex logs simplified

**Quote:**
> "For example, many of our verifiers use regular expressions to extract only the most relevant error messages on failure and return a very short success message otherwise."

### LLM Judge

**Purpose:** Catch agents being too "creative"

**What It Catches:**
- Changes outside scope of prompt
- "Improvements" not requested
- Safety-critical modifications without authorization

**Spotify's Stats:**
> "We know from internal metrics that out of thousands of agent sessions, the judge vetoes about a quarter of them. When that happens, the agent is able to course correct half the time."

**Judge System Prompt:**
```markdown
You are reviewing an automated code change.

Original Task: [prompt]
Changes Made: [diff]

Evaluate:
1. Are all changes directly related to the task?
2. Were any safety-critical elements modified unnecessarily?
3. Is the scope appropriate (not too ambitious)?

Return: APPROVED or REJECTED with reasoning.
```

**Manufacturing Addition:**
```markdown
ADDITIONAL SAFETY CHECKS:
1. Were any safety-critical elements modified?
2. Were any certified modules touched?
3. Were timing requirements changed?
4. Was any forcing/bypassing added?

REJECT if ANY safety concerns detected.
```

### Keeping the Agent Focused

**Quote:**
> "By design, our background coding agent is built to do one thing: take a prompt and perform a code change to the best of its ability."

**What Agent CAN Do:**
- See codebase
- Edit files
- Execute verifiers

**What Agent CANNOT Do:**
- Push code
- Interact with users
- Author prompts
- Access external systems

**Security Benefits:**
> "The agent runs in a container with limited permissions, few binaries, and virtually no access to surrounding systems. It's highly sandboxed."

**Manufacturing Application:**
- Agent runs in isolated container
- No network access (except to LLM API)
- No PLC connections
- No production system access
- All deployments through separate controlled process

### Critical Quote

**Quote:**
> "With verifiers and a Judge to guide them, we've found that our agents can solve increasingly complex tasks with a high degree of reliability. Without these feedback loops, the agents often produce code that simply doesn't work."

---

## Future Directions (Spotify's Roadmap)

### 1. Expanded Platform Support

**Current:** Linux x86 only
**Planned:** macOS (iOS builds), ARM64 (backend systems)

**Manufacturing Equivalent:**
- Current: One PLC type
- Planned: Multi-vendor (Siemens, Rockwell, Mitsubishi, etc.)

### 2. CI/CD Integration

**Quote:**
> "We aim to integrate our background agent more deeply with our existing CI/CD pipelines, specifically by enabling it to act on CI checks in GitHub pull requests."

**Concept:** "Outer loop" (CI checks) complementing "inner loop" (verifiers)

**Manufacturing Equivalent:**
- Agent responds to simulation test failures
- Auto-fixes common issues
- Escalates complex failures to humans

### 3. Structured Evaluations

**Quote:**
> "We recognize the need for more structured evaluations. Implementing robust evals will allow us to systematically assess changes to system prompts, experiment with new agent architectures, and benchmark different LLM providers."

**Spotify Needs:**
- Evaluate prompt changes
- Compare agent architectures
- Benchmark LLM providers

**Manufacturing Needs:**
- Evaluate safety verification effectiveness
- Compare simulation accuracy
- Measure time savings per migration type
- Track quality metrics

---

## Key Metrics & Results

### Spotify's Numbers

**Scale:**
- 1,500+ PRs merged
- 50% of all PRs automated
- Thousands of repositories

**Time Savings:**
- 60-90% compared to manual
- ROI increases as more codebases benefit

**Success Examples:**
- Language modernization
- Breaking upgrades
- UI component migrations
- Config changes with schema validation

### Judge Statistics

**From Spotify:**
- Judge reviews thousands of sessions
- Vetoes ~25% of attempts
- Agent course-corrects 50% of vetoed attempts
- Most common trigger: Going outside prompt scope

### Manufacturing Projections

**Based on Spotify's results adapted for manufacturing:**

**Time Savings:**
- 70-75% for well-defined migrations
- 50-60% for complex migrations
- 80%+ for simple config changes

**Success Rate:**
- 90-95% with proper verification
- Lower initial rate, improves with prompt refinement

**Safety:**
- 0 incidents (mandatory with proper verification)
- 100% human review for safety-critical
- Staged rollouts reduce risk

---

## Critical Success Factors

### From Spotify's Experience

1. **Flexible Architecture**
   - Swap agents/LLMs as tech evolves
   - Keep infrastructure stable
   - Build abstraction layers

2. **Strong Verification**
   - Multiple layers
   - Fast inner loop
   - Comprehensive outer loop
   - LLM judge as final check

3. **Focused Agent**
   - One job: code transformation
   - Limited tools
   - Sandboxed execution
   - Surrounding infrastructure handles rest

4. **Iterative Prompts**
   - Start simple
   - Learn from failures
   - Refine based on agent feedback
   - Version control prompts

5. **Appropriate Scope**
   - One change type per migration
   - Clear preconditions
   - Concrete examples
   - Verifiable success criteria

### For Manufacturing

**Additional Factors:**

6. **Safety First**
   - Mandatory safety verifier
   - Human safety review
   - Comprehensive testing
   - Zero tolerance for violations

7. **Staged Rollouts**
   - Pilot sites first
   - Test environment validation
   - Gradual production deployment
   - Monitor and measure

8. **Regulatory Compliance**
   - Document everything
   - Maintain audit trail
   - Meet certification requirements
   - Regular compliance reviews

---

## Lessons Learned Summary

### What Works

✅ Natural language prompts (easier than AST manipulation)
✅ Goal-oriented descriptions (for Claude Code)
✅ Concrete examples (heavily influences outcome)
✅ Limited tool set (reduces unpredictability)
✅ Strong verification loops (inner + outer)
✅ LLM judge (catches scope creep)
✅ Sandboxed execution (security)
✅ Flexible architecture (swap components)

### What Doesn't Work

❌ Overly generic prompts
❌ Combining multiple migrations
❌ Too many tools for agent
❌ Relying on single verification layer
❌ Skipping human review for critical changes
❌ Tight coupling to specific LLM/agent

### Critical Quotes

**On Complexity:**
> "Our Maven dependency updater... has led to the transformation script growing to over 20,000 lines of code."

**On Prompting:**
> "Writing prompts is hard, and most folks don't have much experience doing it."

**On Verification:**
> "Without these feedback loops, the agents often produce code that simply doesn't work."

**On Impact:**
> "We consider this a very promising start, and we strongly believe that we are only scratching the surface of what's possible."

---

## Application to Manufacturing

### Direct Applications

1. **Fleet Management** → Multi-site PLC updates
2. **Natural Language Prompts** → Engineering-friendly
3. **Verification Loops** → Safety + compilation + simulation
4. **LLM Judge** → Safety scope verification
5. **Iterative Improvement** → Learn from each migration

### Key Adaptations

1. **Add Safety Layer** - Mandatory, comprehensive, zero tolerance
2. **Add Human Review** - Required for safety-critical
3. **Add Simulation** - Test before hardware deployment
4. **Add Compliance** - Regulatory documentation
5. **Slower Rollout** - Staged, validated, monitored

### Expected Benefits

- 70-75% time savings (similar to Spotify)
- 100% consistency (better than manual)
- Comprehensive testing (better than manual)
- Regulatory compliance (automated)
- Knowledge preservation (prompts are documentation)

---

## Conclusion

Spotify has proven that background coding agents can successfully automate complex code transformations at scale (1,500+ PRs, 60-90% time savings). The key insights:

1. **Replace complex scripts with natural language** - More accessible
2. **Strong verification loops are essential** - Inner + outer + judge
3. **Keep agents focused** - Limited scope, limited tools
4. **Iterate on prompts** - Learn from failures, refine continuously
5. **Build flexible architecture** - Tech changes fast, be ready to adapt

For manufacturing, these principles apply with additional emphasis on:
- **Safety verification** (non-negotiable)
- **Human oversight** (required for critical systems)
- **Comprehensive testing** (simulation before hardware)
- **Regulatory compliance** (automated documentation)

The potential is clear: Similar time savings with appropriate safeguards for the unique requirements of physical systems.
