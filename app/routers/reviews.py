from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func


from app.models.users import User as UserModel
from app.models.products import Product as ProductModel
from app.models.reviews import Review as ReviewModel
from app.schemas import Review as ReviewSchema, ReviewCreate

from app.auth import get_current_user
from app.db_depends import get_async_db

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)


async def update_product_rating(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    product = await db.get(ProductModel, product_id)
    product.rating = avg_rating
    await db.commit()


@router.get("/", response_model=list[ReviewSchema])
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список всех активных отзывов (is_active = True) о товарах.
    """
    result = await db.scalars(select(ReviewModel).where(ReviewModel.is_active == True))
    return result.all()


@router.post("/", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
    review: ReviewCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Создаёт новый отзыв для указанного товара. После добавления отзыва пересчитывает средний рейтинг товара
    (rating в таблице products) на основе всех активных оценок (grade) для этого товара.
    """

    # проверка роли пользователя
    if current_user.role != "buyer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only buyers can perform this action")

    # проверка наличия товара
    product_result = await db.scalars(
        select(ProductModel).where(ProductModel.id == review.product_id, ProductModel.is_active == True)
    )
    db_product = product_result.first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # проверка на наличие отзыва от покупателя на данный товар
    review_result = await db.scalars(
        select(ReviewModel).where(
            ReviewModel.product_id == review.product_id,
            ReviewModel.user_id == current_user.id,
            ReviewModel.is_active == True
        )
    )
    if review_result.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This buyer has already left a review for this product"
        )

    # создание отзыва в БД
    db_review = ReviewModel(**review.model_dump(), user_id=current_user.id)
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)

    # пересчет рейтинга
    await update_product_rating(db, review.product_id)

    return db_review


@router.delete("/{review_id}")
async def delete_product(
    review_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Выполняет мягкое удаление отзыва по review_id, устанавливая is_active = False.
    После удаления пересчитывает рейтинг товара (rating в таблице products) на основе оставшихся активных отзывов.
    """

    # проверка существования отзыва
    result_review = await db.scalars(
        select(ReviewModel).where(ReviewModel.id == review_id, ReviewModel.is_active == True)
    )
    review = result_review.first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found or inactive")

    # проверка роли пользователя
    if review.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the review author or an admin can delete this review"
        )

    await db.execute(
        update(ReviewModel).where(ReviewModel.id == review_id).values(is_active=False)
    )
    await db.commit()

    await update_product_rating(db, review.product_id)

    return {"message": "Review deleted"}
