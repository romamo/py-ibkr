from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import AssetClass, BuySell, CashAction, Code, OpenClose, OrderType, PutCall, TradeType


class FlexModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Trade(FlexModel):
    transactionType: TradeType | None = None
    openCloseIndicator: OpenClose | None = None
    buySell: BuySell | None = None
    orderType: OrderType | None = None
    assetCategory: AssetClass | None = None
    accountId: str | None = None
    currency: str | None = None
    fxRateToBase: Decimal | None = None
    symbol: str | None = None
    conid: str | None = None
    cusip: str | None = None
    isin: str | None = None
    figi: str | None = None
    description: str | None = None
    listingExchange: str | None = None
    multiplier: Decimal | None = None
    strike: Decimal | None = None
    expiry: date | None = None
    putCall: PutCall | None = None
    tradeID: str | None = None
    reportDate: date | None = None
    tradeDate: date | None = None
    tradeTime: time | None = None
    settleDateTarget: date | None = None
    exchange: str | None = None
    quantity: Decimal | None = None
    tradePrice: Decimal | None = None
    tradeMoney: Decimal | None = None
    proceeds: Decimal | None = None
    netCash: Decimal | None = None
    netCashInBase: Decimal | None = None
    taxes: Decimal | None = None
    ibCommission: Decimal | None = None
    ibCommissionCurrency: str | None = None
    closePrice: Decimal | None = None
    notes: list[Code] = Field(default_factory=list)
    cost: Decimal | None = None
    mtmPnl: Decimal | None = None
    origTradePrice: Decimal | None = None
    origTradeDate: date | None = None
    origTradeID: str | None = None
    origOrderID: str | None = None
    openDateTime: datetime | None = None
    fifoPnlRealized: Decimal | None = None
    capitalGainsPnl: Decimal | None = None
    levelOfDetail: str | None = None
    ibOrderID: str | None = None
    orderTime: datetime | None = None
    changeInPrice: Decimal | None = None
    changeInQuantity: Decimal | None = None
    fxPnl: Decimal | None = None
    clearingFirmID: str | None = None
    transactionID: str | None = None
    holdingPeriodDateTime: datetime | None = None
    ibExecID: str | None = None
    brokerageOrderID: str | None = None
    orderReference: str | None = None
    volatilityOrderLink: str | None = None
    exchOrderId: str | None = None
    extExecID: str | None = None
    traderID: str | None = None
    isAPIOrder: bool | None = None
    acctAlias: str | None = None
    model: str | None = None
    securityID: str | None = None
    securityIDType: str | None = None
    principalAdjustFactor: Decimal | None = None
    dateTime: datetime | None = None
    underlyingConid: str | None = None
    underlyingSecurityID: str | None = None
    underlyingSymbol: str | None = None
    underlyingListingExchange: str | None = None
    issuer: str | None = None
    sedol: str | None = None
    whenRealized: datetime | None = None
    whenReopened: datetime | None = None
    accruedInt: Decimal | None = None
    serialNumber: str | None = None
    deliveryType: str | None = None
    commodityType: str | None = None
    fineness: Decimal | None = None
    weight: str | None = None
    relatedTradeID: str | None = None
    relatedTransactionID: str | None = None
    origTransactionID: str | None = None
    subCategory: str | None = None
    issuerCountryCode: str | None = None
    rtn: str | None = None
    initialInvestment: Decimal | None = None

    # Missing in ibflex but present in XML
    positionActionID: str | None = None
    actionID: str | None = None
    availableForTradingDate: datetime | None = None
    exDate: datetime | None = None


class CashTransaction(FlexModel):
    type: CashAction | None = None
    assetCategory: AssetClass | None = None
    subCategory: str | None = None
    accountId: str | None = None
    currency: str | None = None
    fxRateToBase: Decimal | None = None
    description: str | None = None
    conid: str | None = None
    securityID: str | None = None
    cusip: str | None = None
    isin: str | None = None
    listingExchange: str | None = None
    underlyingConid: str | None = None
    underlyingSecurityID: str | None = None
    underlyingListingExchange: str | None = None
    amount: Decimal | None = None
    dateTime: datetime | None = None
    sedol: str | None = None
    symbol: str | None = None
    securityIDType: str | None = None
    underlyingSymbol: str | None = None
    issuer: str | None = None
    multiplier: Decimal | None = None
    strike: Decimal | None = None
    expiry: date | None = None
    putCall: PutCall | None = None
    principalAdjustFactor: Decimal | None = None
    tradeID: str | None = None
    code: list[Code] = Field(default_factory=list)
    transactionID: str | None = None
    reportDate: date | None = None
    clientReference: str | None = None
    settleDate: date | None = None
    acctAlias: str | None = None
    actionID: str | None = None
    model: str | None = None
    levelOfDetail: str | None = None
    serialNumber: str | None = None
    deliveryType: str | None = None
    commodityType: str | None = None
    fineness: Decimal | None = None
    weight: str | None = None
    figi: str | None = None
    issuerCountryCode: str | None = None
    availableForTradingDate: datetime | None = None
    exDate: datetime | None = None


class FlexStatement(FlexModel):
    accountId: str
    fromDate: date
    toDate: date
    period: str
    whenGenerated: datetime
    Trades: list[Trade] = Field(default_factory=list)
    CashTransactions: list[CashTransaction] = Field(default_factory=list)
    # Add other lists as needed


class FlexQueryResponse(FlexModel):
    queryName: str
    type: str
    FlexStatements: list[FlexStatement] = Field(default_factory=list)
