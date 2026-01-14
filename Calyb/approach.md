# Universal Workflow Intelligence Engine

## Executive Summary

This document outlines a **platform-agnostic methodology** for reverse-engineering SaaS workflows and transforming them into machine-executable workflow definitions. The approach is designed to work universally across any SaaS platform (Salesforce, Jira, HubSpot, Vendure, etc.) without requiring platform-specific adaptations.

**Core Principle**: Software workflows are deterministic state machines. Our job is to discover the state transition graph and map human semantics to system primitives.


## Design Principles

Our workflow intelligence engine is built on the following production-grade design principles:

### 1. **Declarative Over Imperative**
- Workflows describe **what** should happen, not **how** to execute it
- Steps are data structures, not code
- Execution engine interprets the workflow DAG

### 2. **Credential-Agnostic Design**
- Zero secrets in workflow definitions
- Authentication tokens injected at runtime
- Enables safe storage, version control, and sharing
- Supports credential rotation without workflow changes

### 3. **Deterministic Execution**
- Same inputs always produce same outputs
- No hidden state dependencies
- Reproducible for debugging and auditing

### 4. **Idempotency-Aware**
- Workflows can be safely re-executed
- Duplicate detection strategies (fetch-existing, skip, error)
- State reconciliation before mutation

### 5. **Auditability & Observability Built-In**
- Full execution traces with correlation IDs
- Input/output logging at each step
- Structured telemetry for monitoring
- Compliance-ready audit trails

### 6. **Fail-Safe Defaults**
- Explicit error handling policies
- Rollback mechanisms for transactional workflows
- Graceful degradation strategies
- Pre/post condition validation

### 7. **Zero UI Coupling**
- No CSS selectors, DOM paths, or click coordinates
- Pure API-level abstractions
- UI can change without breaking workflows
- Headless execution by design


## System Architecture

The workflow intelligence engine operates as a multi-layer system:

```
┌─────────────────────────────────────────────────────┐
│           User Intent (Natural Language)            │
│     "Create a promotion for VIP customers..."       │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│         Semantic Normalization Layer                │
│  Maps human concepts → API primitives               │
│  ("VIP Group" → customerGroupId: "xyz123")          │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│          Workflow DAG Engine                        │
│  • Dependency resolution                            │
│  • Execution sequencing                             │
│  • Data flow management                             │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│         Secure API Executor                         │
│  • Runtime credential injection                     │
│  • Request signing & authentication                 │
│  • Rate limiting & retry logic                      │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│         Observability & Audit Layer                 │
│  • Trace correlation                                │
│  • Metric emission                                  │
│  • Structured logging                               │
└─────────────────────────────────────────────────────┘
```


## The Universal Reverse-Engineering Algorithm

This algorithm is **platform-agnostic** and has been validated on multiple SaaS platforms.

### Phase 1: Intent Decomposition

**Goal**: Break user request into atomic business operations.

```
Input: "Create a Black Friday coupon 'BF2024'. 15% discount for orders 
        above $100 for VIP customers."

Decomposition:
1. CREATE entity: Promotion
2. CONFIGURE attribute: Coupon Code = "BF2024"
3. CONFIGURE attribute: Discount = 15%
4. ADD CONDITION: Minimum Order Value = $100
5. ADD CONDITION: Customer Group = "VIP"
```

**Technique**: Parse natural language into CRUD operations + configuration constraints.


### Phase 2: UI → API Correlation

**Goal**: Map each UI action to its underlying API call.

#### Step 2.1: UI Action Triggering
- Manually perform the workflow in the application
- Use browser DevTools Network tab to capture all API traffic
- Filter by XHR/Fetch requests (REST) or WebSocket frames (GraphQL)

#### Step 2.2: Request Analysis
For each captured request:
```
Captured: POST /admin-api (GraphQL)
Body: { "query": "mutation { createPromotion(...) { id } }" }

Extract:
- API Type: GraphQL Mutation
- Operation Name: createPromotion
- Required Fields: {enabled, couponCode, translations}
- Response Schema: {id, name, createdAt}
```

#### Step 2.3: Sequencing Discovery
- Observe **order** of API calls
- Identify which requests cannot proceed without prior responses
- Example: `addPromotionCondition` requires `promotionId` from `createPromotion`

**Platform Independence**: This works identically for REST APIs, GraphQL, or even SOAP.


### Phase 3: Schema Validation

**Goal**: Verify discovered API patterns against official documentation.

#### Lookup Strategy:
1. **Official API Docs**: Search for operation names (e.g., `createPromotion`)
2. **GraphQL Introspection**: Query `__schema` to get type definitions
3. **OpenAPI/Swagger Specs**: For REST APIs, validate against schema definitions
4. **SDKs**: Inspect client library source code for canonical parameter names

#### Validation Checklist:
- All captured fields are documented
- Required vs. optional parameters match schema
- Data types align (string vs. integer, date formats)
- Enum values are valid
- Reject undocumented "magic" fields (likely to break)


### Phase 4: Semantic Gap Resolution

**Goal**: Map UI terminology to API field names and handle type conversions.

#### The Challenge:
UI displays user-friendly terms that don't match API internals.

| UI Term | API Field | Transformation |
|---------|-----------|----------------|
| "Order Total Above $100" | `minimum_order_amount` | Multiply by 100 (USD → cents) |
| "VIP Customer Group" | `customerGroupId: "abc123"` | Name → ID lookup via query |
| "15% Discount" | `order_percentage_discount` | Integer (15, not 0.15) |
| "Unlimited Stock" | `trackInventory: false` | Boolean flag inversion |

#### Discovery Techniques:

**A. Network Traffic Analysis**
- UI shows "$100" → API sends `10000` → Infer multiplication factor

**B. HTML Inspection**
- Check `<select>` options: `<option value="abc123">VIP Group</option>`
- Reveals ID ↔ Name mapping

**C. Response Schema Analysis**
- API returns `{id: "xyz", name: "VIP"}` → Understand entity structure

**D. Documentation Cross-Reference**
- Search docs for "stock" → Find `StockLocationStrategy` enum
- Map "Unlimited" → `UNLIMITED` or `trackInventory: false`

**E. Pattern Recognition**
- Currency fields universally stored in smallest unit (cents, paise, yen)
- Dates commonly in ISO 8601 format
- IDs are UUIDs or integers, never human-readable names


### Phase 5: Dependency Graph Construction

**Goal**: Build a directed acyclic graph (DAG) of step dependencies.

#### Algorithm:
```python
def build_dependency_graph(api_calls):
    graph = {}
    
    for call in api_calls:
        # Extract input parameters
        inputs = extract_parameters(call.request)
        
        # Identify which inputs reference outputs of prior steps
        dependencies = []
        for param_value in inputs.values():
            if is_reference(param_value):  # e.g., "{{steps.create.id}}"
                source_step = extract_source_step(param_value)
                dependencies.append(source_step)
        
        graph[call.name] = {
            'depends_on': dependencies,
            'produces': extract_outputs(call.response)
        }
    
    return topological_sort(graph)
```

#### Example:
```
Step 1: createPromotion() → outputs: {promotionId}
Step 2: addCondition(promotionId) → depends on Step 1
Step 3: addAction(promotionId) → depends on Step 1
```

DAG allows:
- Parallel execution of independent steps (Step 2 & 3)
- Proper sequencing of dependent steps
- Data flow tracking


### Phase 6: Abstraction Layer

**Goal**: Remove concrete values and replace with parameterized inputs.

#### Before (Hardcoded):
```json
{
  "couponCode": "BF2024",
  "discount": 15,
  "minOrderTotal": 10000
}
```

#### After (Parameterized):
```json
{
  "couponCode": "{{inputs.coupon_code}}",
  "discount": "{{inputs.discount_percentage}}",
  "minOrderTotal": "{{inputs.min_order_total_usd * 100}}"
}
```

**Benefits**:
- Workflow becomes reusable for different promotions
- Inputs can be validated before execution
- Type safety and boundary checks


### Phase 7: Production Hardening

**Goal**: Add operational resilience features.

#### Security Layer:
```json
{
  "security": {
    "auth_required": true,
    "minimum_role": "admin",
    "secrets_handling": "runtime_injected",
    "rate_limit": {"max_requests": 10, "window_seconds": 60}
  }
}
```

#### Error Handling:
```json
{
  "error_handling": {
    "on_duplicate": "fetch_existing",
    "on_validation_error": "fail",
    "retry_policy": {
      "max_attempts": 3,
      "backoff_ms": 1000
    },
    "rollback_steps": ["create_promotion"]
  }
}
```

#### Validation:
```json
{
  "validation": {
    "pre_conditions": [
      {
        "id": "check_customer_group_exists",
        "query": "query { customerGroups { items { name } } }",
        "condition": "$.items[?(@.name == 'VIP')]",
        "error_message": "Customer group 'VIP' does not exist"
      }
    ]
  }
}
```


## Generalization: Applying to Other Platforms

**The methodology described above is platform-agnostic.** Here's how to apply it to other SaaS platforms:

### Salesforce
1. **Decomposition**: Same approach (CRUD operations)
2. **UI → API Correlation**: Use browser DevTools to capture REST API or SOAP calls
3. **Schema Validation**: Consult Salesforce Object Reference for field definitions
4. **Semantic Gaps**: "Account Name" → `Account.Name` (API object notation)
5. **Dependencies**: "Create Contact" requires `AccountId` from "Create Account"

### Jira
1. **Decomposition**: Break "Create Epic with Stories" into atomic operations
2. **UI → API Correlation**: Capture REST API calls (`POST /rest/api/3/issue`)
3. **Schema Validation**: Reference Jira REST API documentation
4. **Semantic Gaps**: "Issue Type" → `issuetype.id` (name to ID lookup)
5. **Dependencies**: "Link Issues" requires `issueId` from "Create Issue"

### HubSpot
1. **Decomposition**: Parse "Create Deal with Contact" into steps
2. **UI → API Correlation**: Capture REST API calls to HubSpot endpoints
3. **Schema Validation**: Use HubSpot API Explorer for schemas
4. **Semantic Gaps**: "Deal Stage" → `dealstage` property with pipeline-specific IDs
5. **Dependencies**: "Associate Contact" requires both `contactId` and `dealId`


## Security Design

### Threat Model

**Threats We Mitigate**:
1. **Credential Leakage**: Secrets stored in version control
2. **Privilege Escalation**: Workflows executing with excessive permissions
3. **Injection Attacks**: Malicious input parameters
4. **Replay Attacks**: Stolen workflow definitions executed maliciously
5. **Audit Evasion**: Actions performed without traceability

### Security Architecture

#### 1. Credential-Agnostic Workflows
**Problem**: Hardcoded API tokens in workflow files.

**Solution**:
```json
{
  "security": {
    "auth_required": true,
    "secrets_handling": "runtime_injected"
  }
}
```

- Workflows contain **zero** authentication credentials
- Execution engine injects tokens from secure vault (e.g., AWS Secrets Manager, HashiCorp Vault)
- Enables safe storage in git, sharing across teams, and credential rotation

#### 2. Role-Based Access Control (RBAC)
```json
{
  "security": {
    "minimum_role": "admin",
    "permissions": [
      "CreatePromotion",
      "UpdatePromotion",
      "ReadCustomerGroup"
    ]
  }
}
```

- Workflows declare minimum required permissions
- Execution engine validates user's role before execution
- Principle of least privilege

#### 3. Input Validation & Sanitization
```json
{
  "inputs": {
    "coupon_code": {
      "validation": {
        "pattern": "^[A-Z0-9]{4,20}$",
        "max_length": 20
      }
    }
  }
}
```

- Prevents injection attacks (SQL, GraphQL, command injection)
- Type safety enforcement
- Boundary checks (min/max values)

#### 4. Pre-Execution Validation
```json
{
  "validation": {
    "pre_conditions": [
      {
        "id": "check_auth",
        "type": "security",
        "description": "Verify user has admin role",
        "critical": true
      }
    ]
  }
}
```

- Verify user authentication status
- Check resource existence before mutation
- Prevent destructive operations on invalid state

#### 5. Audit Logging
```json
{
  "observability": {
    "audit": {
      "log_all_mutations": true,
      "log_inputs": true,
      "log_outputs": true,
      "log_user_context": true,
      "retention_days": 90
    }
  }
}
```

- Full audit trail of who executed what, when
- Immutable logs for compliance (SOC2, GDPR, HIPAA)
- Correlation IDs for incident investigation
- **PII Handling**: Workflows declare PII fields; execution engine redacts from logs

#### 6. Rate Limiting
```json
{
  "security": {
    "rate_limit": {
      "max_requests": 10,
      "window_seconds": 60
    }
  }
}
```

- Prevents abuse and accidental DoS
- Per-workflow and per-user rate limits
- Sliding window algorithm

#### 7. Dry-Run Mode
**Critical Feature**: Validate workflows without side effects.

```json
{
  "execution_config": {
    "dry_run_supported": true
  }
}
```

**Implementation**:
- Execute queries (read operations)
- Skip mutations (write operations)
- Validate permissions, data existence, and dependencies
- Return execution plan without modifying state

**Benefits**:
- Test workflows in production environment safely
- Validate credentials and permissions
- Catch errors before impacting production data


## Advanced Features

### 1. Rollback Mechanism
For workflows with multiple mutation steps, failures mid-execution leave inconsistent state.

**Solution**:
```json
{
  "error_handling": {
    "on_failure": "rollback",
    "rollback_steps": ["create_promotion", "add_condition"]
  }
}
```

**Implementation**:
- Each mutation step declares inverse operation (e.g., `deletePromotion`)
- On failure, execute inverse operations in reverse order
- Best-effort rollback (not fully transactional, but pragmatic)

### 2. Parallel Execution
Independent steps can execute concurrently for performance.

```json
{
  "execution_config": {
    "parallel_safe_groups": [
      ["add_minimum_order_condition", "add_customer_group_condition"]
    ]
  }
}
```

- Reduces total execution time
- Requires careful dependency analysis
- Engine enforces happens-before relationships

### 3. Dynamic Workflow Composition
Workflows can invoke other workflows as sub-steps.

```json
{
  "steps": [
    {
      "id": "create_customer_group",
      "operation": "workflow",
      "workflow_ref": "create_customer_group_v1",
      "inputs": {
        "group_name": "{{inputs.eligible_customer_group}}"
      }
    }
  ]
}
```

- Enables workflow reuse and modularity
- Simplifies complex multi-entity operations

### 4. Conditional Execution
Steps can execute conditionally based on runtime state.

```json
{
  "steps": [
    {
      "id": "send_notification",
      "condition": "{{steps.create_promotion.outputs.promotion_id}} != null",
      "operation": "mutation",
      "api_endpoint": "sendEmail"
    }
  ]
}
```


## Observability & Monitoring

### Telemetry Design

**Structured Logging**:
```json
{
  "timestamp": "2026-01-14T10:30:00Z",
  "trace_id": "abc-123-def",
  "span_id": "step-2",
  "workflow_id": "vendure_promotion_bf2024",
  "step_id": "create_promotion",
  "event": "step_completed",
  "duration_ms": 342,
  "user_id": "user@example.com",
  "status": "success"
}
```

**Metrics**:
- `workflow_execution_duration_ms{workflow_id, status}`
- `workflow_step_duration_ms{workflow_id, step_id, status}`
- `workflow_execution_count{workflow_id, status}`
- `workflow_error_rate{workflow_id, error_type}`

**Distributed Tracing**:
- Each workflow execution generates a unique `trace_id`
- Each step is a span with parent → child relationships
- Enables end-to-end latency analysis

**Alerting**:
```json
{
  "monitoring": {
    "success_rate_alert_threshold": 0.95,
    "latency_p99_threshold_ms": 5000,
    "error_rate_alert_threshold": 0.05
  }
}
```


## Workflow Schema Design

### Core Schema Principles

1. **Machine-Readable**: Engine can parse and execute without human interpretation
2. **Self-Documenting**: Includes descriptions, examples, and semantic mappings
3. **Versioned**: Schema version allows backward-compatible evolution
4. **Extensible**: Custom fields via namespaces (e.g., `x-vendor-specific`)

### Schema Structure

```
workflow_definition:
  ├── metadata (identity, versioning, ownership)
  ├── inputs (required/optional parameters with validation)
  ├── security (auth, permissions, rate limits)
  ├── validation (pre/post conditions)
  ├── steps (DAG of operations)
  │   ├── id (unique identifier)
  │   ├── sequence (execution order hint)
  │   ├── operation (query, mutation, workflow)
  │   ├── depends_on (dependency list)
  │   ├── inputs (parameterized request body)
  │   ├── outputs (response field extraction)
  │   ├── error_handling (retry, rollback, fail policies)
  │   └── telemetry (logging, metrics)
  ├── execution_config (parallelism, timeouts, dry-run)
  └── observability (tracing, monitoring, audit)
```


## Implementation Considerations

### For a Production Engine

1. **Execution Runtime**: Build interpreter in Go/Rust for performance
2. **Template Engine**: Use Jinja2 or similar for `{{variable}}` interpolation
3. **State Management**: Maintain execution state in Redis for resumability
4. **Queue-Based Execution**: Use Kafka/RabbitMQ for asynchronous workflows
5. **Multi-Tenancy**: Isolate workflows per customer with namespace prefixes
6. **Versioning**: Support multiple schema versions with migration paths


## Conclusion

This methodology is **universally applicable** to any SaaS platform because it operates on fundamental principles:

1. **UI actions map to API calls** (true for all web applications)
2. **APIs have schemas** (GraphQL introspection, OpenAPI specs, documentation)
3. **Semantic gaps exist** (UI terminology ≠ API field names)
4. **Dependencies form DAGs** (state machines have deterministic transitions)

**The algorithm does not change. Only the platform-specific details differ.**

By following this methodology, we can reverse-engineer workflows for any modern SaaS platform with a documented API

