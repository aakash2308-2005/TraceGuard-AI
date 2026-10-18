"""Unit tests for the RBAC permission matrix."""

from app.auth.rbac import (
    CASE_APPROVE_ROLES,
    CASE_WRITE_ROLES,
    CaseRole,
    GlobalRole,
    role_can,
)


def test_admin_can_manage_users():
    assert role_can(GlobalRole.ADMIN, "manage_users")
    assert role_can(GlobalRole.ADMIN, "manage_config")


def test_investigator_cannot_manage_users():
    assert not role_can(GlobalRole.INVESTIGATOR, "manage_users")
    assert role_can(GlobalRole.INVESTIGATOR, "create_case")


def test_readonly_has_no_write_permissions():
    assert not role_can(GlobalRole.READONLY, "create_case")
    assert not role_can(GlobalRole.READONLY, "view_audit")


def test_case_write_and_approve_roles():
    assert CaseRole.INVESTIGATOR in CASE_WRITE_ROLES
    assert CaseRole.VIEWER not in CASE_WRITE_ROLES
    assert CaseRole.REVIEWER in CASE_APPROVE_ROLES
    assert CaseRole.INVESTIGATOR not in CASE_APPROVE_ROLES
