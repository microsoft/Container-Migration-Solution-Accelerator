# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from steps.analysis.models.step_output import Analysis_BooleanExtendedResult
from steps.analysis.models.step_param import Analysis_TaskParam
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.design.models.step_output import Design_ExtendedBooleanResult
from steps.documentation.models.step_output import GeneratedFile


def test_analysis_task_param_requires_fields():
    with pytest.raises(ValidationError):
        Analysis_TaskParam()  # type: ignore[call-arg]

    task = Analysis_TaskParam(
        process_id="p1",
        container_name="c1",
        source_file_folder="p1/source",
        workspace_file_folder="p1/workspace",
        output_file_folder="p1/converted",
    )
    assert task.process_id == "p1"
    assert task.container_name == "c1"


def test_analysis_boolean_extended_result_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Analysis_BooleanExtendedResult(unknown_field=True)  # type: ignore[call-arg]


def test_extended_boolean_results_forbid_extra_fields():
    with pytest.raises(ValidationError):
        Yaml_ExtendedBooleanResult(extra=123)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        Design_ExtendedBooleanResult(extra=123)  # type: ignore[call-arg]


def test_default_lists_are_not_shared_between_instances():
    r1 = Analysis_BooleanExtendedResult()
    r2 = Analysis_BooleanExtendedResult()

    r1.blocking_issues.append("x")
    assert r2.blocking_issues == []


def test_documentation_generated_file_forbids_extra_fields():
    with pytest.raises(ValidationError):
        GeneratedFile(
            file_name="a.md",
            file_type="doc",
            content_summary="summary",
            unexpected="nope",
        )
