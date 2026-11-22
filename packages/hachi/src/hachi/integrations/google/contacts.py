import json

from hachi.core.loop import ToolRegistry
from hachi.core.validators import validate_email, validate_phone
from hachi.integrations.google.service import GoogleService


class ContactsService(GoogleService):
    """
    Google Contacts Integration (The Identity Layer)
    Provides autonomous resolution of names to emails/phone numbers.
    """

    @property
    def required_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/contacts"]

    def register_tools(self, registry: ToolRegistry) -> None:
        def google_search_contact(name: str) -> str:
            """Search contacts by display name substring.

            Note: matching is substring-based (case-insensitive) against the full
            contact list; for large address books consider the People API
            ``searchContacts`` endpoint instead.
            """
            try:
                response = self.client.get(
                    "https://people.googleapis.com/v1/people/me/connections"
                    "?personFields=names,emailAddresses,phoneNumbers&pageSize=1000"
                )

                search_lower = name.lower()
                matches = []
                for person in response.get("connections", []):
                    person_names = person.get("names", [])
                    if any(search_lower in n.get("displayName", "").lower() for n in person_names):
                        emails = [e.get("value") for e in person.get("emailAddresses", [])]
                        phones = [p.get("value") for p in person.get("phoneNumbers", [])]

                        matches.append(
                            {
                                "resourceName": person.get("resourceName", ""),
                                "name": person_names[0].get("displayName")
                                if person_names
                                else "Unknown",
                                "emails": emails,
                                "phones": phones,
                            }
                        )

                if not matches:
                    return f"No contacts found matching '{name}'."

                return (
                    f"Found {len(matches)} match(es) for '{name}':\n{json.dumps(matches, indent=2)}"
                )
            except Exception as e:
                return f"Failed to search Google Contacts: {str(e)}"

        def google_create_contact(name: str, email: str) -> str:
            """Create a new Google Contact after validating the email address."""
            # UC-CONTACT-001: validate email before touching the API
            ok_email, email_result = validate_email(email)
            if not ok_email:
                return f"Invalid email address: {email_result}"

            try:
                body = {
                    "names": [{"givenName": name}],
                    "emailAddresses": [{"value": email_result}],
                }
                self.client.post(
                    "https://people.googleapis.com/v1/people:createContact", json_data=body
                )
                return f"Successfully saved new contact: {name} ({email_result})."
            except Exception as e:
                return f"Failed to create Google Contact: {str(e)}"

        def google_update_contact(
            resourceName: str, phone: str | None = None, email: str | None = None
        ) -> str:
            """Update an existing Google Contact after validating any supplied values."""
            # UC-CONTACT-001: validate before touching the API
            if email is not None:
                ok_email, email_result = validate_email(email)
                if not ok_email:
                    return f"Invalid email address: {email_result}"
                email = email_result

            if phone is not None:
                ok_phone, phone_result = validate_phone(phone)
                if not ok_phone:
                    return f"Invalid phone number: {phone_result}"
                phone = phone_result

            try:
                # 1. Fetch existing contact to get the required etag
                person = self.client.get(
                    f"https://people.googleapis.com/v1/{resourceName}"
                    "?personFields=names,emailAddresses,phoneNumbers"
                )

                update_fields = []
                # 2. Append new data
                if phone:
                    phones = person.get("phoneNumbers", [])
                    phones.append({"value": phone})
                    person["phoneNumbers"] = phones
                    update_fields.append("phoneNumbers")

                if email:
                    emails = person.get("emailAddresses", [])
                    emails.append({"value": email})
                    person["emailAddresses"] = emails
                    update_fields.append("emailAddresses")

                if not update_fields:
                    return "No updates provided."

                # 3. Send the PATCH request
                fields_str = ",".join(update_fields)
                self.client.patch(
                    f"https://people.googleapis.com/v1/{resourceName}"
                    f":updateContact?updatePersonFields={fields_str}",
                    json_data=person,
                )
                return "Successfully updated contact."
            except Exception as e:
                return f"Failed to update Google Contact: {str(e)}"

        def google_list_contacts(max_results: int = 50) -> str:
            """List saved Google Contacts up to *max_results* entries."""
            try:
                matches = []
                page_token: str | None = None
                while len(matches) < max_results:
                    batch_size = min(max_results - len(matches), 1000)
                    url = (
                        f"https://people.googleapis.com/v1/people/me/connections"
                        f"?personFields=names,emailAddresses,phoneNumbers&pageSize={batch_size}"
                    )
                    if page_token:
                        url += f"&pageToken={page_token}"
                    response = self.client.get(url)
                    for person in response.get("connections", []):
                        person_names = person.get("names", [])
                        emails = [e.get("value") for e in person.get("emailAddresses", [])]
                        phones = [p.get("value") for p in person.get("phoneNumbers", [])]
                        matches.append(
                            {
                                "resourceName": person.get("resourceName", ""),
                                "name": person_names[0].get("displayName")
                                if person_names
                                else "Unknown",
                                "emails": emails,
                                "phones": phones,
                            }
                        )
                    page_token = response.get("nextPageToken")
                    if not page_token:
                        break

                if not matches:
                    return "No contacts found."

                return f"Found {len(matches)} contacts:\n{json.dumps(matches, indent=2)}"
            except Exception as e:
                return f"Failed to list Google Contacts: {str(e)}"

        def google_delete_contact(resourceName: str) -> str:
            """Permanently delete a Google Contact — requires explicit approval.

            UC-CONTACT-002: the action is gated behind ``require_approval`` so that
            a single conversational instruction cannot silently destroy contact data.
            """
            ok, reason = self.require_approval(
                action="delete_contact",
                summary=f"Delete contact {resourceName}",
                detail=(
                    f"Permanently removes the Google Contact with resource name "
                    f"'{resourceName}'. This cannot be undone."
                ),
            )
            if not ok:
                return f"⛔ Action not approved: {reason}"

            try:
                self.client.delete(f"https://people.googleapis.com/v1/{resourceName}:deleteContact")
                return f"Successfully deleted contact: {resourceName}"
            except Exception as e:
                return f"Failed to delete Google Contact: {str(e)}"

        registry.register(
            {
                "name": "google_search_contact",
                "description": "Fuzzy search the user's Google Contacts to find someone's exact "
                "email address or phone number. ALWAYS use this if the user asks you to email "
                "someone but doesn't provide the email.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name or partial name of the person to search for.",
                        }
                    },
                    "required": ["name"],
                },
            },
            google_search_contact,
        )

        registry.register(
            {
                "name": "google_create_contact",
                "description": "Autonomously save a new contact to the user's Google Contacts.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The full name of the contact."},
                        "email": {
                            "type": "string",
                            "description": "The email address to associate with them.",
                        },
                    },
                    "required": ["name", "email"],
                },
            },
            google_create_contact,
        )

        registry.register(
            {
                "name": "google_update_contact",
                "description": "Update an existing Google Contact with a new phone number or "
                "email.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "resourceName": {
                            "type": "string",
                            "description": "The resourceName of the contact (e.g. people/c123456). "
                            "Fetch this first using google_search_contact.",
                        },
                        "phone": {"type": "string", "description": "New phone number to add."},
                        "email": {"type": "string", "description": "New email address to add."},
                    },
                    "required": ["resourceName"],
                },
            },
            google_update_contact,
        )

        registry.register(
            {
                "name": "google_list_contacts",
                "description": "Fetch a list of all saved Google Contacts. Use this when the user "
                "asks 'fetch my contacts' or 'who is in my contacts'.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of contacts to return (default: 50)",
                        }
                    },
                },
            },
            google_list_contacts,
        )

        registry.register(
            {
                "name": "google_delete_contact",
                "description": "DANGER: Permanently delete a Google Contact. "
                "This action requires explicit approval before it is executed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "resourceName": {
                            "type": "string",
                            "description": "The resourceName of the contact to delete "
                            "(e.g. people/c123456).",
                        }
                    },
                    "required": ["resourceName"],
                },
            },
            google_delete_contact,
        )
