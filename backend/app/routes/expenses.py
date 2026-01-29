from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Optional
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseOut
from sqlalchemy.future import select
from sqlalchemy import desc, func
from app.schemas.expense import ExpenseUpdate
router = APIRouter(prefix="/expenses", tags=["expenses"])

@router.get("/", response_model=list[ExpenseOut])
async def list_expenses(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = select(Expense).where(
        Expense.user_id == current_user.id
    )

    if start_date:
        query = query.where(Expense.expense_date >= start_date)

    if end_date:
        query = query.where(Expense.expense_date <= end_date)

    if category:
        query = query.where(Expense.category == category)

    query = (
        query.order_by(desc(Expense.expense_date))
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    return result.scalars().all()


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
        category=expense.category.lower() if expense.category else None,
        description=expense.description,
        expense_date=expense.expense_date,
        extra_data=expense.extra_data,
    )

    db.add(new_expense)
    await db.commit()
    await db.refresh(new_expense)

    return new_expense


@router.put("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    )

    db_expense = result.scalar_one_or_none()

    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    data = expense.model_dump(exclude_unset=True)
    if "category" in data and data["category"]:
        data["category"] = data["category"].lower()

    for key, value in data.items():
        setattr(db_expense, key, value)

    await db.commit()
    await db.refresh(db_expense)

    return db_expense

@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    )

    db_expense = result.scalar_one_or_none()

    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    await db.delete(db_expense)
    await db.commit()

    return None

@router.get("/stats")
async def expense_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # Total spent
    total_result = await db.execute(
        select(func.sum(Expense.amount))
        .where(Expense.user_id == current_user.id)
    )

    total = total_result.scalar() or 0

    # Group by category
    category_result = await db.execute(
        select(
            Expense.category,
            func.sum(Expense.amount)
        )
        .where(Expense.user_id == current_user.id)
        .group_by(Expense.category)
    )

    rows = category_result.all()

    by_category = {
        category: amount for category, amount in rows
    }

    return {
        "total": total,
        "by_category": by_category
    }
