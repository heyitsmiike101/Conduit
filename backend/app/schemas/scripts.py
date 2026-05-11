"""Pydantic schemas for Script resources."""

import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.db.models import ScriptScope


def _to_python_name(name: str) -> str:
    """Convert a free-form name into a valid Python identifier for import."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_').lower()
    # Ensure it doesn't start with a digit
    if slug and slug[0].isdigit():
        slug = 'tool_' + slug
    return slug or 'tool'


class ScriptCreate(BaseModel):
    scope: ScriptScope
    account_id: Optional[str] = Field(None, description="Required when scope is 'account'")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    enabled: bool = True
    timeout_seconds: Optional[int] = Field(None, gt=0, description="Max run time in seconds")
    script_type: Literal["script", "tool"] = "script"

    @model_validator(mode="after")
    def validate_scope_account_id(self) -> "ScriptCreate":
        if self.scope == ScriptScope.ACCOUNT and not self.account_id:
            raise ValueError("account_id is required when scope is 'account'")
        if self.scope == ScriptScope.GLOBAL and self.account_id:
            raise ValueError("account_id must be None when scope is 'global'")
        return self


class ScriptUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, gt=0)


class ScriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: ScriptScope
    account_id: Optional[str]
    name: str
    file_path: str
    description: Optional[str]
    enabled: bool
    timeout_seconds: Optional[int]
    selected_variable_ids: Optional[str] = None
    script_type: str = "script"
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def python_name(self) -> str:
        """Valid Python identifier for importing this tool."""
        return _to_python_name(self.name)


class ScriptContentResponse(BaseModel):
    """Response for GET /scripts/{id}/content — includes file text."""
    script_id: str
    file_path: str
    content: str


class ScriptContentUpdate(BaseModel):
    """Body for PUT /scripts/{id}/content."""
    content: str
    label: Optional[str] = Field(None, description="Optional label for this version snapshot")


class ScriptVersionResponse(BaseModel):
    """A single historical version of a script."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    script_id: str
    version_number: int
    label: Optional[str]
    file_path: Optional[str] = None
    created_at: datetime
    # code is intentionally omitted from list — only returned by revert/detail endpoints


class ScriptVersionDetailResponse(ScriptVersionResponse):
    """Full version including the code — returned by revert and individual fetch."""
    code: str


class ScriptVariablesUpdate(BaseModel):
    """Body for PUT /scripts/{id}/variables — set which variables are injected."""
    selected_variable_ids: Optional[List[str]] = Field(
        None,
        description="List of variable IDs to inject. None/null means inject all."
    )


class ScriptConfigResponse(BaseModel):
    """
    All variables accessible to this script, with a 'selected' flag.
    selected=True means the variable will be injected at runtime.
    If selected_variable_ids is null on the script, all vars are selected.
    """
    selected_variable_ids: Optional[List[str]]
    global_vars: List[dict]
    account_vars: List[dict]
