#!/usr/bin/env python3
"""
Workflow Definition Validator

Validates workflow JSON files against the Universal Workflow Schema v1.0.0
Performs structural validation, semantic checks, and security audits.

Usage:
    python workflow_validator.py <workflow_file.json>
    python workflow_validator.py workflow_map.json --strict
"""

import json
import sys
import re
from typing import Dict, List, Any, Set, Tuple
from pathlib import Path
import argparse


class WorkflowValidator:
    """Validates workflow definitions for correctness and best practices"""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        
    def validate(self, workflow: Dict[str, Any]) -> bool:
        """Run all validation checks"""
        print("[*] Validating workflow definition...\n")
        
        # Structural validation
        self._validate_structure(workflow)
        self._validate_metadata(workflow.get('metadata', {}))
        self._validate_inputs(workflow.get('inputs', {}))
        self._validate_security(workflow.get('security', {}))
        self._validate_steps(workflow.get('steps', []))
        
        # Semantic validation
        self._validate_dependencies(workflow.get('steps', []))
        self._validate_data_flow(workflow.get('steps', []))
        
        # Security audit
        self._audit_security(workflow)
        
        # Best practices
        self._check_best_practices(workflow)
        
        return len(self.errors) == 0
    
    def _validate_structure(self, workflow: Dict[str, Any]):
        """Validate top-level structure"""
        required_keys = ['metadata', 'inputs', 'security', 'steps']
        
        for key in required_keys:
            if key not in workflow:
                self.errors.append(f"Missing required key: '{key}'")
        
        # Check for unknown keys
        valid_keys = {
            'metadata', 'inputs', 'security', 'validation',
            'steps', 'execution_config', 'observability', 'documentation'
        }
        
        unknown = set(workflow.keys()) - valid_keys
        if unknown:
            self.warnings.append(f"Unknown top-level keys: {unknown}")
    
    def _validate_metadata(self, metadata: Dict[str, Any]):
        """Validate metadata section"""
        required = ['workflow_name', 'workflow_id', 'platform', 'schema_version']
        
        for field in required:
            if field not in metadata:
                self.errors.append(f"metadata.{field} is required")
        
        # Validate workflow_name format
        if 'workflow_name' in metadata:
            name = metadata['workflow_name']
            if not re.match(r'^[a-z][a-z0-9_]*$', name):
                self.errors.append(
                    f"workflow_name '{name}' must be snake_case starting with a letter"
                )
        
        # Validate schema version
        if 'schema_version' in metadata:
            version = metadata['schema_version']
            if not re.match(r'^\d+\.\d+\.\d+$', version):
                self.errors.append(f"schema_version '{version}' must be semver (e.g., 1.0.0)")
        
        # Check for idempotency declaration
        if 'idempotent' not in metadata:
            self.warnings.append("Consider declaring 'idempotent' status in metadata")
    
    def _validate_inputs(self, inputs: Dict[str, Any]):
        """Validate inputs section"""
        if 'required' not in inputs and 'optional' not in inputs:
            self.warnings.append("No inputs defined (required or optional)")
            return
        
        # Validate required inputs
        for name, param in inputs.get('required', {}).items():
            if 'type' not in param:
                self.errors.append(f"Input '{name}' missing 'type' field")
            if 'description' not in param:
                self.warnings.append(f"Input '{name}' missing description")
            
            # Check for validation rules
            if param.get('type') == 'string' and 'validation' not in param:
                self.info.append(
                    f"Input '{name}' (string) has no validation rules (consider adding pattern/length)"
                )
    
    def _validate_security(self, security: Dict[str, Any]):
        """Validate security configuration"""
        if not security:
            self.errors.append("Security configuration is required")
            return
        
        if 'auth_required' not in security:
            self.errors.append("security.auth_required must be declared")
        
        if 'secrets_handling' not in security:
            self.errors.append("security.secrets_handling must be declared")
        elif security['secrets_handling'] not in ['runtime_injected', 'vault', 'env_var']:
            self.errors.append(f"Invalid secrets_handling: {security['secrets_handling']}")
        
        # Check for credential-agnostic design
        if security.get('secrets_handling') == 'runtime_injected':
            self.info.append("[+] Credential-agnostic design (runtime_injected)")
        else:
            self.warnings.append("Consider using 'runtime_injected' for better security")
        
        # Check for RBAC
        if 'minimum_role' not in security:
            self.warnings.append("Consider specifying 'minimum_role' for RBAC")
        
        # Check for rate limiting
        if 'rate_limit' not in security:
            self.warnings.append("Consider adding rate_limit configuration")
    
    def _validate_steps(self, steps: List[Dict[str, Any]]):
        """Validate individual steps"""
        if not steps:
            self.errors.append("Workflow must have at least one step")
            return
        
        step_ids: Set[str] = set()
        
        for i, step in enumerate(steps):
            step_num = i + 1
            
            # Required fields
            if 'id' not in step:
                self.errors.append(f"Step {step_num} missing 'id' field")
                continue
            
            step_id = step['id']
            
            # Check ID uniqueness
            if step_id in step_ids:
                self.errors.append(f"Duplicate step ID: '{step_id}'")
            step_ids.add(step_id)
            
            # Check ID format
            if not re.match(r'^[a-z][a-z0-9_]*$', step_id):
                self.errors.append(
                    f"Step ID '{step_id}' must be snake_case starting with a letter"
                )
            
            # Required fields
            for field in ['operation', 'api_endpoint']:
                if field not in step:
                    self.errors.append(f"Step '{step_id}' missing '{field}' field")
            
            # Validate operation type
            if step.get('operation') not in ['query', 'mutation', 'workflow', 'custom']:
                self.errors.append(
                    f"Step '{step_id}' has invalid operation: {step.get('operation')}"
                )
            
            # Check for error handling
            if 'error_handling' not in step:
                self.warnings.append(f"Step '{step_id}' has no error_handling configuration")
            
            # Check for outputs on mutations
            if step.get('operation') == 'mutation' and 'outputs' not in step:
                self.warnings.append(
                    f"Mutation step '{step_id}' should declare 'outputs' for downstream dependencies"
                )
            
            # Check for telemetry
            if 'telemetry' not in step:
                self.info.append(f"Step '{step_id}' has no telemetry configuration")
    
    def _validate_dependencies(self, steps: List[Dict[str, Any]]):
        """Validate step dependencies form a valid DAG"""
        step_ids = {step['id'] for step in steps if 'id' in step}
        
        for step in steps:
            step_id = step.get('id', 'unknown')
            depends_on = step.get('depends_on', [])
            
            for dep_id in depends_on:
                if dep_id not in step_ids:
                    self.errors.append(
                        f"Step '{step_id}' depends on unknown step '{dep_id}'"
                    )
        
        # Check for circular dependencies (simplified)
        if self._has_circular_dependency(steps):
            self.errors.append("Circular dependency detected in workflow steps")
    
    def _has_circular_dependency(self, steps: List[Dict[str, Any]]) -> bool:
        """Detect circular dependencies using DFS"""
        graph = {step['id']: step.get('depends_on', []) for step in steps if 'id' in step}
        
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        
        return False
    
    def _validate_data_flow(self, steps: List[Dict[str, Any]]):
        """Validate data flows between steps"""
        available_outputs = {}
        
        for step in steps:
            step_id = step.get('id', 'unknown')
            
            # Check if inputs reference valid outputs
            inputs_str = json.dumps(step.get('inputs', {}))
            
            # Find template references like {{steps.x.outputs.y}}
            refs = re.findall(r'\{\{steps\.([^.]+)\.outputs\.([^}]+)\}\}', inputs_str)
            
            for ref_step, ref_field in refs:
                if ref_step not in available_outputs:
                    self.errors.append(
                        f"Step '{step_id}' references output from unknown step '{ref_step}'"
                    )
                elif ref_field not in available_outputs[ref_step]:
                    self.warnings.append(
                        f"Step '{step_id}' references '{ref_field}' which is not declared "
                        f"in step '{ref_step}' outputs"
                    )
            
            # Register this step's outputs
            if 'outputs' in step:
                available_outputs[step_id] = set(step['outputs'].keys())
    
    def _audit_security(self, workflow: Dict[str, Any]):
        """Perform security audit"""
        # Check for hardcoded credentials
        workflow_str = json.dumps(workflow).lower()
        
        suspicious_patterns = [
            (r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', "Possible hardcoded password"),
            (r'token["\']?\s*[:=]\s*["\'][^"\']+["\']', "Possible hardcoded token"),
            (r'api[_-]?key["\']?\s*[:=]\s*["\'][^"\']+["\']', "Possible hardcoded API key"),
            (r'secret["\']?\s*[:=]\s*["\'][^"\']+["\']', "Possible hardcoded secret"),
        ]
        
        for pattern, message in suspicious_patterns:
            if re.search(pattern, workflow_str):
                self.errors.append(f"SECURITY: {message} found in workflow")
        
        # Check for PII logging
        observability = workflow.get('observability', {})
        audit = observability.get('audit', {})
        
        if audit.get('log_inputs') and not workflow.get('security', {}).get('pii_fields'):
            self.warnings.append(
                "Audit logs inputs but no PII fields declared - consider privacy implications"
            )
    
    def _check_best_practices(self, workflow: Dict[str, Any]):
        """Check adherence to best practices"""
        # Check for documentation
        if 'documentation' not in workflow:
            self.warnings.append("No documentation section found")
        else:
            doc = workflow['documentation']
            if 'semantic_gaps' not in doc or not doc['semantic_gaps']:
                self.info.append("Consider documenting semantic gaps (UI term → API field)")
        
        # Check for observability
        if 'observability' not in workflow:
            self.warnings.append("No observability configuration found")
        
        # Check for validation
        if 'validation' not in workflow:
            self.warnings.append("No validation rules (pre/post conditions) defined")
        
        # Check for dry-run support
        exec_config = workflow.get('execution_config', {})
        if not exec_config.get('dry_run_supported'):
            self.info.append("Workflow does not support dry-run mode")
        
        # Check for rollback support
        if not exec_config.get('rollback_supported'):
            self.info.append("Workflow does not support rollback on failure")
    
    def print_results(self):
        """Print validation results"""
        print("\n" + "="*60)
        print("VALIDATION RESULTS")
        print("="*60 + "\n")
        
        if self.errors:
            print(f"[-] ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
            print()
        
        if self.warnings:
            print(f"[!] WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
            print()
        
        if self.info:
            print(f"[i] INFO ({len(self.info)}):")
            for info in self.info:
                print(f"   - {info}")
            print()
        
        if not self.errors and not self.warnings:
            print("[+] Workflow validation passed with no issues!\n")
        elif not self.errors:
            print("[+] Workflow validation passed (with warnings)\n")
        else:
            print("[-] Workflow validation failed\n")
        
        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Validate Universal Workflow Definition files'
    )
    parser.add_argument(
        'workflow_file',
        type=str,
        help='Path to workflow JSON file'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    
    args = parser.parse_args()
    
    # Load workflow file
    workflow_path = Path(args.workflow_file)
    
    if not workflow_path.exists():
        print(f"[-] Error: File not found: {workflow_path}")
        sys.exit(1)
    
    try:
        with open(workflow_path, 'r') as f:
            workflow = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[-] Error: Invalid JSON: {e}")
        sys.exit(1)
    
    # Validate
    validator = WorkflowValidator(strict_mode=args.strict)
    success = validator.validate(workflow)
    validator.print_results()
    
    # Exit code
    if not success:
        sys.exit(1)
    elif args.strict and validator.warnings:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
