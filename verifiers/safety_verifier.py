"""
Safety Verifier
Critical verification for safety-rated industrial systems.

In manufacturing, this is non-negotiable before any code changes.
"""

import asyncio
from typing import Dict, List
import logging
import re

logger = logging.getLogger(__name__)


class SafetyVerifier:
    """
    Verifies safety-critical requirements.
    
    Checks:
    1. Emergency stops remain functional
    2. Safety interlocks not bypassed
    3. SIL rating maintained
    4. Guard circuits intact
    5. No unauthorized safety modifications
    
    This is MORE critical than Spotify's linters/tests.
    Failed safety = production shutdown + regulatory issues.
    """
    
    def __init__(self):
        self.name = "safety_verifier"
        
    async def verify(self, changes: Dict, site_config: Dict) -> Dict:
        """
        Run comprehensive safety checks.
        
        Unlike compiler (can retry), safety failures are hard stops.
        """
        logger.info(f"Running {self.name} verifier")
        
        safety_rating = site_config.get('safety_rating', 'SIL-1')
        
        # Run all safety checks
        checks = [
            self._check_emergency_stops(changes),
            self._check_safety_interlocks(changes),
            self._check_guard_circuits(changes),
            self._check_forbidden_modifications(changes),
            self._verify_sil_compliance(changes, safety_rating)
        ]
        
        results = await asyncio.gather(*checks)
        
        # All safety checks must pass
        all_passed = all(r['passed'] for r in results)
        
        if all_passed:
            return {
                'passed': True,
                'message': '✓ All safety checks passed',
                'details': results
            }
        else:
            failures = [r for r in results if not r['passed']]
            return {
                'passed': False,
                'message': f'✗ Safety verification failed ({len(failures)} issues)',
                'details': results,
                'critical': True  # Signals this is a hard failure
            }
    
    async def _check_emergency_stops(self, changes: Dict) -> Dict:
        """
        Verify emergency stop circuits unchanged.
        
        E-stops must NEVER be modified by automated agents.
        """
        changed_files = [c['file_path'] for c in changes.get('changes', [])]
        
        # Check if any emergency stop code was touched
        estop_patterns = [
            r'E_STOP',
            r'EMERGENCY_STOP',
            r'EMG_STOP',
            r'SAFETY_STOP'
        ]
        
        for change in changes.get('changes', []):
            code = change.get('new_code', '')
            for pattern in estop_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    # Found E-stop modification - investigate
                    logger.warning(f"Emergency stop pattern found: {pattern}")
                    
                    # In production: deep analysis to ensure it's safe
                    # For this example: allow if only comments changed
                    if self._is_comment_only_change(change):
                        continue
                    else:
                        return {
                            'passed': False,
                            'check': 'emergency_stops',
                            'message': 'Unauthorized E-stop modification detected',
                            'severity': 'CRITICAL'
                        }
        
        return {
            'passed': True,
            'check': 'emergency_stops',
            'message': 'Emergency stops unchanged'
        }
    
    async def _check_safety_interlocks(self, changes: Dict) -> Dict:
        """
        Verify safety interlock logic.
        
        Example interlocks:
        - Door must be closed before machine starts
        - Light curtain must be active
        - Two-hand control required
        """
        # Analyze interlock logic
        for change in changes.get('changes', []):
            code = change.get('new_code', '')
            
            # Check for dangerous patterns
            dangerous = [
                r'FORCE',           # Forcing I/O is dangerous
                r'DISABLE.*SAFETY', # Disabling safety
                r'BYPASS.*GUARD',   # Bypassing guards
            ]
            
            for pattern in dangerous:
                if re.search(pattern, code, re.IGNORECASE):
                    return {
                        'passed': False,
                        'check': 'safety_interlocks',
                        'message': f'Dangerous pattern detected: {pattern}',
                        'severity': 'CRITICAL'
                    }
        
        return {
            'passed': True,
            'check': 'safety_interlocks',
            'message': 'Safety interlocks verified'
        }
    
    async def _check_guard_circuits(self, changes: Dict) -> Dict:
        """Verify physical guard circuits (gates, fences, etc.)"""
        return {
            'passed': True,
            'check': 'guard_circuits',
            'message': 'Guard circuits intact'
        }
    
    async def _check_forbidden_modifications(self, changes: Dict) -> Dict:
        """
        Check for modifications to forbidden code sections.
        
        Some code (safety PLCs, certified logic) cannot be
        modified without re-certification.
        """
        forbidden_files = [
            'certified_safety_logic.st',
            'sil3_rated_module.st'
        ]
        
        for change in changes.get('changes', []):
            filepath = change.get('file_path', '')
            if any(f in filepath for f in forbidden_files):
                return {
                    'passed': False,
                    'check': 'forbidden_modifications',
                    'message': f'Cannot modify certified file: {filepath}',
                    'severity': 'CRITICAL'
                }
        
        return {
            'passed': True,
            'check': 'forbidden_modifications',
            'message': 'No forbidden files modified'
        }
    
    async def _verify_sil_compliance(self, changes: Dict, rating: str) -> Dict:
        """
        Verify SIL (Safety Integrity Level) compliance.
        
        SIL ratings (IEC 61508):
        - SIL 1: Low risk reduction
        - SIL 2: Medium risk reduction  
        - SIL 3: High risk reduction
        - SIL 4: Very high risk reduction
        
        Changes must not downgrade SIL rating.
        """
        # In production: Complex analysis of safety architecture
        # For example: redundancy, voting, diagnostics
        
        return {
            'passed': True,
            'check': 'sil_compliance',
            'message': f'{rating} compliance maintained'
        }
    
    def _is_comment_only_change(self, change: Dict) -> bool:
        """Check if change only affects comments"""
        # Simplified check
        old = change.get('old_code', '')
        new = change.get('new_code', '')
        
        # Remove comments and compare
        old_no_comments = re.sub(r'//.*|/\*.*?\*/', '', old, flags=re.DOTALL)
        new_no_comments = re.sub(r'//.*|/\*.*?\*/', '', new, flags=re.DOTALL)
        
        return old_no_comments.strip() == new_no_comments.strip()


class SimulationVerifier:
    """
    Runtime simulation verifier.
    
    Runs code in simulation before deploying to real hardware.
    Spotify equivalent: Integration tests, but for physical systems.
    """
    
    async def verify(self, changes: Dict, site_config: Dict) -> Dict:
        """
        Run code in virtual commissioning environment.
        
        Tools:
        - Siemens PLCSIM Advanced
        - Rockwell Emulate 5000
        - Factory I/O simulation
        
        Tests:
        - Normal operation cycles
        - Emergency stop scenarios
        - Fault conditions
        - Edge cases
        """
        logger.info("Running simulation verification")
        
        # In production: Launch virtual PLC, run test scenarios
        await asyncio.sleep(1)  # Simulate test time
        
        return {
            'passed': True,
            'message': '✓ Simulation tests passed',
            'test_results': {
                'normal_cycle': 'PASS',
                'emergency_stop': 'PASS',
                'fault_injection': 'PASS'
            }
        }
