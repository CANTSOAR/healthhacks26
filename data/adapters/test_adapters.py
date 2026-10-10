"""Run: .venv/bin/python -m pytest data/adapters -q      (no network; the Vlada client is exercised against faked responses)"""
import json

import pytest

from data.adapters import PublicExtracts, Vlada, VladaError, get_data_service
from data.adapters.base import TableNotFound


def test_public_extracts_reads_csv_and_json_with_filters():
    svc = PublicExtracts()
    assert "nhamcs_ed_by_acuity" in svc.list_tables()
    rows = svc.get_table("nhamcs_ed_by_acuity", subset="metro_teaching", acuity="3")
    assert len(rows) == 1 and 0 < rows[0]["p_admit"] < 1
    one = svc.get_table("care_compare_ed_rwjuh")
    assert one[0]["facility"]["Facility ID"] == "310038"
    with pytest.raises(TableNotFound):
        svc.get_table("no_such_table")
    assert svc.status()["online"] is False


def test_selection_is_by_key_presence_only():
    assert isinstance(get_data_service(env={}), PublicExtracts)
    assert get_data_service(env={"VLADA_API_KEY": "k"}, post=lambda *a: (500, {}, "")).name == "vlada"


class FakeVlada:
    def __init__(self, rows, sse=False, fail=False):
        self.rows, self.sse, self.fail, self.seen = rows, sse, fail, []

    def __call__(self, url, payload, headers, timeout):
        self.seen.append((url, payload, headers))
        if self.fail:
            return 503, {}, "Busy"
        if payload["method"] == "initialize":
            return 200, {"Mcp-Session-Id": "s1"}, json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": {"protocolVersion": "2025-03-26"}})
        result = {"content": [{"type": "text", "text": json.dumps({"rows": self.rows})}]}
        body = json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result})
        return 200, {}, (f"event: message\ndata: {body}\n\n" if self.sse else body)


@pytest.mark.parametrize("sse", [False, True])
def test_vlada_client_against_faked_response(sse):
    fake = FakeVlada([{"facility_id": "310038", "op_18b": 206}], sse=sse)
    v = Vlada(api_key="secret", post=fake, sql_map={"care_compare_ed": "SELECT facility_id, op_18b FROM some_source"})
    rows = v.get_table("care_compare_ed", facility_id="310038")
    assert rows == [{"facility_id": "310038", "op_18b": 206}]
    url, payload, headers = fake.seen[-1]
    assert url == "https://mcp.vladahealth.com/mcp" and headers["Authorization"] == "Bearer secret" and headers["Mcp-Session-Id"] == "s1"
    assert payload["method"] == "tools/call" and payload["params"]["name"] == "query_substrate"
    sql = payload["params"]["arguments"]["sql"]
    assert "facility_id = '310038'" in sql and sql.endswith("LIMIT 200")
    assert fake.seen[0][1]["method"] == "initialize"


def test_vlada_errors_and_fallback_to_public_extracts():
    with pytest.raises(VladaError):
        Vlada(api_key="")
    v = Vlada(api_key="k", post=FakeVlada([]), sql_map={})
    with pytest.raises(VladaError):
        v.get_table("unmapped")
    svc = get_data_service(env={"VLADA_API_KEY": "k"}, post=FakeVlada([], fail=True), sql_map={"nhamcs_ed_by_acuity": "SELECT 1"})
    rows = svc.get_table("nhamcs_ed_by_acuity", subset="all_hospitals", acuity="2")   # service 'Busy' -> offline extract
    assert len(rows) == 1 and svc.status()["fallback_calls"] == 1 and "503" in svc.status()["last_fallback"]["reason"]
