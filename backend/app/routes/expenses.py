from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseOut
from sqlalchemy.future import select
from sqlalchemy import desc

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post(
    "/",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    expense: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    new_expense = Expense(
        user_id=current_user.id,
        amount=expense.amount,
        category=expense.category,
        description=expense.description,
        expense_date=expense.expense_date,
        extra_data=expense.extra_data,
    )

    db.add(new_expense)
    await db.commit()
    await db.refresh(new_expense)

    return new_expense

@router.get("/", response_model=list[ExpenseOut])
async def list_expenses(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = (
        select(Expense)
        .where(Expense.user_id == current_user.id)
        .order_by(desc(Expense.expense_date))
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)

    expenses = result.scalars().all()

    return expenses