# Migration: Protocol Migration from Modbus to OPC UA

## Overview
Migrate communication infrastructure from legacy Modbus TCP to modern OPC UA across all production lines. This enables better security, standardization, and Industry 4.0 readiness.

## Target Sites
- All sites currently using Modbus TCP
- PLC types: Siemens S7 (all versions), Allen-Bradley ControlLogix

## Migration Prompt

You are tasked with migrating industrial communication protocol from Modbus TCP to OPC UA in PLC code and HMI/SCADA configurations.

### Preconditions

**ONLY proceed if:**
1. The PLC firmware supports OPC UA (Siemens: v4.0+, Rockwell: v30+)
2. OPC UA server module is installed and configured
3. Network infrastructure supports OPC UA traffic (port 4840)
4. Communication mapping documentation exists
5. Target HMI/SCADA system supports OPC UA client

**DO NOT proceed if:**
- OPC UA server is not configured
- Security certificates are not installed
- Production downtime window is not scheduled
- Rollback plan is not approved

### Task Overview

Migrate from Modbus TCP communication pattern to OPC UA:

1. Replace Modbus function blocks with OPC UA equivalents
2. Update data addressing from Modbus registers to OPC UA nodes
3. Implement OPC UA security (certificates, authentication)
4. Update HMI/SCADA client configurations
5. Preserve all data semantics and update rates

### Examples

#### Example 1: Reading Temperature Sensor

**Before (Modbus TCP):**
```iec61131
(* Modbus TCP Read - Holding Register *)
MB_CLIENT(
    Connect := TRUE,
    IP_Addr := '192.168.1.100',
    Function := 3,          // Read Holding Registers
    Start_Addr := 4001,     // Register 40001
    Quantity := 1,
    => Data := Temperature_Raw,
    => Done := MB_Done,
    => Error := MB_Error
);

Temperature_Celsius := WORD_TO_REAL(Temperature_Raw) / 10.0;
```

**After (OPC UA):**
```iec61131
(* OPC UA Read - Structured addressing *)
OPCUA_READ(
    Active := TRUE,
    ServerEndpoint := 'opc.tcp://192.168.1.100:4840',
    NodeId := 'ns=2;s=Sensors.Temperature.Zone1',
    SecurityPolicy := 'Basic256Sha256',
    => Value := Temperature_Celsius,
    => Quality := OPCUA_Quality,
    => Done := OPCUA_Done,
    => Error := OPCUA_Error
);

(* No conversion needed - OPC UA provides typed data *)
```

#### Example 2: Writing Setpoint

**Before (Modbus TCP):**
```iec61131
(* Modbus TCP Write - Single Register *)
MB_CLIENT_WRITE(
    Connect := TRUE,
    IP_Addr := '192.168.1.100',
    Function := 6,          // Write Single Register
    Start_Addr := 4100,
    Data := REAL_TO_WORD(Setpoint_Value * 10.0),
    => Done := MB_Write_Done,
    => Error := MB_Write_Error
);
```

**After (OPC UA):**
```iec61131
(* OPC UA Write - Typed variable *)
OPCUA_WRITE(
    Active := TRUE,
    ServerEndpoint := 'opc.tcp://192.168.1.100:4840',
    NodeId := 'ns=2;s=Controls.Setpoint.Zone1',
    Value := Setpoint_Value,
    SecurityPolicy := 'Basic256Sha256',
    => Done := OPCUA_Write_Done,
    => Error := OPCUA_Write_Error
);
```

#### Example 3: Monitoring Connection Status

**Before (Modbus TCP):**
```iec61131
IF MB_Error = TRUE THEN
    Connection_Status := 'Modbus Error';
    Alarm_Comms_Lost := TRUE;
END_IF;
```

**After (OPC UA):**
```iec61131
IF OPCUA_Error = TRUE OR OPCUA_Quality.QualityCode <> 16#00000000 THEN
    Connection_Status := 'OPC UA Error';
    Alarm_Comms_Lost := TRUE;
    
    (* Enhanced diagnostics available *)
    Last_Error_Code := OPCUA_Error_Code;
    Last_Error_Time := OPCUA_Error_Timestamp;
END_IF;
```

### Data Mapping

Create a mapping table from Modbus addresses to OPC UA Node IDs:

| Modbus Address | Data Type | OPC UA Node ID | Description |
|----------------|-----------|----------------|-------------|
| 40001 | WORD (temp*10) | ns=2;s=Sensors.Temperature.Zone1 | Temperature sensor |
| 40002 | WORD (press*100) | ns=2;s=Sensors.Pressure.Zone1 | Pressure sensor |
| 40100 | WORD (sp*10) | ns=2;s=Controls.Setpoint.Zone1 | Setpoint value |
| 40101 | WORD (0/1) | ns=2;s=Controls.Enable.Zone1 | Enable control |

### Security Configuration

OPC UA requires security configuration:

```iec61131
(* OPC UA Client Configuration *)
OPCUA_Config(
    ServerEndpoint := 'opc.tcp://server.local:4840',
    SecurityMode := SecurityMode.SignAndEncrypt,
    SecurityPolicy := 'Basic256Sha256',
    AuthenticationMode := UserNamePassword,
    UserName := 'PLCClient',
    Password := PlcPassword,          // From secure storage
    CertificateStore := '/certs/',
    => Connected := OPCUA_Connected,
    => SessionID := OPCUA_SessionID
);
```

### Critical Requirements

1. **Data Integrity**: All data points must maintain same update rates
2. **Security**: Must use SignAndEncrypt security mode
3. **Backwards Compatibility**: Keep Modbus active during testing phase
4. **Error Handling**: Implement comprehensive error logging
5. **Performance**: OPC UA update rate ≤ Modbus update rate

### Migration Steps

1. **Identify Modbus Communications**
   - Find all MB_CLIENT, MB_CLIENT_WRITE function blocks
   - Document register addresses and purposes
   - Identify data types and scaling

2. **Configure OPC UA Server**
   - Create information model with structured namespaces
   - Map Modbus registers to OPC UA nodes
   - Configure security certificates

3. **Update PLC Code**
   - Replace Modbus function blocks with OPC UA equivalents
   - Update addressing from registers to node IDs
   - Remove data type conversions (if OPC UA provides correct types)
   - Implement security configuration

4. **Update HMI/SCADA**
   - Configure OPC UA client connections
   - Update tag database from Modbus to OPC UA
   - Test all graphics and trends

5. **Testing Phase**
   - Run parallel Modbus + OPC UA for validation
   - Compare data consistency
   - Test failover scenarios
   - Verify performance metrics

### What NOT to Change

- Do not modify control logic algorithms
- Do not change data update rates without approval
- Do not remove Modbus until OPC UA is validated
- Do not modify safety-critical communications (separate review)
- Do not change network infrastructure

### Success Criteria

The migration is successful when:
1. ✓ All Modbus read operations replaced with OPC UA reads
2. ✓ All Modbus write operations replaced with OPC UA writes
3. ✓ Security configured (certificates, authentication)
4. ✓ Code compiles without errors
5. ✓ Communication tests pass in simulation
6. ✓ Data accuracy verified (OPC UA matches old Modbus values)
7. ✓ Performance meets requirements (update rates maintained)
8. ✓ HMI/SCADA updated and tested
9. ✓ Error handling and diagnostics implemented

### Verification Steps

After making changes, you MUST verify:
1. Call verify tool to compile PLC code
2. Run communication simulation tests
3. Verify security configuration is correct
4. Check performance metrics (scan time, update rates)
5. Test error handling scenarios
6. Validate HMI/SCADA connectivity

### Rollback Plan

If issues occur:
1. Switch back to Modbus communication (keep code during testing)
2. Document issues for root cause analysis
3. Schedule remediation
4. Re-test before next attempt

### Benefits

- **Security**: Encrypted communication, user authentication
- **Standardization**: Industry standard protocol
- **Diagnostics**: Better error information and quality status
- **Scalability**: Easier to add new devices
- **Industry 4.0**: Ready for cloud connectivity and analytics

### Notes

- Migration timeline: 2-3 months across all sites
- Requires coordination with IT for network/security
- Test thoroughly in non-production environment first
- Consider site-by-site rollout to minimize risk
- Estimated time savings: 70% vs manual migration

---

## Migration Metadata

```yaml
name: "protocol-migration-modbus-to-opcua"
version: "1.0"
created: "2024-12-29"
author: "Fleet Management System"
requires_review: true
requires_downtime: true
estimated_time_per_site: "2 hours"
complexity: "high"
```
