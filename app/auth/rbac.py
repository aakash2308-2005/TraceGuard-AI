"""Role-based access control definitions.

Global roles gate coarse capabilities; case memberships gate per-case access.
Both are enforced on the backend (SEC-001).
"""

from enum import Enum


class GlobalRole(str, Enum):
    ADMIN = "admin"
    LEAD = "lead_investigator"
    INVESTIGATOR = "investigator"
    REVIEWER = "reviewer"
    READONLY = "readonly"


class CaseRole(str, Enum):
    LEAD = "lead"
    INVESTIGATOR = "investigator"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


# Permission flags attached to each global role.
ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    GlobalRole.ADMIN: {
        "manage_users": True,
        "manage_config": True,
        "create_case": True,
        "view_audit": True,
    },
    GlobalRole.LEAD: {
        "manage_users": False,
        "manage_config": False,
        "create_case": True,
        "view_audit": True,
    },
    GlobalRole.INVESTIGATOR: {
        "manage_users": False,
        "manage_config": False,
        "create_case": True,
        "view_audit": False,
    },
    GlobalRole.REVIEWER: {
        "manage_users": False,
        "manage_config": False,
        "create_case": False,
        "view_audit": False,
    },
    GlobalRole.READONLY: {
        "manage_users": False,
        "manage_config": False,
        "create_case": False,
        "view_audit": False,
    },
}

# Case roles that may write (upload evidence, start investigations).
CASE_WRITE_ROLES = {CaseRole.LEAD, CaseRole.INVESTIGATOR}
# Case roles that may approve reports.
CASE_APPROVE_ROLES = {CaseRole.LEAD, CaseRole.REVIEWER}


def role_can(role: str, permission: str) -> bool:
    """Return True if the global role grants the permission."""
    return ROLE_PERMISSIONS.get(role, {}).get(permission, False)
