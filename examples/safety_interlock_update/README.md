# Example: Safety Interlock Update Migration

This example demonstrates a complete end-to-end migration using background coding agents, inspired by Spotify's approach.

## Scenario

Your manufacturing company needs to update safety interlock logic across 50+ production lines to meet the new ISO 13849-1:2023 standard. Manual implementation would take weeks. Using background coding agents, you can complete it in days with higher consistency.

## Step-by-Step Guide

### 1. Prepare the Migration

```bash
# Navigate to fleet manager
cd fleet-manager

# Review the prompt
cat ../prompts/safety_interlock_update.md

# Check target sites
grep "safety_rating: SIL-2" config.yaml
```

### 2. Run Dry-Run First

**Always test with dry-run before production changes!**

```bash
# Dry run on all SIL-2 sites
python cli.py safety-interlock-update-iso13849 --dry-run

# Output:
# INFO: Starting migration: safety-interlock-update-iso13849
# INFO: Targeting 3 sites
# INFO: Processing site: Plant-01-Assembly
# INFO: Running plc_compiler verifier
# INFO: Running safety_verifier verifier
# ✓ Created change request for Plant-01-Assembly
# ...
# ============================================================
# Migration Summary: 3/3 successful
# ============================================================
# ✓ Plant-01-Assembly
# ✓ Plant-01-Welding  
# ✓ Plant-03-CNC
```

### 3. Review Agent Logs

The agent maintains detailed logs showing its decision process:

```json
{
  "session_id": "migration-20241229-001",
  "site": "Plant-01-Assembly",
  "prompt": "Update safety interlock logic...",
  "turns": [
    {
      "turn": 1,
      "action": "discovered files",
      "files": ["src/safety_interlocks.st", "src/main_program.st"]
    },
    {
      "turn": 2,
      "action": "created plan",
      "steps": ["update guard monitoring", "add diagnostics", "verify"]
    },
    {
      "turn": 3,
      "action": "made change",
      "file": "src/safety_interlocks.st",
      "verification": "passed"
    }
  ],
  "verifications": {
    "compiler": "✓ passed",
    "safety": "✓ passed",
    "judge": "✓ passed - changes within scope"
  },
  "result": "success"
}
```

### 4. Review Generated Changes

Each site gets a Change Authorization Request (CAR):

```
CAR-Plant-01-Assembly-20241229/
├── diff.patch                  # Code changes
├── verification_report.pdf     # Safety verification
├── simulation_results.json     # Test results
└── review_checklist.md        # For human review
```

### 5. Human Review (Critical!)

For safety-critical changes, human review is mandatory:

```markdown
# Review Checklist for CAR-Plant-01-Assembly-20241229

## Automated Verifications ✓
- [x] Code compiles successfully
- [x] Safety verifier passed
- [x] Simulation tests passed
- [x] LLM judge approved (within scope)

## Human Review Required
- [ ] Safety engineer review
- [ ] Compare against ISO 13849-1:2023 standard
- [ ] Verify redundant sensor configuration
- [ ] Check diagnostic logging
- [ ] Confirm no unauthorized changes

## Sign-off
Safety Engineer: _______________ Date: ___________
Plant Manager: _________________ Date: ___________
```

### 6. Deploy to Test Environment

```bash
# Deploy to test system
python cli.py safety-interlock-update-iso13849 \
  --sites Plant-01-Assembly \
  --environment test

# Run extended verification
python ../verifiers/simulation_verifier.py \
  --car CAR-Plant-01-Assembly-20241229 \
  --run-extended-tests
```

### 7. Production Deployment

After successful test verification:

```bash
# Deploy to production
python cli.py safety-interlock-update-iso13849 \
  --sites Plant-01-Assembly \
  --environment production \
  --require-approval
```

## Results

### Time Savings

| Method | Time per Site | Total Time (50 sites) |
|--------|---------------|------------------------|
| Manual | 8 hours | 400 hours (10 weeks) |
| Agent-Assisted | 2 hours | 100 hours (2.5 weeks) |
| **Savings** | **75%** | **300 hours** |

### Quality Improvements

- **Consistency**: 100% identical implementation pattern
- **Compliance**: All changes verified against standard
- **Testing**: Every change simulated before deployment
- **Documentation**: Automatic generation of change records

## Lessons from Spotify Applied

### 1. Context Engineering (Part 2)

Our prompt follows Spotify's principles:

✓ **States preconditions clearly**
```
ONLY proceed if:
- Firmware version supports new library
- Backup verified
```

✓ **Uses concrete examples**
```iec61131
Before: IF Guard_Sensor = TRUE THEN...
After: SAFETY_GUARD_MONITOR(...)
```

✓ **Defines success criteria**
```
✓ Code compiles
✓ Safety verification passes
✓ Simulation tests pass
```

✓ **Does one change at a time**
- This migration only updates guard monitoring
- Emergency stops are separate migration
- IO mapping is separate migration

### 2. Verification Loops (Part 3)

We implemented multiple verification layers:

**Inner Loop (Fast Feedback)**
- Compilation check after each change
- Syntax validation
- Quick safety checks

**Outer Loop (Comprehensive)**
- Full safety verification
- Simulation tests
- LLM judge review

**Human Loop (Safety Critical)**
- Safety engineer review
- Test environment validation
- Production approval

### 3. LLM Judge

The judge catches scope creep:

```python
# Example: Agent tried to "improve" code beyond scope
judge_evaluation = """
REJECTED: Agent added performance optimizations not in prompt.
- Task: Update safety interlock pattern
- Found: Also optimized scan time (not requested)
- Action: Revert optimization, keep only safety updates
"""
```

## Common Issues & Solutions

### Issue 1: Agent Gets Lost

**Symptom**: Agent makes incorrect changes after turn 5-6

**Solution**: Reduce context window, simplify prompt
```python
# From Spotify: "Do one change at a time"
# Split into smaller migrations
```

### Issue 2: Verification Fails Unexpectedly

**Symptom**: Code compiles but safety verifier rejects

**Solution**: Check for edge cases in prompt
```markdown
What NOT to change:
- Emergency stop circuits
- Certified modules
```

### Issue 3: Too Generic

**Symptom**: Agent produces different solutions per site

**Solution**: More concrete examples
```markdown
Always use THIS exact pattern:
SAFETY_GUARD_MONITOR(...)
NOT variations or alternatives
```

## Next Steps

1. **Expand to More Sites**: Roll out to remaining 47 sites
2. **Monitor Results**: Track real-world performance vs simulation
3. **Iterate Prompt**: Use feedback to improve prompt
4. **New Migrations**: Apply same pattern to other updates

## Additional Resources

- Full prompt: `../prompts/safety_interlock_update.md`
- Fleet config: `../fleet-manager/config.yaml`
- Verifiers: `../verifiers/`
- Agent implementation: `../agents/plc_agent.py`

---

**Key Takeaway**: Background coding agents can handle complex, safety-critical migrations when combined with strong verification loops and appropriate human oversight.
