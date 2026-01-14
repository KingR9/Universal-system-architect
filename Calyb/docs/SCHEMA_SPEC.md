# Universal Workflow Schema Specification

## Overview

The Universal Workflow Schema is a **platform-agnostic**, **declarative** specification for representing reverse-engineered SaaS workflows. It separates *what* needs to happen (intent) from *how* it happens (platform-specific execution).

## Design Principles

1. **Declarative**: Describe the workflow, not the execution algorithm
2. **Platform-Agnostic**: Works for Vendure, Salesforce, Shopify, etc.
3. **Credential-Agnostic**: No secrets in definitions
4. **Composable**: Steps can be reused across workflows
5. **Observable**: Built-in telemetry and audit logging
6. **Secure by Default**: RBAC, input validation

## Schema Structure

```
workflow_definition
├── metadata          # Identity, versioning, tags
├── inputs            # Required/optional parameters
├── security          # Auth, RBAC, PII, rate limits
├── validation        # Pre/post conditions
├── steps             # Ordered execution graph
├── execution_config  # Retry, timeout, rollback
├── observability     # Telemetry, audit logs
└── documentation     # Semantic gaps, references
```

## Section Reference

### 1. Metadata

**Purpose**: Identity and version management

```json
{
  "metadata": {
    "workflow_name": "create_black_friday_promotion",
    "workflow_id": "wf_bf2024_v1",
    "description": "Creates a Black Friday promotion with customer group targeting",
    "platform": "vendure",
    "platform_version": "2.0.0",
    "schema_version": "1.0.0",
    "author": "Platform Team",
    "created_at": "2024-11-01T00:00:00Z",
    "updated_at": "2024-11-15T10:30:00Z",
    "idempotent": true,
    "tags": ["promotions", "black-friday", "marketing"]
  }
}
```

**Required Fields**:
- `workflow_name`: Snake_case identifier (a-z, 0-9, _)
- `workflow_id`: Unique identifier (UUID recommended)
- `platform`: Target platform (vendure, salesforce, etc.)
- `schema_version`: Semantic version (MAJOR.MINOR.PATCH)

**Best Practices**:
- Use semantic versioning for workflow_id
- Set `idempotent: true` if safe to re-run
- Tag workflows for discoverability

### 2. Inputs

**Purpose**: Define required and optional parameters

```json
{
  "inputs": {
    "required": {
      "promotionName": {
        "type": "string",
        "description": "Display name for the promotion",
        "validation": {
          "pattern": "^[A-Za-z0-9 \\-_]{3,100}$",
          "min_length": 3,
          "max_length": 100
        },
        "example": "Black Friday 2024"
      },
      "discountPercentage": {
        "type": "number",
        "description": "Discount percentage (0-100)",
        "validation": {
          "minimum": 0,
          "maximum": 100
        },
        "example": 20
      }
    },
    "optional": {
      "startDate": {
        "type": "string",
        "description": "Promotion start date (ISO 8601)",
        "default": "now",
        "validation": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
        }
      }
    }
  }
}
```

**Supported Types**:
- `string`, `number`, `integer`, `boolean`, `array`, `object`

**Validation Rules**:
- `pattern`: Regex for string validation
- `min_length`, `max_length`: String length bounds
- `minimum`, `maximum`: Numeric bounds
- `enum`: Allowed values list

**Security**:
- Mark sensitive inputs: `"sensitive": true`
- Never include examples of real credentials

### 3. Security

**Purpose**: Authentication, authorization, and protection

```json
{
  "security": {
    "auth_required": true,
    "auth_type": "bearer_token",
    "secrets_handling": "runtime_injected",
    "minimum_role": "promotions_manager",
    "scopes": ["catalog:write", "promotions:write"],
    "rate_limit": {
      "requests_per_second": 10,
      "burst_limit": 50
    },
    "pii_fields": [
      "customerEmail",
      "customerPhone"
    ]
  }
}
```

**Required Fields**:
- `auth_required`: Boolean (true recommended)
- `secrets_handling`: How credentials are provided
  - `runtime_injected`: ✅ Best practice
  - `vault`: Use secrets management service
  - `env_var`: Environment variables (less secure)

**Optional Fields**:
- `minimum_role`: RBAC role requirement
- `scopes`: OAuth2-style permission scopes
- `rate_limit`: Prevent abuse
- `pii_fields`: Auto-redact in logs

### 4. Validation

**Purpose**: Pre- and post-execution checks

```json
{
  "validation": {
    "pre_conditions": [
      {
        "id": "check_auth",
        "type": "security",
        "description": "Verify user has promotions:write permission",
        "query": "query { me { permissions } }",
        "condition": "$.me.permissions includes 'promotions:write'",
        "error_message": "User lacks promotions:write permission",
        "critical": true
      }
    ],
    "post_conditions": [
      {
        "id": "verify_promotion_active",
        "type": "query",
        "description": "Verify promotion was created and is enabled",
        "query": "query { promotion(id: $promotionId) { enabled } }",
        "condition": "$.promotion.enabled == true",
        "error_message": "Promotion not enabled after creation"
      }
    ]
  }
}
```

**Condition Types**:
- `security`: Auth/authz checks
- `query`: Data existence/state validation
- `script`: Custom validation logic
- `data`: Input data validation

**Critical vs Non-Critical**:
- `critical: true`: Abort workflow if failed
- `critical: false`: Log warning but continue

### 5. Steps

**Purpose**: Ordered execution graph with dependencies

```json
{
  "steps": [
    {
      "id": "create_promotion",
      "description": "Create the promotion object",
      "operation": "mutation",
      "api_endpoint": "createPromotion",
      "inputs": {
        "input": {
          "name": "{{inputs.promotionName}}",
          "enabled": true,
          "couponCode": "{{inputs.couponCode}}",
          "startsAt": "{{inputs.startDate}}",
          "endsAt": "{{inputs.endDate}}"
        }
      },
      "outputs": {
        "promotionId": "$.createPromotion.id",
        "promotionCode": "$.createPromotion.couponCode"
      },
      "depends_on": [],
      "error_handling": {
        "strategy": "abort",
        "max_retries": 3
      },
      "telemetry": {
        "track_duration": true,
        "log_level": "info"
      }
    },
    {
      "id": "add_discount_action",
      "description": "Add percentage discount action",
      "operation": "mutation",
      "api_endpoint": "updatePromotion",
      "inputs": {
        "input": {
          "id": "{{steps.create_promotion.outputs.promotionId}}",
          "actions": [
            {
              "code": "order_percentage_discount",
              "arguments": [
                {
                  "name": "discount",
                  "value": "{{inputs.discountPercentageInCents}}"
                }
              ]
            }
          ]
        }
      },
      "depends_on": ["create_promotion"],
      "error_handling": {
        "strategy": "retry",
        "max_retries": 3
      }
    }
  ]
}
```

**Step Fields**:
- `id`: Unique snake_case identifier
- `operation`: `query`, `mutation`, `workflow`, `custom`
- `api_endpoint`: GraphQL operation or REST URL
- `inputs`: Parameters with template support
- `outputs`: JSONPath extraction for downstream steps
- `depends_on`: Array of step IDs (defines DAG)
- `error_handling`: Abort, retry, skip, or fallback
- `telemetry`: Observability configuration

**Template Variables**:
- `{{inputs.paramName}}`: Workflow input
- `{{steps.stepId.outputs.field}}`: Output from previous step
- `{{env.VAR_NAME}}`: Environment variable (use sparingly)

**Error Handling Strategies**:
- `abort`: Stop workflow (default for critical steps)
- `retry`: Exponential backoff retry
- `skip`: Continue to next step (for non-critical steps)
- `fallback`: Execute alternate step

### 6. Execution Config

**Purpose**: Retry, timeout, and rollback policies

```json
{
  "execution_config": {
    "parallel": false,
    "timeout_seconds": 300,
    "retry_policy": {
      "max_attempts": 3,
      "backoff_strategy": "exponential",
      "initial_delay_ms": 1000,
      "max_delay_ms": 30000,
      "retryable_errors": [
        "RATE_LIMIT_EXCEEDED",
        "TEMPORARY_FAILURE"
      ]
    },
    "dry_run_supported": true,
    "rollback_supported": true
  }
}
```

**Parallel Execution**:
- `parallel: true`: Steps without dependencies run concurrently
- `parallel: false`: Strict sequential execution

**Retry Policy**:
- `fixed`: Same delay between retries
- `linear`: Linearly increasing delay
- `exponential`: Exponentially increasing delay (recommended)

**Dry-Run Support**:
- `dry_run_supported: true`: Workflow can simulate without mutations
- Useful for validation and testing

### 7. Observability

**Purpose**: Telemetry and audit logging

```json
{
  "observability": {
    "telemetry": {
      "enabled": true,
      "trace_id_required": true,
      "span_per_step": true,
      "metrics": ["duration_ms", "error_count", "retry_count"]
    },
    "audit": {
      "enabled": true,
      "log_inputs": true,
      "log_outputs": true,
      "retention_days": 90,
      "redact_pii": true
    }
  }
}
```

**Telemetry**:
- Distributed tracing with trace_id
- Per-step spans for granular monitoring
- Standard metrics for dashboards

**Audit Logging**:
- Compliance-grade audit trail
- PII redaction based on security.pii_fields
- Configurable retention period

### 8. Documentation

**Purpose**: Semantic mappings and references

```json
{
  "documentation": {
    "semantic_gaps": [
      {
        "ui_term": "Discount Percentage",
        "api_field": "discount (in cents)",
        "mapping_logic": "20% discount → 2000 cents (multiply by 100)"
      },
      {
        "ui_term": "Customer Group Name",
        "api_field": "customerGroupId (UUID)",
        "mapping_logic": "Resolve name → ID via CustomerGroups query"
      }
    ],
    "related_workflows": [
      "disable_promotion",
      "update_promotion_dates"
    ],
    "references": [
      {
        "title": "Vendure Promotion API",
        "url": "https://docs.vendure.io/reference/graphql-api/admin/mutations/#createpromotion"
      }
    ]
  }
}
```

**Semantic Gaps**:
- Bridge UI terminology to API fields
- Document non-obvious transformations
- Critical for maintainability

## Validation Rules

### Structural Validation
1. All required top-level keys present
2. Step IDs are unique and snake_case
3. No circular dependencies in `depends_on`
4. Template variables reference valid inputs/outputs
5. Semantic versioning for schema_version

### Semantic Validation
1. Outputs declared are used by downstream steps
2. All template variables can be resolved
3. Pre-conditions can be evaluated before execution
4. Post-conditions can be evaluated after execution

### Security Validation
1. No hardcoded credentials (grep for "password", "token", "key")
2. `secrets_handling` is `runtime_injected` (recommended)
3. All inputs have validation rules
4. PII fields are declared if `log_inputs: true`
5. `minimum_role` specified for sensitive operations

## Best Practices

### DO 
- Use `runtime_injected` for credentials
- Validate all inputs with regex/bounds
- Declare PII fields for auto-redaction
- Enable audit logging for production workflows
- Use semantic step IDs (create_promotion, not step1)
- Document semantic gaps in UI → API mappings
- Test with dry-run before production
- Version workflows with semantic versioning

### DON'T 
- Hardcode credentials in workflow definitions
- Skip input validation ("trust but verify")
- Log PII without declaring `pii_fields`
- Use generic step IDs (step1, step2, etc.)
- Create circular dependencies
- Deploy without pre/post-condition validation
- Ignore rate limits in high-volume workflows


## Appendix: Full Example

See [workflow_map.json](../workflow_map.json) for an example of the Universal Workflow Schema.
