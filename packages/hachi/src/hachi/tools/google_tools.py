"""Google Workspace tools — wire the GoogleIntegrationHub into the ToolRegistry.

All 44 google_* tools (Gmail, Calendar, Drive, Docs, Sheets, Contacts, Meet,
Tasks, Planning) are registered as a lazy ``google`` tool group so they do not
bloat every turn's context.

Registration is **conditional**: if ``GOOGLE_CLIENT_ID`` is not set in the
environment, a single friendly stub is registered instead — it tells the agent
how to configure the integration rather than crashing silently.

Each tool authenticates lazily via the OAuth manager; the first call triggers
the browser consent flow if no cached token exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hachi.core.loop import ToolRegistry

if TYPE_CHECKING:
    from hachi.core.approvals import ActionApprover

# The full set of tool names the hub registers — used to populate
# _GROUP_BY_TOOL_NAME in the orchestrator without hard-coding them twice.
GOOGLE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "google_send_email",
        "google_list_emails",
        "google_search_emails",
        "google_create_draft",
        "google_reply_thread",
        "google_read_email_thread",
        "google_archive_email",
        "google_mark_email_read",
        "google_categorize_email",
        "google_batch_categorize_emails",
        "google_list_gmail_labels",
        "google_create_gmail_label",
        "google_get_events_for_date",
        "google_list_events",
        "google_create_event",
        "google_create_recurring_event",
        "google_update_event",
        "google_delete_event",
        "google_find_free_time",
        "google_plan_my_day",
        "google_search_drive",
        "google_upload_file",
        "google_move_file",
        "google_trash_file",
        "google_share_file",
        "google_create_folder",
        "google_read_doc",
        "google_create_doc",
        "google_append_doc_text",
        "google_read_sheet",
        "google_create_sheet",
        "google_append_sheet_row",
        "google_list_contacts",
        "google_search_contact",
        "google_create_contact",
        "google_update_contact",
        "google_delete_contact",
        "google_monitor_meeting",
        "google_list_task_lists",
        "google_list_tasks",
        "google_create_task",
        "google_complete_task",
        "google_update_task",
        "google_delete_task",
    }
)

_NOT_CONFIGURED_SCHEMA: dict[str, object] = {
    "name": "google_not_configured",
    "description": (
        "Google Workspace integration is not configured. "
        "Set GOOGLE_CLIENT_ID (and optionally GOOGLE_CLIENT_SECRET) in your environment "
        "and restart Hachi to unlock Gmail, Calendar, Drive, and 40+ other tools."
    ),
    "input_schema": {"type": "object", "properties": {}},
}


def register_google_tools(registry: ToolRegistry, approver: ActionApprover | None = None) -> bool:
    """Register all Google Workspace tools into *registry*.

    Returns ``True`` if the hub was fully mounted (``GOOGLE_CLIENT_ID`` set),
    ``False`` if only the stub was registered.

    All tools are tagged with the ``google`` lazy group so the orchestrator
    only activates them for turns that need Google access.

    Args:
        registry: The agent's :class:`~hachi.core.loop.ToolRegistry`.
        approver: Optional :class:`~hachi.core.approvals.ActionApprover` to wire
                  into the hub so leaf tools can gate destructive actions.  ``None``
                  keeps backward compatibility — the client will fail-safe (deny) when
                  a destructive action is requested without an approver.
    """
    # Resolve GOOGLE_CLIENT_ID the same lazy way the OAuth flow does — from the process
    # environment OR a project / config-dir .env — so a value configured anywhere (incl. via
    # `hachi setup`, which writes config_dir/.env) mounts the real hub, not the stub.
    from hachi.core.oauth import _google_client_id

    if not _google_client_id():
        registry.register(
            _NOT_CONFIGURED_SCHEMA,
            lambda: (
                "Google Workspace integration is not configured. "
                "Set GOOGLE_CLIENT_ID (in your environment or .env), then restart Hachi."
            ),
            group="google",
        )
        return False

    from hachi.integrations.google import GoogleIntegrationHub

    hub = GoogleIntegrationHub(approver=approver)
    hub.register_tools(registry)

    # Re-tag every registered google_* tool with the lazy group so the
    # orchestrator's use_tools("google") activates them correctly.
    for name in GOOGLE_TOOL_NAMES:
        if name in registry._tools:
            registry._groups[name] = "google"

    return True
