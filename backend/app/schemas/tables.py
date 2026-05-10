"""Pydantic schemas for InfoTable and InfoTableRow resources."""

import json
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import ScriptScope

# Suppress Pydantic's warning that 'schema_json' shadows the deprecated Pydantic v1
# classmethod of the same name. We're on Pydantic v2 where that method no longer
# exists, and 'schema_json' is the actual DB column name we need to map.
warnings.filterwarnings(
    "ignore",
    message="Field name \"schema_json\" in .* shadows an attribute in parent",
    category=UserWarning,
)


class InfoTableCreate(BaseModel):
    scope: ScriptScope
    account_id: Optional[str] = Field(None, description="Required when scope is 'account'")
    name: str = Field(..., min_length=1, max_length=255)
    schema_json: str = Field(..., description="JSON string defining the table's column schema")

    @field_validator("schema_json")
    @classmethod
    def validate_schema_json(cls, value: str) -> str:
        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"schema_json must be valid JSON: {exc}") from exc
        return value

    @model_validator(mode="after")
    def validate_scope_account_id(self) -> "InfoTableCreate":
        if self.scope == ScriptScope.ACCOUNT and not self.account_id:
            raise ValueError("account_id is required when scope is 'account'")
        if self.scope == ScriptScope.GLOBAL and self.account_id:
            raise ValueError("account_id must be None when scope is 'global'")
        return self


class InfoTableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: ScriptScope
    account_id: Optional[str]
    name: str
    schema_json: str
    created_at: datetime


class InfoTableRowCreate(BaseModel):
    row_data: Dict[str, Any] = Field(..., description="Arbitrary key-value row data")


class InfoTableRowUpdate(BaseModel):
    row_data: Dict[str, Any]


class InfoTableRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    table_id: str
    row_data_json: str
    created_at: datetime
    updated_at: datetime
