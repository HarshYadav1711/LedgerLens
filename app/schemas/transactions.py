from pydantic import BaseModel, ConfigDict


class TopMerchantItem(BaseModel):
    merchant: str
    total_amount: float


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    txn_id: str | None
    date: str | None
    merchant: str | None
    amount: float | None
    currency: str | None
    status: str | None
    category: str | None
    account_id: str | None
    notes: str | None
    is_anomaly: bool
    anomaly_reason: str | None
    llm_category: str | None
    llm_failed: bool


class CategoryBreakdownItem(BaseModel):
    category: str
    count: int
    total_amount: float
