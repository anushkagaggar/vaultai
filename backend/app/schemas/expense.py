from datetime import date
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator


class ExpenseCreate(BaseModel):
    amount: float = Field(gt=0)
    category: str = Field(max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    expense_date: date
    extra_data: Optional[Dict[str, Any]] = None
    @field_validator("category", "description", mode="before")
    @classmethod
    def clean_text(cls, v):
        if v is None:
            return v

        v = v.strip()

        if not v:
            raise ValueError("Field cannot be empty")

        return v



class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    expense_date: Optional[date] = None
    extra_data: Optional[Dict[str, Any]] = None
    @field_validator("category", "description", mode="before")
    @classmethod
    def clean_text(cls, v):
        if v is None:
            return v

        v = v.strip()

        if not v:
            raise ValueError("Field cannot be empty")

        return v


class ExpenseOut(BaseModel):
    id: int
    amount: float
    category: str
    description: Optional[str]
    expense_date: date
    extra_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
