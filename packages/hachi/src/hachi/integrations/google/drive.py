"""
Google Drive Service Plugin
"""

import mimetypes
from pathlib import Path

from hachi.core.loop import ToolRegistry
from hachi.core.validators import validate_email
from hachi.integrations.google.service import GoogleService

# Maximum upload size: 100 MiB — uploads larger than this are rejected to prevent
# unbounded memory use during multipart buffering.
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MiB


class DriveService(GoogleService):
    @property
    def required_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/drive.file"]

    def search_drive(self, query: str, max_results: int = 5) -> str:
        """Searches Google Drive for files, following pagination up to max_results."""
        try:
            files: list = []
            page_token: str | None = None
            while len(files) < max_results:
                params: dict = {
                    "q": query,
                    "pageSize": min(max_results - len(files), 100),
                    "fields": "nextPageToken, files(id, name, mimeType, webViewLink)",
                }
                if page_token:
                    params["pageToken"] = page_token
                response = self.client.get("/drive/v3/files", params=params)
                files.extend(response.get("files", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            if not files:
                return f"No files found matching query: {query}"

            result = [f"Found {len(files)} file(s):"]
            for f in files:
                result.append(
                    f"- {f.get('name')} (ID: {f.get('id')}) [Link: {f.get('webViewLink')}]"
                )
            return "\n".join(result)
        except Exception as e:
            return f"⛔ Failed to search Drive: {str(e)}"

    def create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Creates a folder in Google Drive."""
        try:
            metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                metadata["parents"] = [parent_id]
            response = self.client.post("/drive/v3/files", json_data=metadata)
            folder_id = response.get("id")
            return f"Folder '{folder_name}' created successfully. ID: {folder_id}"
        except Exception as e:
            return f"⛔ Failed to create folder: {str(e)}"

    def upload_file(self, file_path: str, parent_id: str = None) -> str:
        """Uploads a local file to Google Drive.

        Size limit: files larger than 100 MiB are rejected to prevent unbounded
        in-memory multipart buffering. Symlinks that resolve outside the original
        path's parent directory are also rejected.
        """
        path = Path(file_path)

        if not path.exists():
            return f"⛔ File not found: {file_path}"

        # UC-DRIVE-001: reject symlinks that escape their declared location
        if path.is_symlink():
            try:
                resolved = path.resolve(strict=True)
            except OSError as e:
                return f"⛔ Cannot resolve symlink '{file_path}': {e}"
            # The symlink must stay within the same directory as the declared path
            declared_parent = path.parent.resolve()
            if not str(resolved).startswith(str(declared_parent)):
                return (
                    f"⛔ Symlink '{file_path}' points outside its declared directory "
                    f"(resolved to '{resolved}'). Upload refused for security."
                )

        # UC-DRIVE-001: enforce size cap (100 MiB)
        try:
            file_size = path.stat().st_size
        except OSError as e:
            return f"⛔ Cannot stat file '{file_path}': {e}"

        if file_size > _MAX_UPLOAD_BYTES:
            limit_mib = _MAX_UPLOAD_BYTES // (1024 * 1024)
            actual_mib = file_size / (1024 * 1024)
            return (
                f"⛔ File '{path.name}' is {actual_mib:.1f} MiB, which exceeds the "
                f"{limit_mib} MiB upload limit. Please reduce the file size or use "
                "a resumable upload approach."
            )

        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = "application/octet-stream"

        metadata = {"name": path.name}
        if parent_id:
            metadata["parents"] = [parent_id]

        try:
            # Note: We must use the /upload/drive/v3/files endpoint for multipart uploads
            response = self.client.upload_multipart(
                "/upload/drive/v3/files",
                metadata=metadata,
                file_path=file_path,
                mime_type=mime_type,
                params={"uploadType": "multipart", "fields": "id, name, webViewLink"},
            )
            file_id = response.get("id")
            link = response.get("webViewLink", "N/A")
            return f"File '{path.name}' uploaded successfully. ID: {file_id} [Link: {link}]"
        except Exception as e:
            return f"⛔ Failed to upload file: {str(e)}"

    def move_file(self, file_id: str, new_parent_id: str) -> str:
        """Moves a file to a new folder."""
        try:
            file_meta = self.client.get(f"/drive/v3/files/{file_id}", params={"fields": "parents"})
            previous_parents = ",".join(file_meta.get("parents", []))
            self.client.patch(
                f"/drive/v3/files/{file_id}",
                params={"addParents": new_parent_id, "removeParents": previous_parents},
                json_data={},
            )
            return f"File {file_id} moved to folder {new_parent_id}."
        except Exception as e:
            return f"⛔ Failed to move file: {str(e)}"

    def share_file(self, file_id: str, email: str, role: str = "writer") -> str:
        """Shares a file with a specific user.

        Requires approval before sharing. Validates the grantee email address
        before calling the Drive API.
        """
        # UC-DRIVE-002: validate email before doing anything else
        email_ok, email_value = validate_email(email)
        if not email_ok:
            return f"⛔ Invalid grantee email address: {email_value}"

        # UC-DRIVE-002: require approval before sharing externally
        ok, reason = self.require_approval(
            action="share_file",
            summary=f"Share file {file_id} with {email_value} as {role}",
            detail=(
                f"This will grant '{role}' access on Drive file '{file_id}' "
                f"to the external account '{email_value}'."
            ),
        )
        if not ok:
            return f"⛔ Action not approved: {reason}"

        try:
            permission = {"type": "user", "role": role, "emailAddress": email_value}
            self.client.post(f"/drive/v3/files/{file_id}/permissions", json_data=permission)
            return f"Successfully shared file {file_id} with {email_value} as {role}."
        except Exception as e:
            return f"⛔ Failed to share file: {str(e)}"

    def trash_file(self, file_id: str) -> str:
        """Safely moves a file to the trash instead of permanently deleting it."""
        # UC-DRIVE-003: require approval for this destructive action
        ok, reason = self.require_approval(
            action="trash_file",
            summary=f"Move file {file_id} to Drive Trash",
            detail=(
                f"File '{file_id}' will be moved to the Trash. It can be recovered within 30 days."
            ),
        )
        if not ok:
            return f"⛔ Action not approved: {reason}"

        try:
            self.client.patch(f"/drive/v3/files/{file_id}", json_data={"trashed": True})
            return (
                f"Successfully moved file {file_id} to the trash. It will be permanently "
                "deleted in 30 days."
            )
        except Exception as e:
            return f"⛔ Failed to trash file: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "google_search_drive",
                "description": "Search for files in Google Drive using standard Drive query "
                "syntax.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g., \"name contains 'budget'\")",
                        },
                        "max_results": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            self.search_drive,
        )

        registry.register(
            {
                "name": "google_create_folder",
                "description": "Create a new folder in Google Drive.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "folder_name": {"type": "string"},
                        "parent_id": {
                            "type": "string",
                            "description": "Optional ID of the parent folder",
                        },
                    },
                    "required": ["folder_name"],
                },
            },
            self.create_folder,
        )

        registry.register(
            {
                "name": "google_upload_file",
                "description": "Upload a local binary file (e.g. PDF, Image, Text) to Google "
                "Drive. Files must be 100 MiB or smaller. Symlinks that escape "
                "their declared directory are rejected.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the local file to upload",
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "Optional ID of the destination folder in Drive",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            self.upload_file,
        )

        registry.register(
            {
                "name": "google_move_file",
                "description": "Move a file into a specific folder in Google Drive.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string", "description": "ID of the file to move"},
                        "new_parent_id": {
                            "type": "string",
                            "description": "ID of the destination folder",
                        },
                    },
                    "required": ["file_id", "new_parent_id"],
                },
            },
            self.move_file,
        )

        registry.register(
            {
                "name": "google_share_file",
                "description": "Share a Google Drive file or Google Doc with a specific email "
                "address. Requires approval before sharing.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string", "description": "ID of the file to share"},
                        "email": {
                            "type": "string",
                            "description": "Email address of the user to share with",
                        },
                        "role": {
                            "type": "string",
                            "enum": ["reader", "commenter", "writer"],
                            "description": "Permission role (default: writer)",
                        },
                    },
                    "required": ["file_id", "email"],
                },
            },
            self.share_file,
        )

        registry.register(
            {
                "name": "google_trash_file",
                "description": "Safely move a file or folder to the Google Drive Trash. The item "
                "is not permanently deleted and can be recovered within 30 days. Use this instead "
                "of a hard delete to maintain user safety. Requires approval.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "ID of the file or folder to trash",
                        }
                    },
                    "required": ["file_id"],
                },
            },
            self.trash_file,
        )
