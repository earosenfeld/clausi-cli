# Custom Regulations Guide

## Overview

Clausi supports custom regulations in addition to the built-in regulations (EU-AIA, GDPR, HIPAA, SOC2, ISO-42001). Custom regulations allow you to define company-specific policies, internal guidelines, or any other compliance framework.

## Location

Custom regulations are stored in:
```
~/.clausi/custom_regulations/
```

## Creating a Custom Regulation

1. **Create the directory** (if it doesn't exist):
   ```bash
   mkdir -p ~/.clausi/custom_regulations
   ```

2. **Create a YAML file** with your regulation name:
   ```bash
   # Example: company-security-policy.yml
   touch ~/.clausi/custom_regulations/company-security-policy.yml
   ```

3. **Define your regulation** using the YAML format:

```yaml
name: "Company Security Policy"
description: "Internal security and compliance requirements"
version: "1.0"

clauses:
  - id: "SEC-001"
    title: "Authentication Requirements"
    description: "All applications must implement MFA"
    requirements:
      - "Implement multi-factor authentication for all user accounts"
      - "Support TOTP or hardware security keys"
      - "Enforce MFA for admin accounts"
    severity: "critical"

  - id: "SEC-002"
    title: "Data Encryption"
    description: "Sensitive data must be encrypted at rest and in transit"
    requirements:
      - "Use TLS 1.3 for all network communications"
      - "Encrypt PII data using AES-256"
      - "Store encryption keys in secure key management system"
    severity: "high"

  - id: "SEC-003"
    title: "Logging and Monitoring"
    description: "Security events must be logged and monitored"
    requirements:
      - "Log all authentication attempts"
      - "Log all data access events"
      - "Set up alerts for suspicious activity"
    severity: "warning"
```

## Using Custom Regulations

Once created, your custom regulation will automatically appear in the CLI:

```bash
# List available regulations (includes custom)
clausi models list

# Scan using custom regulation
clausi scan . -r company-security-policy

# Combine built-in and custom regulations
clausi scan . -r EU-AIA -r company-security-policy -r GDPR
```

## YAML Format Reference

### Required Fields

- `name`: Human-readable name of the regulation
- `description`: Brief description of what the regulation covers
- `clauses`: List of compliance requirements

### Clause Structure

Each clause should have:

- `id`: Unique identifier (e.g., "SEC-001", "POLICY-123")
- `title`: Short title of the requirement
- `description`: Detailed description
- `requirements`: List of specific requirements to check
- `severity`: One of: `critical`, `high`, `warning`, `info`

### Optional Fields

- `version`: Version number of your regulation
- `effective_date`: When the regulation takes effect
- `references`: External documentation links

## Example: Internal API Standards

```yaml
name: "Internal API Standards"
description: "Company standards for REST API development"
version: "2.0"
effective_date: "2024-01-01"

clauses:
  - id: "API-001"
    title: "API Authentication"
    requirements:
      - "Use OAuth 2.0 or JWT for API authentication"
      - "Include rate limiting on all public endpoints"
    severity: "critical"

  - id: "API-002"
    title: "Error Handling"
    requirements:
      - "Return proper HTTP status codes"
      - "Include error IDs for tracking"
      - "Never expose stack traces in production"
    severity: "high"
```

## Tips

1. **Start Simple**: Begin with a few key requirements
2. **Use Clear IDs**: Make clause IDs easy to reference (e.g., SEC-001, API-123)
3. **Be Specific**: Write concrete, testable requirements
4. **Version Control**: Store custom regulations in your company's git repo
5. **Share**: Distribute custom regulations to your team via git

## Backend Support

The backend automatically validates and processes custom regulations. No backend configuration needed!

