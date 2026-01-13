# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pydantic import BaseModel, Field

class Analysis_TaskParam(BaseModel):
    process_id: str = Field(description="Unique identifier for the analysis process")
    container_name: str = Field(description="Name of the container holding process files")
    source_file_folder: str = Field(description="Path to the source files folder")
    output_file_folder: str = Field(description="Path to the output files folder")
    workspace_file_folder: str = Field(description="Path to the workspace files folder")
