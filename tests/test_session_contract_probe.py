import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.session_contract_probe import probe_events


def test_probe_events_reports_missing_trace():
    report = probe_events([{"session_id": "s"}, {"trace_id": "t"}])
    assert report["healthy"] is False
    assert report["missing_trace_indexes"] == [0]
    assert report["missing_session_indexes"] == [1]
