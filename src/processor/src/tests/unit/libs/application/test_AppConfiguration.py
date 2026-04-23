# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from libs.application.application_configuration import Configuration


def test_configuration_defaults():
    cfg = Configuration()
    assert cfg.app_logging_enable is False
    assert cfg.storage_queue_name == "processes-queue"
