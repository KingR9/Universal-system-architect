# Security Architecture

## Overview

The Universal Workflow Intelligence Engine implements defense-in-depth security with credential-agnostic design, RBAC, audit logging, and PII protection.

## Security Principles

### 1. Credential-Agnostic Design

**Problem**: Hardcoded credentials in workflow definitions create security vulnerabilities and maintenance overhead.

**Solution**: Runtime credential injection with `secrets_handling: runtime_injected`

```json
{
  "security": {
    "auth_required": true,
    "secrets_handling": "runtime_injected",
    "auth_type": "bearer_token"
  }
}
```

**Benefits**:
- No secrets in version control
- Centralized credential rotation
- Per-environment credential management
- Audit trail of credential usage

### 2. Role-Based Access Control (RBAC)

Workflows declare minimum required roles:

```json
{
  "security": {
    "minimum_role": "promotions_manager",
    "scopes": ["catalog:write", "promotions:write"]
  }
}
```

**Enforcement Points**:
1. Pre-execution: Validate user has required role
2. Runtime: Scope each API call to authorized resources
3. Post-execution: Audit permission usage

### 3. Audit Logging

Comprehensive audit trail for compliance:

```json
{
  "observability": {
    "audit": {
      "enabled": true,
      "log_inputs": true,
      "log_outputs": true,
      "retention_days": 90
    }
  }
}
```

**Logged Events**:
- Workflow invocation (who, when, what)
- Input parameters (with PII redaction)
- Step execution results
- Authorization decisions
- Errors and exceptions

### 4. PII Protection

Declare PII fields for automatic redaction:

```json
{
  "security": {
    "pii_fields": [
      "customerEmail",
      "customerPhone",
      "shippingAddress"
    ]
  }
}
```

**Protection Mechanisms**:
- Automatic redaction in logs: `customerEmail: [REDACTED]`
- Encrypted storage for audit logs
- GDPR-compliant deletion workflows

### 5. Rate Limiting

Prevent abuse and ensure fair resource usage:

```json
{
  "security": {
    "rate_limit": {
      "requests_per_second": 10,
      "burst_limit": 50
    }
  }
}
```

**Enforcement**:
- Token bucket algorithm
- Per-user and per-workflow limits
- Graceful degradation under load

## Threat Model

### Threats Mitigated

| Threat | Mitigation |
|--------|-----------|
| Credential theft | Runtime injection, no storage |
| Unauthorized access | RBAC + pre-conditions |
| Data exfiltration | Audit logs + output validation |
| Injection attacks | Input validation + parameterized queries |
| CSRF | State tokens + idempotency keys |
| Rate abuse | Token bucket rate limiting |

### Threats NOT Mitigated

- **Network-level attacks**: Requires infrastructure-level defenses (WAF, DDoS protection)
- **Platform vulnerabilities**: Vendure/Salesforce/etc. security is their responsibility
- **Social engineering**: Human factors outside technical scope

## Secure Development Practices

### Input Validation

All inputs MUST have validation rules:

```json
{
  "inputs": {
    "required": {
      "promotionName": {
        "type": "string",
        "validation": {
          "pattern": "^[A-Za-z0-9 \\-_]{3,100}$",
          "min_length": 3,
          "max_length": 100
        }
      }
    }
  }
}
```

### Output Sanitization

Outputs are validated against expected schemas:

```json
{
  "validation": {
    "post_conditions": [
      {
        "id": "verify_promotion_created",
        "type": "query",
        "description": "Verify promotion was created and is active"
      }
    ]
  }
}
```

### Secure Defaults

- Authentication: **REQUIRED** by default
- Audit logging: **ENABLED** by default
- TLS: **REQUIRED** for all API calls
- Credential injection: **RUNTIME** only

## Compliance

### SOC 2 Type II

- Audit logs retained for 90 days
- Role-based access controls
- Change management via version control
- Incident response procedures

### GDPR

- PII field declarations
- Audit log encryption
- Right to erasure support
- Data minimization principles

### HIPAA (if applicable)

- PHI field declarations
- Encrypted audit logs
- Access logs for all PHI access
- Business Associate Agreements required

## Security Checklist

Before deploying a workflow to production:

- [ ] No hardcoded credentials (`grep -i "password\|token\|key"`)
- [ ] `secrets_handling: runtime_injected` configured
- [ ] `minimum_role` declared
- [ ] All inputs have validation rules
- [ ] PII fields declared
- [ ] Audit logging enabled
- [ ] Rate limits configured
- [ ] Pre-conditions verify authorization
- [ ] Post-conditions validate state
- [ ] Error messages don't leak sensitive data
- [ ] Dry-run tested in staging
- [ ] Security review approved

## Incident Response

If a security incident is detected:

1. **Isolate**: Disable affected workflow immediately
2. **Investigate**: Review audit logs for scope of compromise
3. **Remediate**: Rotate credentials, patch vulnerabilities
4. **Notify**: Inform affected users per compliance requirements
5. **Learn**: Update threat model and controls

## Contact

For security issues, contact: security@example.com

**Do NOT** file public issues for security vulnerabilities.
