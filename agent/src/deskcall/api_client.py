"""Klien HTTP ke deskcall-api (docs/API.md): laporan event dan hasil panggilan. Stdlib-only."""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .models import CallResult

log = logging.getLogger(__name__)


class ApiError(Exception):
    pass


class DeskcallApi:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        request = urllib.request.Request(
            self._base + path, data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"X-API-Key": self._key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise ApiError("POST %s -> HTTP %d" % (path, exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ApiError("POST %s failed: %s" % (path, type(exc).__name__)) from exc

    def post_event(self, call_id: str, event_type: str, detail: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"type": event_type}
        if detail:
            body["detail"] = detail
        return self._post("/api/v1/calls/%s/events" % call_id, body)

    def post_result(self, call_id: str, result: CallResult) -> Dict[str, Any]:
        if result.tag is None:
            raise ApiError("result has no tag")
        body: Dict[str, Any] = {
            "tag": result.tag.value,
            "verified": result.verified,
            "transcript": [{"speaker": t.speaker, "text": t.text[:4000], "state": t.state} for t in result.transcript],
            "statesVisited": result.states_visited,
        }
        if result.ptp_date:
            body["ptpDate"] = result.ptp_date.isoformat()
        if result.note:
            body["note"] = result.note
        return self._post("/api/v1/calls/%s/result" % call_id, body)

    async def apost_event(self, call_id: str, event_type: str, detail: Optional[str] = None) -> None:
        try:
            await asyncio.to_thread(self.post_event, call_id, event_type, detail)
        except ApiError as exc:  # laporan event tidak boleh mematikan percakapan
            log.warning("event %s not reported: %s", event_type, exc)

    async def apost_result(self, call_id: str, result: CallResult) -> None:
        await asyncio.to_thread(self.post_result, call_id, result)
