# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pydantic import BaseModel, Field


class CoordinatorSelectionResponse(BaseModel):
    selected_participant: str | None = Field(default=None)
    instruction: str | None = Field(default=None)
    finish: bool = Field(default=False)
    final_message: str | None = Field(default=None)
