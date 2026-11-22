"""
Notion Pages Service
Handles creating, reading, and updating pages in the Notion workspace.
"""

from typing import Any

from hachi.core.loop import ToolRegistry
from hachi.integrations.notion.service import NotionService


class NotionPages(NotionService):
    def create_page(self, parent_id: str, parent_type: str, title: str, content: str) -> str:
        """
        Creates a new Notion page within a specific database or page.
        Automatically converts simple text into a Notion paragraph block to shield the LLM
        from complex JSON.
        """
        if parent_type.lower() == "page":
            parent = {"page_id": parent_id}
            properties = {"title": {"title": [{"text": {"content": title}}]}}
        else:
            parent = {"database_id": parent_id}
            properties = {"Name": {"title": [{"text": {"content": title}}]}}

        blocks = self._parse_markdown_to_blocks(content)

        payload = {"parent": parent, "properties": properties, "children": blocks}

        try:
            res = self._post("/pages", json_data=payload)
            return f"Successfully created page '{title}'. Link: {res.get('url')}"
        except Exception as e:
            return f"Failed to create Notion page: {str(e)}"

    def _parse_markdown_to_blocks(self, content: str) -> list[dict[str, Any]]:
        import re

        blocks = []
        lines = content.split("\n")

        current_paragraph = []
        in_code_block = False
        code_content = []

        def flush_paragraph():
            if not current_paragraph:
                return
            text = "\n".join(current_paragraph).strip()
            if not text:
                current_paragraph.clear()
                return

            for i in range(0, len(text), 2000):
                chunk = text[i : i + 2000]
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
                    }
                )
            current_paragraph.clear()

        for line in lines:
            stripped = line.strip()

            if in_code_block:
                if stripped.startswith("```"):
                    in_code_block = False
                    text = "\n".join(code_content)
                    for i in range(0, max(1, len(text)), 2000):
                        chunk = text[i : i + 2000]
                        blocks.append(
                            {
                                "object": "block",
                                "type": "code",
                                "code": {
                                    "language": "plain text",
                                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                                },
                            }
                        )
                    code_content.clear()
                else:
                    code_content.append(line)
                continue

            if stripped.startswith("```"):
                flush_paragraph()
                in_code_block = True
                continue

            if not stripped:
                flush_paragraph()
                continue

            if stripped == "---" or stripped == "***":
                flush_paragraph()
                blocks.append({"object": "block", "type": "divider", "divider": {}})
                continue

            if stripped.startswith("# ") and len(stripped) > 2:
                flush_paragraph()
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {
                            "rich_text": [{"type": "text", "text": {"content": stripped[2:2000]}}]
                        },
                    }
                )
                continue
            elif stripped.startswith("## ") and len(stripped) > 3:
                flush_paragraph()
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": stripped[3:2000]}}]
                        },
                    }
                )
                continue
            elif stripped.startswith("### ") and len(stripped) > 4:
                flush_paragraph()
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [{"type": "text", "text": {"content": stripped[4:2000]}}]
                        },
                    }
                )
                continue

            if stripped.startswith("- ") or stripped.startswith("* "):
                flush_paragraph()
                blocks.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": stripped[2:2000]}}]
                        },
                    }
                )
                continue

            if re.match(r"^\d+\.\s", stripped):
                flush_paragraph()
                text_content = re.sub(r"^\d+\.\s", "", stripped)
                blocks.append(
                    {
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [
                                {"type": "text", "text": {"content": text_content[:2000]}}
                            ]
                        },
                    }
                )
                continue

            if stripped.startswith("> "):
                flush_paragraph()
                blocks.append(
                    {
                        "object": "block",
                        "type": "quote",
                        "quote": {
                            "rich_text": [{"type": "text", "text": {"content": stripped[2:2000]}}]
                        },
                    }
                )
                continue

            current_paragraph.append(stripped)

        flush_paragraph()

        if in_code_block and code_content:
            text = "\n".join(code_content)
            for i in range(0, len(text), 2000):
                chunk = text[i : i + 2000]
                blocks.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "language": "plain text",
                            "rich_text": [{"type": "text", "text": {"content": chunk}}],
                        },
                    }
                )

        return blocks[:100]

    def read_page_blocks(self, page_id: str) -> str:
        """
        Reads the blocks (content) of a specific Notion page and converts it to readable text.
        Also lists child pages and databases. Follows Notion pagination.
        """
        try:
            blocks: list = []
            params: dict = {}
            while True:
                res = self._get(f"/blocks/{page_id}/children", params=params or None)
                blocks.extend(res.get("results", []))
                if not res.get("has_more"):
                    break
                params = {"start_cursor": res["next_cursor"]}

            text_content = []
            for block in blocks:
                b_type = block.get("type")

                if b_type == "child_page":
                    title = block.get("child_page", {}).get("title", "Untitled")
                    text_content.append(f"[CHILD PAGE] {title} (ID: {block['id']})")
                    continue
                elif b_type == "child_database":
                    title = block.get("child_database", {}).get("title", "Untitled")
                    text_content.append(f"[CHILD DATABASE] {title} (ID: {block['id']})")
                    continue

                if b_type and b_type in block:
                    rich_text = block[b_type].get("rich_text", [])
                    line = "".join([rt.get("plain_text", "") for rt in rich_text])
                    if line.strip():
                        text_content.append(line)

            return (
                "\n".join(text_content)
                if text_content
                else "Page is empty or contains unsupported block types."
            )
        except Exception as e:
            return f"Failed to read Notion page: {str(e)}"

    def append_to_page(self, page_id: str, content: str) -> str:
        """
        Appends markdown content to an existing Notion page.
        """
        blocks = self._parse_markdown_to_blocks(content)

        payload = {"children": blocks}

        try:
            self._patch(f"/blocks/{page_id}/children", json_data=payload)
            return f"Successfully appended content to page ID: {page_id}"
        except Exception as e:
            return f"Failed to append to Notion page: {str(e)}"

    def archive_page(self, page_id: str) -> str:
        """
        Archives (deletes) a Notion page.
        """
        payload = {"archived": True}

        try:
            self._patch(f"/pages/{page_id}", json_data=payload)
            return f"Successfully archived page ID: {page_id}"
        except Exception as e:
            return f"Failed to archive Notion page: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "notion_create_page",
                "description": "Create a new page in a Notion database or as a sub-page of "
                "another page. Use this to save notes, action items, or research.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "parent_id": {
                            "type": "string",
                            "description": "The UUID of the parent (either a page ID or "
                            "database ID).",
                        },
                        "parent_type": {
                            "type": "string",
                            "enum": ["page", "database"],
                            "description": "Specify whether the parent_id belongs to a 'page' or "
                            "a 'database'. If creating a page inside another page, use 'page'.",
                        },
                        "title": {"type": "string", "description": "The title of the page."},
                        "content": {
                            "type": "string",
                            "description": "The text content to place inside the page.",
                        },
                    },
                    "required": ["parent_id", "parent_type", "title", "content"],
                },
            },
            self.create_page,
        )

        registry.register(
            {
                "name": "notion_read_page",
                "description": "Read the text content of a specific Notion page using its ID.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "The UUID of the Notion page to read.",
                        }
                    },
                    "required": ["page_id"],
                },
            },
            self.read_page_blocks,
        )

        registry.register(
            {
                "name": "notion_append_to_page",
                "description": "Append markdown text to the bottom of an existing Notion page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "The UUID of the Notion page to update.",
                        },
                        "content": {"type": "string", "description": "The text content to append."},
                    },
                    "required": ["page_id", "content"],
                },
            },
            self.append_to_page,
        )

        registry.register(
            {
                "name": "notion_archive_page",
                "description": "Archive (delete) a Notion page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "The UUID of the Notion page to archive.",
                        }
                    },
                    "required": ["page_id"],
                },
            },
            self.archive_page,
        )
