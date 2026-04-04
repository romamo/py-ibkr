from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias

from pydantic import RootModel
from pydantic_extra_types.currency_code import Currency as CurrencyVO

if TYPE_CHECKING:
    AccountIDInput: TypeAlias = "AccountID" | str
    CurrencyCodeInput: TypeAlias = "CurrencyCode" | CurrencyVO | str
    SymbolInput: TypeAlias = "Symbol" | str
    ConIDInput: TypeAlias = "ConID" | str
    FlexTokenInput: TypeAlias = "FlexToken" | str
    FlexQueryIDInput: TypeAlias = "FlexQueryID" | str
    ReferenceCodeInput: TypeAlias = "ReferenceCode" | str
else:
    AccountIDInput = Any
    CurrencyCodeInput = Any
    SymbolInput = Any
    ConIDInput = Any
    FlexTokenInput = Any
    FlexQueryIDInput = Any
    ReferenceCodeInput = Any


class _StrVO(RootModel[str]):
    """Base for string-based value objects."""

    @property
    def value(self) -> str:
        return self.root

    def __str__(self) -> str:
        return self.root


class AccountID(_StrVO):
    """Strict Value Object for IBKR Account ID."""

    Input: ClassVar[TypeAlias] = AccountIDInput


class Symbol(_StrVO):
    """Strict Value Object for security symbols."""

    Input: ClassVar[TypeAlias] = SymbolInput


class ConID(_StrVO):
    """Strict Value Object for IBKR Contract ID."""

    Input: ClassVar[TypeAlias] = ConIDInput


class FlexToken(_StrVO):
    """Strict Value Object for IBKR Flex Web Service Token."""

    Input: ClassVar[TypeAlias] = FlexTokenInput


class FlexQueryID(_StrVO):
    """Strict Value Object for IBKR Flex Query ID."""

    Input: ClassVar[TypeAlias] = FlexQueryIDInput


class ReferenceCode(_StrVO):
    """Strict Value Object for IBKR Reference Code."""

    Input: ClassVar[TypeAlias] = ReferenceCodeInput


class CurrencyCode(RootModel[CurrencyVO | str]):
    """Strict Value Object for currency codes."""

    Input: ClassVar[TypeAlias] = CurrencyCodeInput

    @property
    def value(self) -> CurrencyVO | str:
        return self.root

    def __str__(self) -> str:
        return str(self.root)
