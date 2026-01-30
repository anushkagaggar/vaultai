from fastapi import APIRouter, Depends, status, HTTPException, Query
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
from sqlalchemy import desc, asc


@router.get("/", response_model=list[ExpenseOut])
async def list_expenses(
    skip: int = 0,
    limit: int = 50,
    sort: str = "expense_date",   # expense_date / amount / category
    order: str = "desc",          # asc / desc
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # Allowed fields (prevent SQL injection)
    sort_map = {
        "expense_date": Expense.expense_date,
        "amount": Expense.amount,
        "category": Expense.category,
    }

    if sort not in sort_map:
        raise HTTPException(400, detail="Invalid sort field")

    sort_column = sort_map[sort]

    order_func = desc if order == "desc" else asc

    query = (
        select(Expense)
        .where(Expense.user_id == current_user.id)
        .order_by(order_func(sort_column))
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
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = select(func.sum(Expense.amount)).where(
        Expense.user_id == current_user.id
    )

    if from_date:
        query = query.where(Expense.expense_date >= from_date)

    if to_date:
        query = query.where(Expense.expense_date <= to_date)

    total_result = await db.execute(query)

    total = total_result.scalar() or 0

    # Group by category
    category_query = select(
        Expense.category,
        func.sum(Expense.amount)
    ).where(
        Expense.user_id == current_user.id
    )

    if from_date:
        category_query = category_query.where(Expense.expense_date >= from_date)

    if to_date:
        category_query = category_query.where(Expense.expense_date <= to_date)

    category_query = category_query.group_by(Expense.category)

    category_result = await db.execute(category_query)

    rows = category_result.all()

    by_category = {
        category: amount for category, amount in rows
    }

    return {
        "total": total,
        "by_category": by_category
    }
