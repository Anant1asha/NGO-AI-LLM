"""Google Meet Integration — meeting monitor with managed lifecycle.

UC-MEET-001 fixes applied here:
- No ``print()`` calls anywhere; logging goes through the standard ``logging`` module
  and structured events so the TUI / gateway can surface them without polluting stdout.
- The background poller runs as a ``Job`` inside the process-wide ``InMemoryJobQueue``
  rather than a fire-and-forget daemon thread.  The tool returns the job-id so callers
  can query status.  A named ``threading.Thread`` is still used to execute the job
  because ``JobWorker.execute_one()`` is not async-aware and the poll loop is inherently
  long-running, but the thread is now tracked via the queue and its completion /
  timeout is recorded as a ``JobResult``.
- The 30-minute start timeout is explicit: when it expires the job fails with a clear
  message that names the duration, rather than silently returning ``None``.
- Errors inside the poll loop are caught and re-raised / recorded rather than swallowed.
- The docstring for the registered tool prominently states that the user MUST manually
  enable transcription in the Meet UI before any transcript will be captured.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid

import httpx

from hachi.core.loop import ToolRegistry
from hachi.integrations.google.service import GoogleService
from hachi.jobs.queue import InMemoryJobQueue, Job, JobWorker

logger = logging.getLogger(__name__)

# How long (seconds) to wait for the meeting to start before giving up.
_START_TIMEOUT_SECONDS = 30 * 60  # 30 minutes
# How long (seconds) to wait for Google to process the transcript after the meeting ends.
_TRANSCRIPT_TIMEOUT_SECONDS = 5 * 60  # 5 minutes
# Interval between poll requests.
_POLL_INTERVAL_SECONDS = 30


def _poll_for_transcript(space_id: str, headers: dict) -> str:
    """Background job: poll Google Meet APIs until the transcript is available.

    This function runs inside a ``Job`` so its return value and any exception are
    captured as a ``JobResult`` — no output reaches stdout.

    Args:
        space_id: The Meet space identifier (e.g. "abc-defg-hij").
        headers: Authenticated HTTP headers from the Google client.

    Returns:
        A status string describing the outcome (stored in ``JobResult.output``).

    Raises:
        RuntimeError: On timeout or when an unrecoverable API error occurs.
    """
    logger.info("[MeetMonitor] Hooked into space %s. Waiting for meeting to begin.", space_id)

    conference_record_name: str | None = None
    deadline = time.monotonic() + _START_TIMEOUT_SECONDS
    attempts = 0

    # --- Phase 1: wait for the meeting to start ---
    while conference_record_name is None:
        if time.monotonic() > deadline:
            timeout_minutes = _START_TIMEOUT_SECONDS // 60
            msg = (
                f"Timeout: meeting {space_id} did not start within {timeout_minutes} minutes. "
                "Monitor has been stopped."
            )
            logger.warning("[MeetMonitor] %s", msg)
            raise RuntimeError(msg)

        try:
            res = httpx.get(
                f"https://meet.googleapis.com/v2/spaces/{space_id}/conferenceRecords",
                headers=headers,
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("conferenceRecords"):
                conference_record_name = data["conferenceRecords"][0]["name"]
                logger.info("[MeetMonitor] Meeting started; tracking %s.", conference_record_name)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "[MeetMonitor] HTTP %s while waiting for conference record: %s",
                exc.response.status_code,
                exc,
            )
        except Exception as exc:
            logger.warning("[MeetMonitor] Error while polling for conference record: %s", exc)

        if conference_record_name is None:
            attempts += 1
            time.sleep(_POLL_INTERVAL_SECONDS)

    # --- Phase 2: wait for the meeting to end ---
    logger.info("[MeetMonitor] Monitoring active meeting %s.", conference_record_name)
    while True:
        try:
            res = httpx.get(
                f"https://meet.googleapis.com/v2/{conference_record_name}",
                headers=headers,
                timeout=30,
            )
            res.raise_for_status()
            record_data = res.json()
            if "endTime" in record_data:
                logger.info("[MeetMonitor] Meeting %s has ended.", conference_record_name)
                break
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"API error while monitoring meeting {conference_record_name}: "
                f"HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Unexpected error while monitoring meeting {conference_record_name}: {exc}"
            ) from exc
        time.sleep(_POLL_INTERVAL_SECONDS)

    # --- Phase 3: fetch the transcript ---
    logger.info("[MeetMonitor] Searching for transcript for %s.", conference_record_name)
    transcript_text: str | None = None
    transcript_deadline = time.monotonic() + _TRANSCRIPT_TIMEOUT_SECONDS
    while time.monotonic() < transcript_deadline:
        try:
            res = httpx.get(
                f"https://meet.googleapis.com/v2/{conference_record_name}/transcripts",
                headers=headers,
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("transcripts"):
                transcript_name = data["transcripts"][0]["name"]
                entries_res = httpx.get(
                    f"https://meet.googleapis.com/v2/{transcript_name}/entries",
                    headers=headers,
                    timeout=30,
                )
                entries_res.raise_for_status()
                entries_data = entries_res.json()
                lines = [entry.get("text", "") for entry in entries_data.get("entries", [])]
                transcript_text = "\n".join(lines)
                break
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "[MeetMonitor] HTTP %s while fetching transcript: %s",
                exc.response.status_code,
                exc,
            )
        except Exception as exc:
            logger.warning("[MeetMonitor] Error while fetching transcript: %s", exc)
        time.sleep(_POLL_INTERVAL_SECONDS)

    if not transcript_text:
        timeout_minutes = _TRANSCRIPT_TIMEOUT_SECONDS // 60
        raise RuntimeError(
            f"Meeting {space_id} ended but no transcript was available within "
            f"{timeout_minutes} minutes. "
            "If you did not click 'Activities > Transcripts > Start Transcription' "
            "inside the Meet UI before the meeting ended, the transcript will never appear."
        )

    # --- Phase 4: persist to Memory Vault ---
    from hachi.core.memory_vault import MemoryVault

    vault = MemoryVault()
    vault.upsert_fact(f"Transcript for meeting {space_id}:\n{transcript_text}", "workspace_state")
    logger.info("[MeetMonitor] Transcript for %s saved to Memory Vault.", space_id)
    return f"Transcript for meeting {space_id} captured and saved to Memory Vault."


class MeetService(GoogleService):
    """
    Google Meet Agent (Native API Tier)
    Uses Google Workspace's native transcription API to process meeting notes.
    """

    @property
    def required_scopes(self) -> list[str]:
        # Required to read meeting artifacts
        return ["https://www.googleapis.com/auth/meetings.space.readonly"]

    def __init__(self, client):
        super().__init__(client)

    def register_tools(self, registry: ToolRegistry) -> None:
        def google_monitor_meeting(meet_link: str) -> str:
            """Start a background monitor for a Google Meet session.

            IMPORTANT — MANUAL TRANSCRIPTION REQUIRED:
            You MUST manually click 'Activities > Transcripts > Start Transcription'
            inside the Google Meet UI *before or during* the call.  If you skip this
            step, Google will not generate a transcript and the monitor will report
            an error when the meeting ends.

            The monitor runs as a tracked background job.  Its status (including any
            timeout or error) is recorded in the job queue and logged; no output is
            written to stdout.

            Requires a paid Google Workspace tier (Business Standard or higher) for
            the Meet REST API to be available.

            Args:
                meet_link: Full Google Meet URL
                           (e.g. https://meet.google.com/abc-defg-hij).

            Returns:
                A message with the job ID that tracks the background monitor, or an
                error string if the initial API probe fails.
            """
            # Extract space_id (e.g. abc-defg-hij)
            space_id = meet_link.split("/")[-1].split("?")[0]

            try:
                # Probe the Workspace Native API to validate the link and auth
                headers = self.client._get_headers()
                probe_url = f"https://meet.googleapis.com/v2/spaces/{space_id}"

                response = httpx.get(probe_url, headers=headers, timeout=15)
                response.raise_for_status()

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    return (
                        "ERROR: Google Meet API access denied. Native meeting transcription "
                        "requires a paid Google Workspace tier (Business Standard or higher)."
                    )
                return (
                    f"ERROR: Google Meet API responded with HTTP {e.response.status_code}. "
                    "Verify the Meet link is valid and the account has API access."
                )
            except Exception as e:
                return f"Failed to reach Google Meet API: {e}"

            # Snapshot headers for use in the background job (the OAuth token is
            # already resolved; the dict is safe to close over).
            captured_headers = dict(headers)
            job_id = uuid.uuid4().hex

            def _run_job() -> str:
                return _poll_for_transcript(space_id=space_id, headers=captured_headers)

            queue = InMemoryJobQueue()
            job = Job(
                job_id=job_id,
                name=f"meet_transcript:{space_id}",
                func=_run_job,
                job_type="background",
            )
            queue.enqueue(job)

            def _on_job_event(event_name: str, payload: dict) -> None:
                logger.debug("[MeetMonitor] job event %s: %s", event_name, payload)
                if event_name == "job.failed":
                    logger.error(
                        "[MeetMonitor] Background job for meeting %s failed: %s",
                        space_id,
                        payload.get("error"),
                    )
                elif event_name == "job.completed":
                    logger.info(
                        "[MeetMonitor] Background job for meeting %s completed in %.1fs.",
                        space_id,
                        payload.get("duration_seconds", 0),
                    )

            worker = JobWorker(queue, on_job_event=_on_job_event)

            def _thread_target() -> None:
                try:
                    worker.execute_one()
                except Exception:
                    logger.exception(
                        "[MeetMonitor] Unhandled exception in monitor thread for %s", space_id
                    )

            thread = threading.Thread(
                target=_thread_target,
                daemon=True,
                name=f"meet:{space_id}",
            )
            thread.start()

            timeout_minutes = _START_TIMEOUT_SECONDS // 60
            return (
                f"Meeting monitor started for space '{space_id}' (job_id={job_id}). "
                f"It will wait up to {timeout_minutes} minutes for the meeting to begin. "
                "IMPORTANT: You must manually click 'Activities > Transcripts > "
                "Start Transcription' inside Google Meet before the meeting ends — "
                "otherwise no transcript will be captured. "
                "Monitor status and any errors are written to the application log."
            )

        registry.register(
            {
                "name": "google_monitor_meeting",
                "description": (
                    "Monitor an ongoing or upcoming Google Meet session and capture the "
                    "meeting transcript when it ends. "
                    "IMPORTANT: The user must manually enable transcription inside Google Meet "
                    "('Activities > Transcripts > Start Transcription') or no notes will be "
                    "generated. Requires a paid Google Workspace tier."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "meet_link": {
                            "type": "string",
                            "description": (
                                "The full Google Meet URL "
                                "(e.g., https://meet.google.com/abc-defg-hij)"
                            ),
                        }
                    },
                    "required": ["meet_link"],
                },
            },
            google_monitor_meeting,
        )
