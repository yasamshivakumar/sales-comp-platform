"""
Action catalog for the Enterprise Activity & Compliance Center.

Maps action strings → module, severity, entity type, human label, and icon key.
Existing record_audit call sites keep working via inference from this catalog.
"""

# Modules tracked by the Activity Center
MODULES = (
    "dashboard",
    "orders",
    "commissions",
    "payouts",
    "compensation_plans",
    "rate_tables",
    "commission_rules",
    "compensation_overrides",
    "quotas",
    "bonuses",
    "accelerators",
    "participants",
    "people_access",
    "crm_integrations",
    "payroll",
    "reports",
    "organization_settings",
    "authentication",
    "roles_permissions",
    "api_keys",
    "audit_log",
    "documents",
)

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"
SEVERITY_SUCCESS = "success"

ICON_LOGIN = "login"
ICON_EXPORT = "export"
ICON_IMPORT = "import"
ICON_APPROVAL = "approval"
ICON_EDIT = "edit"
ICON_DELETE = "delete"
ICON_CALC = "calculation"
ICON_CRM = "crm"
ICON_PAYROLL = "payroll"
ICON_SECURITY = "security"


def _entry(module, severity=SEVERITY_INFO, entity_type="", label="", icon=ICON_EDIT):
    return {
        "module": module,
        "severity": severity,
        "entity_type": entity_type,
        "label": label,
        "icon": icon,
    }


# Canonical + legacy action aliases
ACTION_CATALOG = {
    # Authentication / security
    "login_success": _entry("authentication", SEVERITY_SUCCESS, "session", "Signed in", ICON_LOGIN),
    "login_failed": _entry("authentication", SEVERITY_WARNING, "session", "Failed sign-in", ICON_SECURITY),
    "login_locked_out": _entry("authentication", SEVERITY_CRITICAL, "session", "Login locked out", ICON_SECURITY),
    "login_mfa_required": _entry("authentication", SEVERITY_INFO, "session", "MFA required", ICON_SECURITY),
    "logout": _entry("authentication", SEVERITY_INFO, "session", "Signed out", ICON_LOGIN),
    "password_changed": _entry("authentication", SEVERITY_SUCCESS, "user", "Password changed", ICON_SECURITY),
    "mfa_enroll_started": _entry("authentication", SEVERITY_INFO, "mfa", "MFA enroll started", ICON_SECURITY),
    "mfa_enroll_confirmed": _entry("authentication", SEVERITY_SUCCESS, "mfa", "MFA enrolled", ICON_SECURITY),
    "mfa_disabled": _entry("authentication", SEVERITY_WARNING, "mfa", "MFA disabled", ICON_SECURITY),
    "sessions_revoked_all": _entry("authentication", SEVERITY_WARNING, "session", "All sessions revoked", ICON_SECURITY),
    "trusted_device_revoked": _entry("authentication", SEVERITY_WARNING, "device", "Trusted device revoked", ICON_SECURITY),
    "invite_accepted": _entry("people_access", SEVERITY_SUCCESS, "invite", "Invite accepted", ICON_LOGIN),
    # People & access
    "user_setup_created": _entry("people_access", SEVERITY_SUCCESS, "user", "User created", ICON_EDIT),
    "user_setup_updated": _entry("people_access", SEVERITY_INFO, "user", "User updated", ICON_EDIT),
    "user_setup_upload": _entry("people_access", SEVERITY_INFO, "user", "Users CSV imported", ICON_IMPORT),
    "user_setup_upload_queued": _entry("people_access", SEVERITY_INFO, "user", "Users CSV queued", ICON_IMPORT),
    "invitation_sent": _entry("people_access", SEVERITY_INFO, "invite", "Invite sent", ICON_EDIT),
    "invite_resent": _entry("people_access", SEVERITY_INFO, "invite", "Invite resent", ICON_EDIT),
    "invite_revoked": _entry("people_access", SEVERITY_WARNING, "invite", "Invite revoked", ICON_DELETE),
    "invite_link_copied": _entry("people_access", SEVERITY_INFO, "invite", "Invite link copied", ICON_EDIT),
    "role_changed": _entry("roles_permissions", SEVERITY_WARNING, "user", "Role assigned", ICON_SECURITY),
    "permission_changed": _entry("roles_permissions", SEVERITY_WARNING, "user", "Permission changed", ICON_SECURITY),
    "quota_changed": _entry("quotas", SEVERITY_INFO, "user", "Quota changed", ICON_EDIT),
    "plan_assigned": _entry("participants", SEVERITY_INFO, "user", "Plan assigned", ICON_EDIT),
    "people_profile_updated": _entry("people_access", SEVERITY_INFO, "user", "Profile updated", ICON_EDIT),
    "people_exported": _entry("people_access", SEVERITY_INFO, "user", "People exported", ICON_EXPORT),
    "people_bulk_action": _entry("people_access", SEVERITY_INFO, "user", "People bulk action", ICON_EDIT),
    "territory_changed": _entry("people_access", SEVERITY_INFO, "user", "Territory changed", ICON_EDIT),
    "territory_created": _entry("organization_settings", SEVERITY_SUCCESS, "territory", "Territory created", ICON_EDIT),
    "territory_updated": _entry("organization_settings", SEVERITY_INFO, "territory", "Territory updated", ICON_EDIT),
    "territory_deleted": _entry("organization_settings", SEVERITY_WARNING, "territory", "Territory deleted", ICON_DELETE),
    "hierarchy_created": _entry("people_access", SEVERITY_INFO, "hierarchy", "Hierarchy link created", ICON_EDIT),
    # Orders
    "order_created": _entry("orders", SEVERITY_SUCCESS, "order", "Order created", ICON_EDIT),
    "order_updated": _entry("orders", SEVERITY_INFO, "order", "Order edited", ICON_EDIT),
    "orders_upload": _entry("orders", SEVERITY_INFO, "order", "Orders CSV imported", ICON_IMPORT),
    "orders_upload_queued": _entry("orders", SEVERITY_INFO, "order", "Orders CSV queued", ICON_IMPORT),
    "orders_bulk_approved": _entry("orders", SEVERITY_SUCCESS, "order", "Orders approved", ICON_APPROVAL),
    "orders_bulk_recalculate": _entry("orders", SEVERITY_INFO, "order", "Orders recalculated", ICON_CALC),
    # Commissions / payouts / payroll
    "commissions_recalculated": _entry("commissions", SEVERITY_INFO, "commission", "Commissions recalculated", ICON_CALC),
    "commission_calculated": _entry("commissions", SEVERITY_SUCCESS, "commission", "Commission calculated", ICON_CALC),
    "commissions_manager_approved": _entry("commissions", SEVERITY_SUCCESS, "commission", "Manager approved commissions", ICON_APPROVAL),
    "commissions_finance_approved": _entry("commissions", SEVERITY_SUCCESS, "commission", "Finance approved commissions", ICON_APPROVAL),
    "commissions_approved": _entry("commissions", SEVERITY_SUCCESS, "commission", "Commissions approved", ICON_APPROVAL),
    "commission_dispute_opened": _entry("commissions", SEVERITY_WARNING, "dispute", "Dispute opened", ICON_EDIT),
    "commission_dispute_resolved": _entry("commissions", SEVERITY_SUCCESS, "dispute", "Dispute resolved", ICON_APPROVAL),
    "commission_dispute_acknowledged": _entry("commissions", SEVERITY_INFO, "dispute", "Dispute acknowledged", ICON_EDIT),
    "payout_run_created": _entry("payouts", SEVERITY_INFO, "payout", "Payout run created", ICON_PAYROLL),
    "payout_run_paid": _entry("payouts", SEVERITY_SUCCESS, "payout", "Payout approved / paid", ICON_PAYROLL),
    "payroll_exported": _entry("payroll", SEVERITY_INFO, "payroll", "Payroll exported", ICON_EXPORT),
    # Plans / rates / rules
    "compensation_plan_created": _entry("compensation_plans", SEVERITY_SUCCESS, "plan", "Plan created", ICON_EDIT),
    "compensation_plan_updated": _entry("compensation_plans", SEVERITY_INFO, "plan", "Plan updated", ICON_EDIT),
    "compensation_tier_created": _entry("rate_tables", SEVERITY_SUCCESS, "rate", "Rate added", ICON_EDIT),
    "plan_version.clone": _entry("compensation_plans", SEVERITY_INFO, "plan_version", "Plan version cloned", ICON_EDIT),
    "plan_version.publish": _entry("compensation_plans", SEVERITY_SUCCESS, "plan_version", "Plan published", ICON_APPROVAL),
    "plan_version.archive": _entry("compensation_plans", SEVERITY_WARNING, "plan_version", "Plan archived", ICON_DELETE),
    "plan_version.delete": _entry("compensation_plans", SEVERITY_WARNING, "plan_version", "Plan version deleted", ICON_DELETE),
    "plan_version_cloned": _entry("compensation_plans", SEVERITY_INFO, "plan_version", "Plan version cloned", ICON_EDIT),
    "plan_version_published": _entry("compensation_plans", SEVERITY_SUCCESS, "plan_version", "Plan published", ICON_APPROVAL),
    "plan_version_archived": _entry("compensation_plans", SEVERITY_WARNING, "plan_version", "Plan archived", ICON_DELETE),
    "ai_compensation_plan_created": _entry("compensation_plans", SEVERITY_SUCCESS, "plan", "AI plan created", ICON_EDIT),
    "rule_updated": _entry("commission_rules", SEVERITY_INFO, "rule", "Rule updated", ICON_EDIT),
    # Employee compensation overrides
    "compensation_override_created": _entry("compensation_overrides", SEVERITY_WARNING, "compensation_override", "Commission override created", ICON_EDIT),
    "compensation_override_updated": _entry("compensation_overrides", SEVERITY_WARNING, "compensation_override", "Commission override updated", ICON_EDIT),
    "compensation_override_submitted": _entry("compensation_overrides", SEVERITY_INFO, "compensation_override", "Override submitted for approval", ICON_APPROVAL),
    "compensation_override_approved": _entry("compensation_overrides", SEVERITY_SUCCESS, "compensation_override", "Override approved", ICON_APPROVAL),
    "compensation_override_rejected": _entry("compensation_overrides", SEVERITY_WARNING, "compensation_override", "Override rejected", ICON_APPROVAL),
    "compensation_override_expired": _entry("compensation_overrides", SEVERITY_INFO, "compensation_override", "Override expired", ICON_EDIT),
    "compensation_override_removed": _entry("compensation_overrides", SEVERITY_CRITICAL, "compensation_override", "Override removed", ICON_DELETE),
    # CRM
    "integration_created": _entry("crm_integrations", SEVERITY_SUCCESS, "integration", "CRM connected", ICON_CRM),
    "integration_updated": _entry("crm_integrations", SEVERITY_INFO, "integration", "Integration updated", ICON_CRM),
    "integration_deleted": _entry("crm_integrations", SEVERITY_WARNING, "integration", "Integration deleted", ICON_DELETE),
    "crm_connected": _entry("crm_integrations", SEVERITY_SUCCESS, "integration", "CRM connected", ICON_CRM),
    "crm_identity_mapped": _entry("crm_integrations", SEVERITY_INFO, "integration", "CRM identity mapped", ICON_CRM),
    "field_mapping_updated": _entry("crm_integrations", SEVERITY_INFO, "integration", "Field mapping updated", ICON_CRM),
    "crm_sync_started": _entry("crm_integrations", SEVERITY_INFO, "integration", "CRM sync started", ICON_CRM),
    "crm_sync_completed": _entry("crm_integrations", SEVERITY_SUCCESS, "integration", "CRM sync completed", ICON_CRM),
    "crm_sync_failed": _entry("crm_integrations", SEVERITY_CRITICAL, "integration", "CRM sync failed", ICON_CRM),
    # Reports / exports / API keys / settings / audit
    "report_exported": _entry("reports", SEVERITY_INFO, "report", "Report exported", ICON_EXPORT),
    "api_key_created": _entry("api_keys", SEVERITY_WARNING, "api_key", "API key created", ICON_SECURITY),
    "api_key_deleted": _entry("api_keys", SEVERITY_WARNING, "api_key", "API key deleted", ICON_DELETE),
    "settings_changed": _entry("organization_settings", SEVERITY_WARNING, "settings", "Settings changed", ICON_EDIT),
    "organization_settings_updated": _entry(
        "organization_settings", SEVERITY_WARNING, "settings", "Organization settings updated", ICON_EDIT
    ),
    "profile_updated": _entry("people_access", SEVERITY_INFO, "user", "Account profile updated", ICON_EDIT),
    "document_uploaded": _entry("documents", SEVERITY_SUCCESS, "document", "Document uploaded", ICON_IMPORT),
    "document_viewed": _entry("documents", SEVERITY_INFO, "document", "Document viewed", ICON_EXPORT),
    "document_downloaded": _entry("documents", SEVERITY_INFO, "document", "Document downloaded", ICON_EXPORT),
    "document_version_updated": _entry(
        "documents", SEVERITY_WARNING, "document", "Document version updated", ICON_EDIT
    ),
    "document_version_restored": _entry(
        "documents", SEVERITY_WARNING, "document", "Document version restored", ICON_EDIT
    ),
    "document_approved": _entry("documents", SEVERITY_SUCCESS, "document", "Document approved", ICON_EDIT),
    "document_reviewed": _entry("documents", SEVERITY_INFO, "document", "Document reviewed", ICON_EDIT),
    "document_published": _entry("documents", SEVERITY_SUCCESS, "document", "Document published", ICON_EDIT),
    "document_archived": _entry("documents", SEVERITY_WARNING, "document", "Document archived", ICON_DELETE),
    "document_deleted": _entry("documents", SEVERITY_CRITICAL, "document", "Document deleted", ICON_DELETE),
    "document_updated": _entry("documents", SEVERITY_INFO, "document", "Document updated", ICON_EDIT),
    "audit_export": _entry("audit_log", SEVERITY_INFO, "audit", "Audit log exported", ICON_EXPORT),
    "report_created": _entry("reports", SEVERITY_SUCCESS, "report", "Report created", ICON_EDIT),
    "report_viewed": _entry("reports", SEVERITY_INFO, "report", "Report viewed", ICON_EXPORT),
    "report_modified": _entry("reports", SEVERITY_INFO, "report", "Report modified", ICON_EDIT),
    "report_deleted": _entry("reports", SEVERITY_WARNING, "report", "Report deleted", ICON_DELETE),
    "report_scheduled": _entry("reports", SEVERITY_INFO, "report", "Report scheduled", ICON_EDIT),
    "report_exported": _entry("reports", SEVERITY_INFO, "report", "Report exported", ICON_EXPORT),
    "ai_dashboard_insights_generated": _entry("dashboard", SEVERITY_INFO, "dashboard", "Dashboard insights generated", ICON_CALC),
}

# Prefix rules for dynamic actions (e.g. integration_sync_orders)
_PREFIX_RULES = (
    ("integration_sync_", _entry("crm_integrations", SEVERITY_INFO, "integration", "CRM sync", ICON_CRM)),
    ("commission_", _entry("commissions", SEVERITY_INFO, "commission", "Commission action", ICON_CALC)),
    ("payout_", _entry("payouts", SEVERITY_INFO, "payout", "Payout action", ICON_PAYROLL)),
    ("orders_bulk_", _entry("orders", SEVERITY_INFO, "order", "Orders bulk action", ICON_EDIT)),
    ("plan_version.", _entry("compensation_plans", SEVERITY_INFO, "plan_version", "Plan version action", ICON_EDIT)),
)


SECURITY_ACTIONS = frozenset(
    {
        "login_failed",
        "login_locked_out",
        "login_mfa_required",
        "password_changed",
        "mfa_disabled",
        "sessions_revoked_all",
        "trusted_device_revoked",
        "role_changed",
        "permission_changed",
        "api_key_created",
        "api_key_deleted",
        "settings_changed",
    }
)

EXPORT_ACTIONS = frozenset(
    {
        "people_exported",
        "payroll_exported",
        "report_exported",
        "audit_export",
    }
)

CRM_SYNC_ACTIONS = frozenset(
    {
        "crm_sync_started",
        "crm_sync_completed",
        "crm_sync_failed",
    }
)

PAYROLL_ACTIONS = frozenset(
    {
        "payout_run_created",
        "payout_run_paid",
        "payroll_exported",
    }
)


def resolve_action(action):
    """Return catalog metadata for an action string."""
    key = str(action or "").strip()
    if key in ACTION_CATALOG:
        return dict(ACTION_CATALOG[key])
    for prefix, meta in _PREFIX_RULES:
        if key.startswith(prefix):
            out = dict(meta)
            out["label"] = out["label"] or key.replace("_", " ").replace(".", " ")
            return out
    return _entry(
        "organization_settings",
        SEVERITY_INFO,
        "",
        key.replace("_", " ").replace(".", " ") or "Activity",
        ICON_EDIT,
    )


def action_label(action):
    return resolve_action(action).get("label") or action


def is_security_action(action):
    key = str(action or "")
    if key in SECURITY_ACTIONS:
        return True
    meta = resolve_action(key)
    return meta.get("module") == "authentication" or meta.get("icon") == ICON_SECURITY
