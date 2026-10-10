"""Online implementation: the hackathon's Vlada data service.

Written from the organizer guide (docs/, not tracked): Vlada is reached as an MCP server over HTTP at
https://mcp.vladahealth.com/mcp and exposes the tools find_data_sources, describe_data_source and query_substrate
(read-only SQL, at most 200 rows per call - aggregate in SQL). This client speaks MCP's JSON-RPC over HTTP directly.

NOT RUN AGAINST THE REAL SERVICE. Unverified, because the guide does not state them:
  * the tool ARGUMENT names ("query", "sql") - configurable below;
  * that a bearer token in VLADA_API_KEY is accepted (the guide describes an interactive sign-in);
  * Vlada's table and column names - so the logical-table -> SQL map (VLADA_SQL) ships empty and is filled from
    data/adapters/vlada_tables.json once someone has run describe_data_source. Until a table is mapped,
    get_table() raises VladaError and the factory's fallback serves the public extract instead.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Any, Callable

URL = "https://mcp.vladahealth.com/mcp"
ROW_CAP = 200
SQL_ARG = "sql"
QUERY_ARG = "query"
TABLES_FILE = pathlib.Path(__file__).with_name("vlada_tables.json")


class VladaError(RuntimeError):
    pass


def _http_post(url: str, payload: dict, headers: dict, timeout: float) -> tuple[int, dict, str]:
    import httpx
    r = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    return r.status_code, dict(r.headers), r.text


def _quote(v: Any) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


class Vlada:
    name = "vlada"

    def __init__(self, api_key: str | None = None, url: str | None = None, timeout: float = 30.0,
                 post: Callable[[str, dict, dict, float], tuple[int, dict, str]] = _http_post, sql_map: dict[str, str] | None = None):
        self.api_key = api_key or os.environ.get("VLADA_API_KEY", "")
        if not self.api_key:
            raise VladaError("VLADA_API_KEY is not set")
        self.url = url or os.environ.get("VLADA_MCP_URL", URL)
        self.timeout = timeout
        self._post = post
        self._id = 0
        self._session: str | None = None
        self.sql_map = dict(sql_map) if sql_map is not None else (json.loads(TABLES_FILE.read_text()) if TABLES_FILE.exists() else {})
        self.calls = 0

    # ---- MCP JSON-RPC over HTTP
    def _rpc(self, method: str, params: dict | None = None) -> Any:
        self._id += 1
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        try:
            status, rh, text = self._post(self.url, {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}, headers, self.timeout)
        except Exception as e:  # network errors of any client library
            raise VladaError(f"transport error: {e}") from e
        self.calls += 1
        if status >= 400:
            raise VladaError(f"HTTP {status}: {text[:200]}")
        sid = {k.lower(): v for k, v in rh.items()}.get("mcp-session-id")
        if sid:
            self._session = sid
        body = text.strip()
        if body.startswith("event:") or body.startswith("data:"):   # server-sent events framing
            datas = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
            body = datas[-1] if datas else "{}"
        try:
            msg = json.loads(body)
        except json.JSONDecodeError as e:
            raise VladaError(f"non-JSON response: {body[:200]}") from e
        if "error" in msg:
            raise VladaError(f"JSON-RPC error: {msg['error']}")
        return msg.get("result")

    def call_tool(self, tool: str, arguments: dict) -> Any:
        if self._session is None:
            self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hospitalgym", "version": "0.1"}})
            self._session = self._session or ""
        res = self._rpc("tools/call", {"name": tool, "arguments": arguments}) or {}
        if res.get("isError"):
            raise VladaError(f"tool {tool} failed: {json.dumps(res.get('content'))[:300]}")
        if "structuredContent" in res:
            return res["structuredContent"]
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        joined = "\n".join(texts)
        try:
            return json.loads(joined)
        except json.JSONDecodeError:
            return joined

    # ---- the three tools named in the guide
    def find_data_sources(self, query: str) -> Any:
        return self.call_tool("find_data_sources", {QUERY_ARG: query})

    def describe_data_source(self, source: str) -> Any:
        return self.call_tool("describe_data_source", {"name": source})

    def query(self, sql: str) -> list[dict]:
        out = self.call_tool("query_substrate", {SQL_ARG: sql})
        rows = out.get("rows", out.get("data", out)) if isinstance(out, dict) else out
        if not isinstance(rows, list):
            raise VladaError(f"unexpected query result shape: {str(out)[:200]}")
        return rows

    # ---- DataService interface
    def list_tables(self) -> list[str]:
        return sorted(self.sql_map)

    def get_table(self, name: str, **filters: Any) -> list[dict]:
        if name not in self.sql_map:
            raise VladaError(f"logical table '{name}' has no Vlada SQL mapping yet (add it to {TABLES_FILE.name})")
        sql = self.sql_map[name].rstrip().rstrip(";")
        if filters:
            cond = " AND ".join(f"{k} = {_quote(v)}" for k, v in filters.items() if k.replace("_", "").isalnum())
            sql = f"SELECT * FROM ({sql}) t WHERE {cond}"
        return self.query(f"{sql} LIMIT {ROW_CAP}")

    def status(self) -> dict:
        return {"service": self.name, "online": True, "url": self.url, "calls": self.calls, "mapped_tables": len(self.sql_map)}
