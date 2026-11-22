"""
Integration Runtime

This module manages persistent service connections for Hachi.
It bridges the gap between .og file definitions and live API connections,
so the agent never has to re-authenticate or re-write boilerplate scripts.

Architecture:
    - `env.og` nodes provide credentials as key=value pairs.
    - `integration` nodes define the connection type, config, and tool schema.
    - Built-in handlers (SMTP, HTTP) know how to establish persistent connections.
    - Each integration registers a REAL tool in the ToolRegistry so the LLM
      calls it natively — no script writing, no curl commands.

Supported integration types:
    - smtp  : Persistent SMTP connection for email sending.
    - http  : Persistent HTTP session for REST API calls.
"""

import smtplib
import urllib.error
import urllib.request
from collections.abc import Callable
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from hachi.core.loop import ToolRegistry
from hachi.og_engine.parser import OGNode


class IntegrationRuntime:
    """
    Manages the lifecycle of all active service integrations.
    Loads credentials from env nodes, establishes persistent connections
    from integration nodes, and registers live tool handlers.
    """

    def __init__(self):
        self._env: dict[str, str] = {}  # Flat key-value credential store
        self._connections: dict[str, Any] = {}  # integration_name -> live connection object
        self._handlers: dict[str, Callable] = {}  # integration_name -> callable tool function
        self._integration_nodes: dict[str, OGNode] = {}

    # ==========================================
    # Credential Loading
    # ==========================================

    def load_env_node(self, node: OGNode):
        """
        Ingest credentials from a role=env node's ::dense block.
        Parses key=value pairs and merges them into the flat credential store.

        Args:
            node: An OGNode with role='env'. Its dense block contains KEY=VALUE pairs.
        """
        for line in node.dense.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                self._env[key.strip()] = value.strip()

    def get_credential(self, key: str) -> str | None:
        """
        Retrieve a credential by its key name.

        Args:
            key: The credential key (e.g., 'GMAIL_APP_PASSWORD').

        Returns:
            The credential value, or None if not found.
        """
        return self._env.get(key)

    # ==========================================
    # Integration Setup
    # ==========================================

    def setup_integration(self, node: OGNode) -> bool:
        """
        Read an integration node's ::config, establish a persistent connection,
        and create a callable handler function.

        Args:
            node: An OGNode with role='integration'.

        Returns:
            True if the integration was set up successfully, False otherwise.
        """
        integration_type = node.config.get("type", "").lower()
        self._integration_nodes[node.name] = node

        try:
            if integration_type == "smtp":
                return self._setup_smtp(node)
            elif integration_type == "http":
                return self._setup_http(node)
            else:
                print(
                    f"  [integration] Unknown type '{integration_type}' for {node.name}, skipping."
                )
                return False
        except Exception as e:
            print(f"  [integration] Failed to setup {node.name}: {e}")
            return False

    def register_tools(self, registry: ToolRegistry):
        """
        Register all active integration handlers as real tools in the ToolRegistry.

        Args:
            registry: The tool registry to mount tools onto.
        """
        for name, node in self._integration_nodes.items():
            if name not in self._handlers:
                continue

            # Build the tool schema from the node's ::tool block
            schema = self._build_tool_schema(node)
            if schema:
                registry.register(schema, self._handlers[name])

    def shutdown(self):
        """Gracefully close all persistent connections."""
        for _name, conn in self._connections.items():
            try:
                if hasattr(conn, "quit"):
                    conn.quit()
                elif hasattr(conn, "close"):
                    conn.close()
            except Exception:
                pass
        self._connections.clear()
        self._handlers.clear()

    # ==========================================
    # SMTP Handler
    # ==========================================

    def _setup_smtp(self, node: OGNode) -> bool:
        """
        Establish a persistent SMTP connection using config from the .og file.

        Expected ::config keys:
            type: smtp
            host: smtp.gmail.com
            port: 587
            use_tls: true
            auth_email_key: GMAIL_ADDRESS      (references a key in env.og)
            auth_password_key: GMAIL_APP_PASSWORD (references a key in env.og)
        """
        host = node.config.get("host", "smtp.gmail.com")
        port = int(node.config.get("port", "587"))
        use_tls = node.config.get("use_tls", "true").lower() == "true"

        # Resolve credentials from env store
        email_key = node.config.get("auth_email_key", "")
        password_key = node.config.get("auth_password_key", "")
        email_address = self._env.get(email_key, "")
        password = self._env.get(password_key, "")

        if not email_address or not password:
            return False

        # Establish persistent SMTP connection
        server = smtplib.SMTP(host, port, timeout=30)
        if use_tls:
            server.starttls()
        server.login(email_address, password)

        self._connections[node.name] = server

        # Create the handler closure
        def send_email(to: str, subject: str, body: str) -> str:
            """Send an email via the persistent SMTP connection."""
            try:
                for field_name, field_value in [("to", to), ("subject", subject)]:
                    if field_value and (chr(13) in field_value or chr(10) in field_value):
                        raise ValueError(
                            f"Email field {field_name!r} contains illegal newline characters"
                        )

                msg = MIMEMultipart()
                msg["From"] = email_address
                msg["To"] = to
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))

                # Reconnect if the connection dropped
                conn = self._connections.get(node.name)
                try:
                    conn.noop()
                except Exception:
                    conn = smtplib.SMTP(host, port, timeout=30)
                    if use_tls:
                        conn.starttls()
                    conn.login(email_address, password)
                    self._connections[node.name] = conn

                conn.sendmail(email_address, to, msg.as_string())
                return f"Email sent successfully to {to} with subject '{subject}'."
            except Exception as e:
                return f"Failed to send email: {str(e)}"

        self._handlers[node.name] = send_email
        print(f"  [smtp] {node.name} connected as {email_address}")
        return True

    # ==========================================
    # HTTP Handler
    # ==========================================

    def _setup_http(self, node: OGNode) -> bool:
        """
        Create a persistent HTTP session handler for REST API calls.

        Expected ::config keys:
            type: http
            base_url: https://api.example.com
            auth_header_key: API_KEY_NAME     (references a key in env.og)
            auth_header_name: Authorization   (the HTTP header to inject)
            auth_prefix: Bearer               (prefix before the key value)
        """
        base_url = node.config.get("base_url", "")
        if not base_url:
            print(f"  [http] Missing base_url for {node.name}.")
            return False

        # Resolve auth
        auth_key = node.config.get("auth_header_key", "")
        auth_header_name = node.config.get("auth_header_name", "Authorization")
        auth_prefix = node.config.get("auth_prefix", "Bearer")
        api_key = self._env.get(auth_key, "") if auth_key else ""

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers[auth_header_name] = f"{auth_prefix} {api_key}".strip()

        self._connections[node.name] = {"base_url": base_url, "headers": headers}

        # Create the handler closure
        def http_request(method: str, path: str, body: str = "") -> str:
            """Make an HTTP request to the configured API."""
            try:
                ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
                if method.upper() not in ALLOWED_METHODS:
                    raise ValueError(f"HTTP method is not allowed: {method!r}")
                method = method.upper()

                path = path.lstrip("/")
                if "\\" in path:
                    raise ValueError(f"Invalid request path: {path!r}")
                for component in path.split("/"):
                    if component in (".", ".."):
                        raise ValueError(f"Invalid request path: {path!r}")

                url = f"{base_url.rstrip('/')}/{path}"
                data = body.encode("utf-8") if body else None

                req = urllib.request.Request(url, data=data, headers=headers, method=method)

                with urllib.request.urlopen(req, timeout=30) as resp:
                    response_body = resp.read().decode("utf-8")
                    return f"Status: {resp.status}\n{response_body[:2000]}"
            except urllib.error.HTTPError as e:
                return f"HTTP Error {e.code}: {e.read().decode('utf-8')[:500]}"
            except Exception as e:
                return f"Request failed: {str(e)}"

        self._handlers[node.name] = http_request
        print(f"  [http] {node.name} connected to {base_url}")
        return True

    # ==========================================
    # Schema Builder
    # ==========================================

    def _build_tool_schema(self, node: OGNode) -> dict[str, Any] | None:
        """
        Build an Anthropic-compatible tool JSON schema from the node's ::tool block.

        Expected ::tool keys:
            name: send_email
            description: Send an email via Gmail
            params: to|recipient email, subject|email subject, body|email body
        """
        tool_name = node.tool_def.get("name", "")
        tool_desc = node.tool_def.get("description", "")

        if not tool_name:
            return None

        # Parse params: "to|recipient email, subject|email subject, body|email body"
        params_raw = node.tool_def.get("params", "")
        properties: dict[str, Any] = {}
        required: list[str] = []

        if params_raw:
            for param in params_raw.split(","):
                param = param.strip()
                if "|" in param:
                    param_name, param_desc = param.split("|", 1)
                else:
                    param_name = param
                    param_desc = param

                properties[param_name.strip()] = {
                    "type": "string",
                    "description": param_desc.strip(),
                }
                required.append(param_name.strip())

        return {
            "name": tool_name,
            "description": tool_desc,
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }
