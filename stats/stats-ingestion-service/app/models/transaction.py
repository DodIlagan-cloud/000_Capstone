"""Transaction data model for Stats Ingestion Service"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import date as Date


class Transaction(BaseModel):
    """Transaction model representing a financial transaction"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-04-17",
                "description": "COFFEE SHOP PURCHASE",
                "amount": -5.50,
                "transaction_type": "debit",
                "reference": "TXN001",
            }
        }
    )

    date: Date = Field(..., description="Transaction date")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount (positive for credit, negative for debit)")
    transaction_type: str = Field(..., description="Transaction type: 'credit' or 'debit'")
    reference: Optional[str] = Field(None, description="Transaction reference number")
