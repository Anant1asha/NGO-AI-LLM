"""
Google Docs Service Plugin
"""

from hachi.core.loop import ToolRegistry
from hachi.core.untrusted_content import guard_untrusted
from hachi.integrations.google.service import GoogleService

# Maximum characters returned by read_doc before truncation.
# The Docs API can return very large documents; we cap at 50 000 chars
# to avoid context-window exhaustion.
_READ_DOC_CHAR_LIMIT = 50_000


class DocsService(GoogleService):
    @property
    def required_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/documents"]

    def create_doc(self, title: str, initial_content: str = "") -> str:
        """Creates a Google Document and optionally inserts content."""
        response = self.client.post(
            "https://docs.googleapis.com/v1/documents", json_data={"title": title}
        )
        doc_id = response.get("documentId")

        if doc_id and initial_content:
            requests = [{"insertText": {"location": {"index": 1}, "text": initial_content}}]
            self.client.post(
                f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
                json_data={"requests": requests},
            )

        return (
            f"Document '{title}' created successfully. ID: {doc_id} "
            f"[Link: https://docs.google.com/document/d/{doc_id}]"
        )

    def read_doc(self, doc_id: str) -> str:
        """Reads text content from a Google Document.

        Returns at most 50 000 characters. Longer documents are truncated with a
        note at the end. Returned text is passed through the untrusted-content guard
        (ADV-003) because document content is third-party data.
        """
        try:
            doc = self.client.get(f"https://docs.googleapis.com/v1/documents/{doc_id}")
            content = doc.get("body", {}).get("content", [])
            text_chunks = []

            for element in content:
                if "paragraph" in element:
                    for element_item in element["paragraph"].get("elements", []):
                        if "textRun" in element_item:
                            text_chunks.append(element_item["textRun"]["content"])

            raw_text = "".join(text_chunks)

            # UC-DOCS-002: cap very large documents
            truncated = False
            if len(raw_text) > _READ_DOC_CHAR_LIMIT:
                raw_text = raw_text[:_READ_DOC_CHAR_LIMIT]
                truncated = True

            # ADV-003: frame as untrusted external data
            framed, flagged = guard_untrusted(raw_text, source=f"Google Doc {doc_id}")

            result = framed
            if truncated:
                char_limit_k = _READ_DOC_CHAR_LIMIT // 1000
                result += (
                    f"\n\n[NOTE: Document truncated at {char_limit_k}k characters. "
                    "Request a specific page range or section to read more.]"
                )

            return result
        except Exception as e:
            return f"⛔ Failed to read document: {str(e)}"

    def append_doc_text(self, doc_id: str, text: str) -> str:
        """Appends text to the end of a Google Document.

        UC-DOCS-001: The end-index from the Docs API is the *exclusive* bound of the
        last segment. For a completely empty document the body has a single structural
        element with endIndex=1, so inserting at index 1 is correct.  For documents
        with content the final element's endIndex is one past the last character, so
        we must insert at ``endIndex - 1`` to land *before* the implicit trailing
        newline that the API enforces at position 0.
        """
        try:
            # Get the current document to find the end index
            doc = self.client.get(f"https://docs.googleapis.com/v1/documents/{doc_id}")
            content = doc.get("body", {}).get("content", [])

            # UC-DOCS-001 fix: the Docs API body always ends with a structural
            # element (often a sectionBreak or paragraph) whose endIndex equals
            # the exclusive length of the document + 1.
            # For an empty document:  content[-1].endIndex == 1  → insert at 1
            # For a non-empty document: content[-1].endIndex == N → insert at N-1
            if content:
                last_end = content[-1].get("endIndex", 1)
                # endIndex 1 means the doc has only the implicit segment break at
                # position 0; we can only insert *at* index 1.
                end_index = max(1, last_end - 1)
            else:
                end_index = 1

            requests = [{"insertText": {"location": {"index": end_index}, "text": "\n" + text}}]
            self.client.post(
                f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
                json_data={"requests": requests},
            )
            return f"Successfully appended text to document {doc_id}."
        except Exception as e:
            return f"⛔ Failed to append to document: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "google_create_doc",
                "description": "Create a new Google Document and optionally insert text into it.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of the document"},
                        "initial_content": {
                            "type": "string",
                            "description": "Optional text to insert into the document",
                        },
                    },
                    "required": ["title"],
                },
            },
            self.create_doc,
        )

        registry.register(
            {
                "name": "google_read_doc",
                "description": "Read the raw text content of a Google Document. Returns at most "
                "50 000 characters; longer documents are truncated with a note. "
                "Returned content is treated as untrusted external data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "The Document ID (from the URL)",
                        }
                    },
                    "required": ["doc_id"],
                },
            },
            self.read_doc,
        )

        registry.register(
            {
                "name": "google_append_doc_text",
                "description": "Safely append new text to the bottom of an existing Google "
                "Document. Useful for maintaining a running log of meeting notes without "
                "overwriting previous content.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "The Document ID"},
                        "text": {"type": "string", "description": "The text to append"},
                    },
                    "required": ["doc_id", "text"],
                },
            },
            self.append_doc_text,
        )
