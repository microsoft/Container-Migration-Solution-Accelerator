# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from steps.convert.orchestration.yaml_convert_orchestrator import (
    _parse_conversion_report_quality_gates,
)


def test_parse_signoffs_and_open_blockers_detects_open_and_fail():
    md = """
# YAML Conversion Report

## Blockers (Open must be empty to finish)
- id: B1
  status: Open

## Sign-off
**YAML Expert:** SIGN-OFF: FAIL
**QA Engineer:** SIGN-OFF: PASS
**AKS Expert:** SIGN-OFF: PASS
**Azure Architect:** SIGN-OFF: PASS
**Chief Architect:** SIGN-OFF: PASS
"""

    signoffs, has_open = _parse_conversion_report_quality_gates(md)
    assert has_open is True
    assert signoffs["YAML Expert"] == "FAIL"
    assert signoffs["QA Engineer"] == "PASS"


def test_parse_signoffs_and_open_blockers_no_open_all_pass():
    md = """
# YAML Conversion Report

## Blockers (Open must be empty to finish)
None

## Sign-off
**YAML Expert:** SIGN-OFF: PASS
**QA Engineer:** SIGN-OFF: PASS
**AKS Expert:** SIGN-OFF: PASS
**Azure Architect:** SIGN-OFF: PASS
**Chief Architect:** SIGN-OFF: PASS
"""

    signoffs, has_open = _parse_conversion_report_quality_gates(md)
    assert has_open is False
    assert set(signoffs.keys()) == {
        "YAML Expert",
        "QA Engineer",
        "AKS Expert",
        "Azure Architect",
        "Chief Architect",
    }

