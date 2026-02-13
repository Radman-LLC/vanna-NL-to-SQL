# User Permissions and Access Control

Vanna provides group-based access control that restricts which tools and features are available to different users. This guide explains how to configure user permissions and manage access to Vanna's capabilities.

## How Access Control Works

Vanna uses a group-based permission model. Each user belongs to one or more groups, and each tool declares which groups are allowed to use it. When a user sends a request, the system checks the user's groups against the tool's allowed groups before executing.

This ensures that:

- Sensitive operations (for example, saving training data) are limited to administrators.
- Standard users can query data but cannot modify system configuration.
- Different teams see only the tools relevant to their role.

## Configuring Users

### Define a User

Create a user with specific group memberships:

```python
from vanna.core.user import User

user = User(
    user_id="user123",
    user_email="user@example.com",
    user_groups=["sales", "analytics"]
)
```

### User Properties

- **user_id**: Unique identifier for the user.
- **user_email**: User's email address.
- **user_groups**: List of groups the user belongs to.

### Resolving Users

Implement a `UserResolver` to determine user identity from incoming requests:

```python
from vanna.core.user import UserResolver, User

class MyUserResolver(UserResolver):
    async def resolve(self, request) -> User:
        # Look up user from authentication token, session, etc.
        return User(
            user_id="user123",
            user_email="user@example.com",
            user_groups=["analytics"]
        )
```

## Typical User Groups

The following groups represent a common access model:

### Administrators

Full access to all features, including:

- Running SQL queries
- Saving and managing training data
- Viewing all data across stores
- Running financial reports

### Sales Representatives

Access to sales-related data:

- Running SQL queries for assigned customers
- Viewing commission reports
- Accessing customer relationship data

### Warehouse Staff

Access to inventory and fulfillment data:

- Viewing inventory levels and stock locations
- Running fulfillment and picking queries
- Accessing purchase order receiving data

### Accounting

Access to financial data:

- Running accounts receivable and aging reports
- Viewing transaction and payment reports
- Accessing customer credit and statement data

### Read-Only Users

Limited access for data consumers:

- Running SQL queries
- Viewing query results
- No access to training data management or system configuration

## Tool Permissions

### How Tool Access Groups Work

Each tool declares which groups can use it:

```python
class MyTool(Tool[MyToolArgs]):
    name = "my_tool"
    description = "Does something useful"
    access_groups = ["admin", "analytics"]  # Only these groups can use this tool
```

When a user requests a tool, the Tool Registry checks whether any of the user's groups match the tool's `access_groups`. If there is no match, the request is denied.

### Default Tool Access

- **SQL query execution**: Available to all authenticated users by default.
- **Memory management** (save, search): Typically restricted to administrators.
- **Data visualization**: Available to all authenticated users.

## Configuring Access Control

### Set Up User Resolution

Add the user resolver to your agent:

```python
from vanna import Agent, AgentConfig

agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    user_resolver=MyUserResolver(),
    ...
)
```

### Test Permissions

Verify that permissions work correctly:

1. Log in as a standard user (for example, with "analytics" group).
2. Confirm SQL queries execute successfully.
3. Attempt to save training data (should be denied for non-administrators).
4. Log in as an administrator and confirm full access.

## Best Practices

### Use Least Privilege

Assign users to the minimum groups required for their role. This limits exposure if credentials are compromised.

### Separate Read and Write Access

- Use read-only database connections for most users.
- Reserve write access for specific administrative tasks.

### Review Permissions Regularly

Periodically review user group assignments to ensure they remain appropriate as roles change.

### Combine with Database-Level Security

Vanna's access control works at the tool level. For additional security, use database-level permissions (for example, read-only database accounts) to prevent unintended data modification.

## Troubleshooting

### User Cannot Access a Tool

**Symptom:** A user receives a permission denied error when attempting to use a tool.

**Solutions:**
- Verify the user's group memberships.
- Check the tool's `access_groups` configuration.
- Confirm the user resolver returns the correct groups.

### All Users Have Full Access

**Symptom:** Permissions are not enforced and all users can access everything.

**Solutions:**
- Verify that a user resolver is configured on the agent.
- Check that tools have `access_groups` defined.
- Confirm the Tool Registry is performing permission checks.

### User Groups Not Recognized

**Symptom:** User groups are set but not matched against tool permissions.

**Solutions:**
- Verify that group names match exactly (case-sensitive).
- Check that the user resolver returns groups as a list of strings.
- Confirm the agent is using the correct user resolver.

## Related Topics

- [Getting Started with Vanna](getting-started.md): Initial setup and configuration.
- [Configuring Vanna for Your Database](domain-configuration.md): Define business rules and conventions.
