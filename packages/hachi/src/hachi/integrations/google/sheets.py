"""
Google Sheets Service Plugin
"""

from hachi.core.loop import ToolRegistry
from hachi.core.validators import validate_a1_range
from hachi.integrations.google.service import GoogleService

# Maximum number of rows returned by read_sheet before truncation.
# A single unbounded read of a 100k-row sheet would exhaust the context window.
_READ_SHEET_MAX_ROWS = 1_000


class SheetsService(GoogleService):
    @property
    def required_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/spreadsheets"]

    def append_sheet_row(self, spreadsheet_id: str, range_name: str, values: list[str]) -> str:
        """Appends a row of data to a spreadsheet."""
        # UC-SHEET-001: validate range syntax
        rng_ok, rng_value = validate_a1_range(range_name)
        if not rng_ok:
            return f"⛔ Invalid range '{range_name}': {rng_value}"

        body = {"values": [values]}
        try:
            response = self.client.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
                f"/values/{rng_value}:append",
                params={"valueInputOption": "USER_ENTERED"},
                json_data=body,
            )
            updated_cells = response.get("updates", {}).get("updatedCells", 0)
            return f"Successfully appended row to {spreadsheet_id}. {updated_cells} cells updated."
        except Exception as e:
            return f"⛔ Failed to append row: {str(e)}"

    def create_sheet(self, title: str) -> str:
        """Creates a new Google Spreadsheet."""
        try:
            response = self.client.post(
                "https://sheets.googleapis.com/v4/spreadsheets",
                json_data={"properties": {"title": title}},
            )
            sheet_id = response.get("spreadsheetId")
            return (
                f"Spreadsheet '{title}' created successfully. ID: {sheet_id} "
                f"[Link: https://docs.google.com/spreadsheets/d/{sheet_id}]"
            )
        except Exception as e:
            return f"⛔ Failed to create spreadsheet: {str(e)}"

    def read_sheet(self, spreadsheet_id: str, range_name: str) -> str:
        """Reads data from a Google Spreadsheet.

        UC-SHEET-001: The range is validated against A1 notation before the API
        call. Results are capped at 1 000 rows; when the response is truncated a
        note is appended so the caller knows to narrow the range.

        Note: formulas are *not* evaluated by this method — the Sheets API returns
        the display value (the rendered cell content) rather than the formula text,
        unless the sheet is configured to return formulas. If you need the
        underlying formula, use a dedicated formula-extraction approach.
        """
        # UC-SHEET-001: validate range before hitting the API
        rng_ok, rng_value = validate_a1_range(range_name)
        if not rng_ok:
            return f"⛔ Invalid range '{range_name}': {rng_value}"

        try:
            response = self.client.get(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{rng_value}"
            )
            values = response.get("values", [])
            if not values:
                return "No data found in the specified range."

            # UC-SHEET-001: cap large reads
            truncated = len(values) > _READ_SHEET_MAX_ROWS
            if truncated:
                values = values[:_READ_SHEET_MAX_ROWS]

            # Format as CSV for the LLM to read easily
            rows = []
            for row in values:
                rows.append(", ".join([str(cell) for cell in row]))

            result = "\n".join(rows)
            if truncated:
                result += (
                    f"\n\n[NOTE: Result truncated at {_READ_SHEET_MAX_ROWS} rows. "
                    "Narrow the range (e.g. 'Sheet1!A1:D100') to read a specific section.]"
                )
            return result
        except Exception as e:
            return f"⛔ Failed to read spreadsheet: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "google_append_sheet_row",
                "description": "Append a row of data to a Google Spreadsheet. You must provide "
                "the exact spreadsheet_id. The range_name must be valid A1 notation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "spreadsheet_id": {
                            "type": "string",
                            "description": "The ID of the spreadsheet",
                        },
                        "range_name": {
                            "type": "string",
                            "description": "The range or sheet name (e.g., 'Sheet1' or 'A1:D1')",
                        },
                        "values": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of string values to append as a row",
                        },
                    },
                    "required": ["spreadsheet_id", "range_name", "values"],
                },
            },
            self.append_sheet_row,
        )

        registry.register(
            {
                "name": "google_create_sheet",
                "description": "Create a new blank Google Spreadsheet.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of the new spreadsheet"}
                    },
                    "required": ["title"],
                },
            },
            self.create_sheet,
        )

        registry.register(
            {
                "name": "google_read_sheet",
                "description": "Read data from a Google Spreadsheet. Data is returned in CSV "
                "format. Results are capped at 1 000 rows; narrow the range for large sheets. "
                "The range must be valid A1 notation (e.g. 'Sheet1!A1:D10').",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "spreadsheet_id": {
                            "type": "string",
                            "description": "The ID of the spreadsheet",
                        },
                        "range_name": {
                            "type": "string",
                            "description": "The range or sheet name to read (e.g., 'Sheet1' or "
                            "'Sheet1!A1:D10')",
                        },
                    },
                    "required": ["spreadsheet_id", "range_name"],
                },
            },
            self.read_sheet,
        )
