"""
Pydantic schemas for Variable resources.

Security note: VariableResponse never exposes value_encrypted. The `value`
field is always the decrypted plaintext — masked as "***" for secrets unless
the caller explicitly requests it via the /reveal endpoint.

The model_validator on VariableResponse handles ORM-to-schema conversion:
when a Variable ORM object is passed, it reads value_encrypted and decrypts it
(masking secrets). When a plain dict is passed, it is used directly.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import ScriptScope


class VariableCreate(BaseModel):
    scope: ScriptScope
    account_id: Optional[str] = Field(None, description="Required when scope is 'account'")
    name: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., description="Plaintext value — encrypted before storage")
    is_secret: bool = Field(False, description="If True, value is masked in responses")
    variable_type: str = Field("config", description="'config' or 'api_key'")

    @model_validator(mode="after")
    def validate_scope_account_id(self) -> "VariableCreate":
        if self.scope == ScriptScope.ACCOUNT and not self.account_id:
            raise ValueError("account_id is required when scope is 'account'")
        if self.scope == ScriptScope.GLOBAL and self.account_id:
            raise ValueError("account_id must be None when scope is 'global'")
        return self


class VariableUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    value: Optional[str] = None
    is_secret: Optional[bool] = None
    variable_type: Optional[str] = None


class VariableResponse(BaseModel):
    """
    Never includes value_encrypted.

    When constructed from an ORM Variable object, the model_validator
    decrypts value_encrypted and masks it if is_secret is True.
    When constructed from a dict (e.g. from the /value endpoint with reveal=True),
    the dict is used as-is.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: ScriptScope
    account_id: Optional[str]
    name: str
    value: str = Field(description="Decrypted value, or '***' if secret/api_key and not revealed")
    is_secret: bool
    variable_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def decrypt_value(cls, data: Any) -> Any:
        """
        If given an ORM Variable object, decrypt value_encrypted.
        If given a dict (already has 'value'), pass through unchanged.
        """
        if hasattr(data, "value_encrypted"):
            # ORM object — decrypt and mask secrets
            from app.services.encryption_service import get_variable_value
            vtype = getattr(data, "variable_type", "config") or "config"
            is_masked = data.is_secret or vtype == "api_key"
            return {
                "id": data.id,
                "scope": data.scope,
                "account_id": data.account_id,
                "name": data.name,
                "value": get_variable_value(data, reveal_secret=False) if not is_masked else "***",
                "is_secret": data.is_secret,
                "variable_type": vtype,
                "created_at": data.created_at,
                "updated_at": getattr(data, "updated_at", None),
            }
        return data


class VariableValueResponse(BaseModel):
    """Response for the /value endpoint, which can optionally reveal secrets."""

    id: str
    name: str
    value: str
    is_secret: bool
