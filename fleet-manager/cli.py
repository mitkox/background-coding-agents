#!/usr/bin/env python3
"""
Fleet Manager CLI for Industrial Manufacturing
Inspired by Spotify's Fleet Management system for automating code changes across repositories
"""

import argparse
import yaml
import asyncio
from pathlib import Path
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FleetManager:
    """
    Manages automated migrations across multiple manufacturing sites.
    Similar to Spotify's Fleet Management that handles 50% of their PRs.
    """
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.sites = self.config.get('sites', [])
        
    async def run_migration(self, migration_name: str, dry_run: bool = True):
        """
        Execute a migration across all configured sites.
        
        Process (similar to Spotify's approach):
        1. Load migration prompt
        2. Target sites based on selection criteria
        3. Run agent with prompt + verifiers
        4. Generate change requests
        5. Run verification loops
        6. Submit for review (human in the loop for safety-critical)
        """
        logger.info(f"Starting migration: {migration_name}")
        
        # Load migration configuration
        migration_config = self._load_migration(migration_name)
        prompt = migration_config['prompt']
        
        # Filter target sites
        target_sites = self._filter_sites(migration_config.get('target_filter', {}))
        logger.info(f"Targeting {len(target_sites)} sites")
        
        # Execute migration on each site
        results = []
        for site in target_sites:
            logger.info(f"Processing site: {site['name']}")
            result = await self._run_agent_on_site(
                site=site,
                prompt=prompt,
                migration_config=migration_config,
                dry_run=dry_run
            )
            results.append(result)
            
        # Summary
        self._print_summary(results)
        
        return results
    
    def _load_migration(self, name: str) -> Dict:
        """Load migration definition from prompts directory"""
        migration_path = Path(__file__).parent / 'migrations' / f'{name}.yaml'
        with open(migration_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _filter_sites(self, filters: Dict) -> List[Dict]:
        """Filter sites based on criteria (PLC type, version, location, etc.)"""
        filtered = self.sites
        
        if 'plc_type' in filters:
            filtered = [s for s in filtered if s.get('plc_type') == filters['plc_type']]
        
        if 'firmware_version' in filters:
            filtered = [s for s in filtered 
                       if s.get('firmware_version', '').startswith(filters['firmware_version'])]
        
        return filtered
    
    async def _run_agent_on_site(self, site: Dict, prompt: str, 
                                  migration_config: Dict, dry_run: bool) -> Dict:
        """
        Run the coding agent on a single site.
        
        Key principles from Spotify's Part 2:
        - Tailor prompts to the agent
        - State preconditions clearly
        - Use concrete examples
        - Define desired end state (tests)
        - Do one change at a time
        """
        from agents.plc_agent import PLCAgent
        from verifiers.safety_verifier import SafetyVerifier
        from verifiers.plc_compiler_verifier import PLCCompilerVerifier
        
        agent = PLCAgent(site_config=site)
        
        # Build full context for agent
        full_prompt = self._build_prompt(prompt, site, migration_config)
        
        try:
            # Run agent
            changes = await agent.execute(full_prompt)
            
            # Verification loops (Spotify Part 3 concept)
            verifier_results = []
            
            # 1. Compile check
            compiler = PLCCompilerVerifier()
            compile_result = await compiler.verify(changes, site)
            verifier_results.append(('compile', compile_result))
            
            # 2. Safety verification
            safety = SafetyVerifier()
            safety_result = await safety.verify(changes, site)
            verifier_results.append(('safety', safety_result))
            
            # 3. LLM Judge (check if changes are within scope)
            judge_result = await self._run_llm_judge(changes, prompt)
            verifier_results.append(('judge', judge_result))
            
            all_passed = all(result[1]['passed'] for result in verifier_results)
            
            if all_passed and not dry_run:
                # Create change request
                change_request = self._create_change_request(site, changes)
                logger.info(f"✓ Created change request for {site['name']}")
            else:
                logger.warning(f"⚠ Verification failed for {site['name']}")
            
            return {
                'site': site['name'],
                'success': all_passed,
                'changes': changes,
                'verifications': verifier_results,
                'dry_run': dry_run
            }
            
        except Exception as e:
            logger.error(f"✗ Error processing {site['name']}: {e}")
            return {
                'site': site['name'],
                'success': False,
                'error': str(e)
            }
    
    def _build_prompt(self, base_prompt: str, site: Dict, config: Dict) -> str:
        """
        Build comprehensive prompt with context.
        
        Following Spotify's lessons:
        - Include examples
        - State preconditions
        - Define success criteria
        - Keep focused on one change
        """
        context = f"""
# Site Context
- Name: {site['name']}
- PLC Type: {site['plc_type']}
- Firmware: {site['firmware_version']}
- Production Line: {site.get('line_type', 'Unknown')}

# Safety Requirements
- All safety interlocks must remain functional
- Emergency stops cannot be modified
- Changes must maintain SIL rating

# Examples
{config.get('examples', '')}

# Task
{base_prompt}

# Success Criteria
- Code compiles without errors
- All existing tests pass
- Safety verification passes
- No unintended side effects
"""
        return context
    
    async def _run_llm_judge(self, changes: Dict, original_prompt: str) -> Dict:
        """
        LLM-as-judge verification (Spotify Part 3 concept).
        
        Checks:
        - Are changes within scope of prompt?
        - Any "creative" additions?
        - Safety-critical modifications?
        """
        # In production, call LLM API with system prompt
        judge_prompt = f"""
You are reviewing an automated code change for industrial manufacturing equipment.

Original Task: {original_prompt}

Changes Made: {changes}

Evaluate:
1. Are all changes directly related to the task?
2. Were any safety-critical elements modified unnecessarily?
3. Is the scope appropriate (not too ambitious)?

Return: APPROVED or REJECTED with reasoning.
"""
        
        # Placeholder - would call actual LLM
        # For this example, we'll simulate approval
        return {
            'passed': True,
            'reasoning': 'Changes are within scope and maintain safety requirements'
        }
    
    def _create_change_request(self, site: Dict, changes: Dict) -> str:
        """
        Create a change request (similar to PR in Spotify's system).
        In manufacturing: CAR (Change Authorization Request)
        """
        car_id = f"CAR-{site['name']}-{changes.get('timestamp', 'DRAFT')}"
        logger.info(f"Created {car_id}")
        return car_id
    
    def _print_summary(self, results: List[Dict]):
        """Print summary of migration results"""
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        
        print("\n" + "="*60)
        print(f"Migration Summary: {successful}/{total} successful")
        print("="*60)
        
        for result in results:
            status = "✓" if result['success'] else "✗"
            print(f"{status} {result['site']}")


async def main():
    parser = argparse.ArgumentParser(
        description='Fleet Manager for Industrial Manufacturing Automation'
    )
    parser.add_argument('migration', help='Migration name to execute')
    parser.add_argument('--config', default='config.yaml', help='Configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    parser.add_argument('--sites', nargs='+', help='Specific sites to target')
    
    args = parser.parse_args()
    
    manager = FleetManager(args.config)
    await manager.run_migration(args.migration, dry_run=args.dry_run)


if __name__ == '__main__':
    asyncio.run(main())
