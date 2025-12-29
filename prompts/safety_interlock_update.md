# Migration: Update Safety Interlocks to New Standard

## Overview
Update safety interlock logic across all production lines to comply with new ISO 13849-1:2023 standard.

## Target Sites
- All sites with SIL-2 or SIL-3 rating
- PLC firmware version 2.9+ (Siemens) or 32.x+ (Rockwell)

## Migration Prompt

You are tasked with updating safety interlock logic in industrial PLC code to meet the new ISO 13849-1:2023 standard requirements.

### Preconditions
**ONLY proceed if:**
1. The PLC project contains safety interlock functions
2. Current safety logic uses the old guard monitoring pattern
3. The firmware version supports the new safety library (v3.0+)
4. A backup of the original code has been verified

**DO NOT proceed if:**
- Safety functions are already using the new standard
- The project contains certified safety PLCs (these need manual review)
- Test equipment is not available to verify changes

### Required Changes

Update the safety interlock pattern from:

```iec61131
(* OLD PATTERN - Deprecated *)
IF Guard_Sensor_1 = TRUE AND Guard_Sensor_2 = TRUE THEN
    Safety_OK := TRUE;
ELSE
    Safety_OK := FALSE;
    Machine_Enable := FALSE;
END_IF;
```

To the new standard with redundancy and diagnostics:

```iec61131
(* NEW PATTERN - ISO 13849-1:2023 *)
SAFETY_GUARD_MONITOR(
    Guard_Sensor_1 := Guard_Sensor_1,
    Guard_Sensor_2 := Guard_Sensor_2,
    Test_Pulse := Safety_Test_Pulse,
    => Safety_OK := Safety_OK,
    => Diagnostic := Guard_Diagnostic,
    => Error := Guard_Error
);

IF Safety_OK = TRUE AND Guard_Error = FALSE THEN
    Machine_Enable := TRUE;
ELSE
    Machine_Enable := FALSE;
    // Log diagnostic info
    IF Guard_Error = TRUE THEN
        Error_Logger(Guard_Diagnostic);
    END_IF;
END_IF;
```

### Examples

**Example 1: Single Guard Door**

Before:
```iec61131
IF DoorClosed_Sensor = TRUE THEN
    Allow_Operation := TRUE;
END_IF;
```

After:
```iec61131
SAFETY_GUARD_MONITOR(
    Guard_Sensor_1 := DoorClosed_Sensor,
    Guard_Sensor_2 := DoorClosed_Sensor_Redundant,
    Test_Pulse := Safety_Test_Pulse,
    => Safety_OK := Door_Safety_OK
);

IF Door_Safety_OK = TRUE THEN
    Allow_Operation := TRUE;
END_IF;
```

**Example 2: Light Curtain**

Before:
```iec61131
IF Light_Curtain_OK = TRUE THEN
    Zone_Safe := TRUE;
END_IF;
```

After:
```iec61131
SAFETY_GUARD_MONITOR(
    Guard_Sensor_1 := Light_Curtain_OSSD1,
    Guard_Sensor_2 := Light_Curtain_OSSD2,
    Test_Pulse := Safety_Test_Pulse,
    => Safety_OK := Zone_Safe,
    => Diagnostic := LC_Diagnostic
);
```

### Critical Requirements

1. **Redundancy**: All safety sensors must have redundant monitoring
2. **Diagnostics**: Must log diagnostic information
3. **Test Pulse**: Must implement periodic safety function testing
4. **Failsafe**: Default state must be SAFE (machine disabled)

### What NOT to Change

- Emergency stop circuits (separate standard)
- Certified SIL-3 modules (require manual certification)
- Safety PLC configuration (only application code)
- IO mapping (sensors stay on same addresses)

### Success Criteria

The migration is successful when:
1. ✓ All guard monitoring uses new SAFETY_GUARD_MONITOR function block
2. ✓ Redundant sensor inputs are configured
3. ✓ Diagnostic outputs are logged
4. ✓ Code compiles without errors
5. ✓ Safety verification passes
6. ✓ Simulation tests confirm safe operation
7. ✓ No emergency stop logic was modified

### Verification Steps

After making changes, you MUST verify:
1. Call the verify tool to compile the code
2. Ensure safety verifier passes (NO exceptions)
3. Confirm simulation tests pass
4. Check that all old patterns are replaced

### Notes

- This change is required for compliance by Q2 2025
- Estimated time: 60-90% faster than manual implementation
- Changes require safety review before production deployment
- Test in simulation environment before deploying to hardware

---

## Migration Metadata

```yaml
name: "safety-interlock-update-iso13849"
version: "1.0"
created: "2024-12-29"
author: "Fleet Management System"
requires_review: true
safety_critical: true
```
