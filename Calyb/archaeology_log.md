# Vendure Archaeology Log


This document records specific implementation details, gotchas, and semantic gaps discovered during the reverse-engineering of Vendure's promotion workflow.


## 1. Currency Representation

### Discovery
While creating promotions with minimum order conditions, observed that UI displays `$100.00` but the API expects `10000`.

### Root Cause
Vendure stores all monetary values as **integers representing the smallest currency unit** (cents for USD).

### Evidence
- Network capture of `minimum_order_amount` condition:
  ```graphql
  arguments: [
    { name: "amount", value: "10000" }
  ]
  ```
- API documentation confirms: "All monetary values are in cents"

### Semantic Mapping
| UI Display | API Value | Transformation |
|------------|-----------|----------------|
| $100.00 | 10000 | multiply by 100 |
| $19.99 | 1999 | multiply by 100 |
| $0.50 | 50 | multiply by 100 |

### Impact
**Critical**: Failure to convert results in promotions with incorrect thresholds (e.g., $1.00 instead of $100.00).

### Workflow Implementation
```json
{
  "transformations": {
    "amount": "usd_to_cents"
  },
  "inputs": {
    "amount": "{{inputs.min_order_total_usd * 100 | string}}"
  }
}
```


## 2. Promotion Structure: Conditions vs. Actions

### Discovery
Promotions in Vendure follow a **rule engine pattern**: Conditions (when to apply) + Actions (what to apply).

### Observation
- Initial `createPromotion` mutation creates an "empty" promotion
- Conditions and actions are added via **subsequent `updatePromotion` mutations**
- Cannot create a fully configured promotion in a single API call

### Evidence
```graphql
# Step 1: Create base promotion
mutation {
  createPromotion(input: {
    couponCode: "BF2024"
    enabled: true
  }) { id }
}

# Step 2: Add conditions (separate mutation)
mutation {
  updatePromotion(input: {
    id: "1"
    conditions: [...]
  })
}

# Step 3: Add actions (separate mutation)
mutation {
  updatePromotion(input: {
    id: "1"
    actions: [...]
  })
}
```

### Semantic Gap
UI presents this as a single form submission, but API requires 3+ separate mutations.

### Impact
**Dependency Management**: Steps 2 and 3 require `promotionId` output from Step 1. Execution must be sequential or use dependency tracking.


## 3. Customer Group Resolution

### Discovery
UI displays customer groups by name ("VIP", "Wholesale", etc.), but API requires **numeric or UUID-based IDs**.

### Root Cause
`customer_group` condition argument expects `customerGroupId`, not name.

### Evidence
```graphql
# UI shows dropdown with "VIP"
# But API requires:
arguments: [
  { name: "customerGroupId", value: "\"2\"" }
]
```

### Resolution Strategy
Must perform a **lookup query** before creating the condition:

```graphql
query {
  customerGroups {
    items {
      id
      name
    }
  }
}
```

Then filter results: `items[?(@.name == "VIP")].id`

### Impact
Adds a preliminary query step to the workflow. Failure to resolve the group name results in API validation errors.


## 4. Argument Value Serialization

### Discovery
Promotion condition/action arguments have inconsistent type serialization.

### Observations

| Argument Type | Expected Format | Example |
|---------------|-----------------|---------|
| Integer (amount) | String-wrapped integer | `"10000"` |
| String (ID) | String-wrapped quoted string | `"\"2\""` (double quotes escaped) |
| Boolean | String-wrapped boolean | `"true"` |
| Enum | String-wrapped quoted enum | `"\"auto\""` |

### Evidence
```graphql
# Minimum order condition
arguments: [
  { name: "amount", value: "10000" },           # Integer as string
  { name: "taxInclusion", value: "\"auto\"" }   # Enum as quoted string
]

# Customer group condition
arguments: [
  { name: "customerGroupId", value: "\"2\"" }   # ID as quoted string
]
```

### Root Cause
GraphQL schema defines `ConfigArgInput.value` as `String` type, requiring manual serialization of all argument values.

### Impact
**High Risk**: Incorrect quoting results in API rejection or silent failures (wrong type coercion).

### Workflow Implementation
Use explicit quoting in workflow definitions:
```json
{
  "arguments": [
    { "name": "customerGroupId", "value": "\"{{resolved_id}}\"" }
  ]
}
```


## 5. Condition Code Naming Conventions

### Discovery
Condition types have non-intuitive internal codes.

### Semantic Mapping

| UI Label | API Condition Code | Notes |
|----------|-------------------|-------|
| "Minimum Order Total" | `minimum_order_amount` | Not `minimum_order_total` |
| "Customer Group" | `customer_group` | Straightforward |
| "Product in Cart" | `contains_products` | Not `has_product` |

### Evidence
From GraphQL introspection and network captures.

### Impact
Cannot guess condition codes; must refer to documentation or introspection schema.


## 6. Action Code Naming Conventions

### Discovery
Similar to conditions, action types have specific internal codes.

### Semantic Mapping

| UI Label | API Action Code | Notes |
|----------|-----------------|-------|
| "Percentage Discount" | `order_percentage_discount` | Applies to entire order |
| "Fixed Discount" | `order_fixed_discount` | Not `fixed_discount` |
| "Product Percentage Discount" | `product_percentage_discount` | Item-level |

### Evidence
```graphql
actions: [
  {
    code: "order_percentage_discount",
    arguments: [
      { name: "discount", value: "15" }
    ]
  }
]
```

### Impact
Using wrong action code (e.g., `percentage_discount`) results in API validation error.


## 7. Promotion Translations Requirement

### Discovery
`createPromotion` mutation requires a `translations` array, even for single-language setups.

### Evidence
```graphql
createPromotion(input: {
  translations: [
    {
      languageCode: "en",
      name: "Black Friday Sale",
      description: "..."
    }
  ]
})
```

### Gotcha
Omitting `translations` results in API error: "translations is required".

### UI Behavior
UI has separate "Name" and "Description" fields at the top level, but they are actually part of the translations structure.

### Impact
Workflow must construct translations array explicitly, even for simple use cases.


## 8. Promotion State: Enabled vs. Scheduled

### Discovery
Promotions have three temporal states:

1. **Enabled + No Dates**: Active immediately, no expiry
2. **Enabled + Start Date**: Active at future date
3. **Disabled**: Inactive regardless of dates

### Evidence
```graphql
createPromotion(input: {
  enabled: true,
  startsAt: "2026-11-20T00:00:00Z",  # Optional
  endsAt: "2026-11-30T23:59:59Z"      # Optional
})
```

### Semantic Gap
UI checkbox "Enabled" + date pickers appear as separate controls, but API models them as a single state machine.

### Impact
Workflow must handle optional date fields and their interaction with `enabled` flag.


## 9. Default Values and Implicit Behavior

### Discovery
Several fields have implicit defaults that differ from typical "null" behavior.

| Field | Default Behavior | Notes |
|-------|-----------------|-------|
| `perCustomerUsageLimit` | `null` = unlimited uses | Not 0 or 1 |
| `usageLimit` | `null` = unlimited total uses | Not 0 |
| `enabled` | `true` | Promotions active by default |

### Evidence
Tested by omitting fields and observing created promotions.

### Impact
Workflow should explicitly set these fields to avoid confusion, even when accepting defaults.


## 10. GraphQL Error Handling

### Discovery
Vendure's GraphQL errors follow a specific structure that provides actionable information.

### Error Response Format
```json
{
  "errors": [
    {
      "message": "Promotion with code 'BF2024' already exists",
      "extensions": {
        "code": "DUPLICATE_ENTITY_ERROR"
      }
    }
  ]
}
```

### Error Codes Observed

| Code | Meaning | Handling Strategy |
|------|---------|-------------------|
| `DUPLICATE_ENTITY_ERROR` | Entity already exists | Fetch existing, or skip step |
| `FORBIDDEN` | Insufficient permissions | Fail with auth error |
| `INVALID_CREDENTIALS` | Bad auth token | Refresh token, retry |

### Impact
Workflow error handling can switch on `extensions.code` for intelligent retry/rollback policies.


## 11. ID Type Consistency

### Discovery
Entity IDs in Vendure are **string-based integers**, not UUIDs.

### Evidence
```json
{
  "id": "1",
  "id": "42",
  "id": "1337"
}
```

### Impact
- Safe to perform integer comparisons after parsing
- ID references must be strings in API calls: `"{{promotionId}}"`, not `{{promotionId}}`


## 12. Condition Evaluation Logic

### Discovery
Multiple conditions on a promotion use **AND logic** (all must be true).

### Evidence
From Vendure documentation and testing:
> "A promotion is eligible if ALL conditions return true."

### UI Representation
UI does not show explicit "AND"/"OR" operators, but the behavior is implicitly AND.

### Impact
To create OR logic, must create multiple separate promotions.


## 13. Action Application Order

### Discovery
Multiple actions on a promotion are applied **sequentially** in the order they were added.

### Example
```
Action 1: 10% off entire order
Action 2: $5 flat discount

Final price:
  Original: $100
  After Action 1: $90
  After Action 2: $85
```

### Impact
Order of action addition matters for complex multi-action promotions.


## 14. Audit Trail and History

### Discovery
Vendure maintains an internal audit log for promotions, but it's not exposed via public API.

### Evidence
Admin UI shows "History" tab with timestamped changes, but no corresponding GraphQL query.

### Impact
Workflow execution must implement its own audit logging; cannot rely on platform's built-in history.


## 15. Performance Observations

### Discovery
Promotion mutations have predictable latency:

| Operation | Avg Latency | Notes |
|-----------|-------------|-------|
| `createPromotion` | 150-250ms | Database write |
| `updatePromotion` (add condition) | 100-150ms | Faster than create |
| `customerGroups` query | 50-100ms | Read-only, cached |

### Impact
Sequential workflows with 5 steps → ~750ms total execution time. Parallel execution of independent steps (conditions) can reduce this.


## 16. Rate Limiting

### Discovery
Vendure demo instance has rate limiting on admin API.

### Evidence
After ~50 rapid mutations, received:
```json
{
  "errors": [
    {
      "message": "Too many requests",
      "extensions": { "code": "RATE_LIMIT_EXCEEDED" }
    }
  ]
}
```

### Observed Limits
- ~10 requests/second sustained
- Burst tolerance: ~20 requests

### Impact
Workflow engine must implement exponential backoff and respect rate limits.


## 17. Authentication Token Expiry

### Discovery
Admin API tokens have finite lifetime (appears to be 24 hours for demo instance).

### Evidence
After extended testing session, received `INVALID_CREDENTIALS` error.

### Impact
Workflow execution must handle token refresh or prompt for re-authentication.


## Summary: Key Takeaways for Universal Engine

1. **Currency Representation**: Always verify if monetary values are in smallest unit (cents, paise, etc.)
2. **Multi-Step Mutations**: Many UI actions decompose into multiple API calls; build dependency graphs carefully
3. **ID Resolution**: UI names → API IDs require lookup queries; cache results to avoid redundant queries
4. **Type Serialization**: Check argument value serialization rules (quoted strings, JSON encoding, etc.)
5. **Error Codes**: Parse structured error responses for intelligent retry/rollback logic
6. **Implicit Defaults**: Document and test default values; they may not align with intuition
7. **Logical Operators**: Understand condition evaluation logic (AND vs. OR)
8. **Rate Limits**: Respect platform rate limits; implement exponential backoff
9. **Token Lifecycle**: Handle authentication token expiry gracefully
10. **Performance**: Measure latency; parallelize independent operations where safe


## Validation Checklist

Before deploying a workflow to production, verify:

- All currency values converted to cents
- Customer group names resolved to IDs
- Condition/action codes match API documentation
- Argument values properly serialized (quoted strings for IDs)
- Dependencies between steps explicitly declared
- Error handling for duplicate entities implemented
- Rate limiting and backoff logic in place
- Authentication token refresh mechanism working
- Pre-conditions validated (group exists, code unique)
- Post-conditions verified (promotion created correctly)

