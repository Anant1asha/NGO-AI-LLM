"""
Google Integration Hub

The main entry point for the Google Workspace module.
It dynamically discovers required scopes and registers all tools from all active services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hachi.core.loop import ToolRegistry
from hachi.integrations.google.calendar import CalendarService
from hachi.integrations.google.client import GoogleHTTPClient
from hachi.integrations.google.contacts import ContactsService
from hachi.integrations.google.docs import DocsService
from hachi.integrations.google.drive import DriveService

# Import specific services
from hachi.integrations.google.gmail import GmailService
from hachi.integrations.google.meet import MeetService
from hachi.integrations.google.planning import PlanningService
from hachi.integrations.google.service import GoogleService
from hachi.integrations.google.sheets import SheetsService
from hachi.integrations.google.tasks import TasksService

if TYPE_CHECKING:
    from hachi.core.approvals import ActionApprover


class GoogleIntegrationHub:
    """
    The orchestrator for all Google Workspace plugins.
    Instantiates services, aggregates required scopes, and mounts tools.
    """

    def __init__(self, approver: ActionApprover | None = None):
        # 1. Instantiate the services without a client first to aggregate scopes
        self._services: list[GoogleService] = []

        # Instantiate services (temporarily passing None for client to get scopes)
        gmail = GmailService(client=None)  # type: ignore
        calendar = CalendarService(client=None)  # type: ignore
        drive = DriveService(client=None)  # type: ignore
        docs = DocsService(client=None)  # type: ignore
        sheets = SheetsService(client=None)  # type: ignore
        contacts = ContactsService(client=None)  # type: ignore
        meet = MeetService(client=None)  # type: ignore
        tasks = TasksService(client=None)  # type: ignore
        planning = PlanningService(client=None)  # type: ignore

        # Aggregate scopes dynamically
        all_scopes = set()
        all_scopes.update(gmail.required_scopes)
        all_scopes.update(calendar.required_scopes)
        all_scopes.update(drive.required_scopes)
        all_scopes.update(docs.required_scopes)
        all_scopes.update(sheets.required_scopes)
        all_scopes.update(contacts.required_scopes)
        all_scopes.update(meet.required_scopes)
        all_scopes.update(tasks.required_scopes)
        all_scopes.update(planning.required_scopes)

        # 2. Instantiate the actual client with the aggregated scopes
        self.client = GoogleHTTPClient(scopes=list(all_scopes))
        # Wire the session approver so all destructive leaf tools can gate actions.
        self.client.approver = approver

        # 3. Fully initialize services with the working client
        self._services = [
            GmailService(client=self.client),
            CalendarService(client=self.client),
            DriveService(client=self.client),
            DocsService(client=self.client),
            SheetsService(client=self.client),
            ContactsService(client=self.client),
            MeetService(client=self.client),
            TasksService(client=self.client),
            PlanningService(client=self.client),
        ]

    def register_tools(self, registry: ToolRegistry) -> None:
        """
        Loops through all active plugins and mounts their tools into the agent.
        """
        for service in self._services:
            service.register_tools(registry)
