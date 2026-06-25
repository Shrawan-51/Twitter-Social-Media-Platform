from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter()

@router.post("",response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate,db: Annotated[AsyncSession,Depends(get_db)]):#dependancy injection here using depends
    #it says before running this function call this get_db and pass the result as db parameter

    #for username should not be same check
    result=await db.execute(select(models.User).where(models.User.username == user.username),)
    existing_user=result.scalars().first()

    if existing_user:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User name Alredy exist",
        )
    
    #for email unique check
    result=await db.execute(select(models.User).where(models.User.email == user.email),)
    existing_email=result.scalars().first()

    if existing_email:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email Alredy exist",
        )
    new_user=models.User(
        username=user.username,
        email=user.email,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user #now when we return user the pidantic will auto convert it to a userresponse we write in api creation

@router.get("/{user_id}",response_model=UserResponse)
async def get_user(user_id: int,db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND ,
        detail="User Not Found"
    )

@router.get("/{user_id}/posts",response_model=list[PostResponse])
async def get_user_posts(user_id: int, db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    result= await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id == user_id))
    posts=result.scalars().all()
    return posts

@router.patch("/{user_id}",response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, db: Annotated[AsyncSession,Depends(get_db)]):
    res = await db.execute(select(models.User).where(models.User.id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found"
        )
    res = await db.execute(select(models.User).where(models.User.email==user_update.email))
    email = res.scalars().first()

    if user_update.username is not None and user.username != user_update.username:
        result = await db.execute(select(models.User).where(models.User.username == user_update.username))
        existing_user=result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username already exists")
    if user_update.email is not None and user.email != user_update.email:
        result = await db.execute(select(models.User).where(models.User.email == user_update.email))
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Email already exist")

    if user_update.email is not None:
        user.email = user_update.email
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    # update_data = user.model_dump(exclude_unset=True)
    # for field,val in update_data.items:
    #     setattr(user,field,val)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int,db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    await db.delete(user)
    await db.commit()
    return None
# @router.delete("api/users/{user_id}",status_code=status.HTTP_200_OK)
# async def delete_user(user_id: int,db: Annotated[AsyncSession,Depends(get_db)]):
#     result = await db.execute(select(models.User).where(models.User.id == user_id))
#     user = result.scalars().first()

#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found")
    
#     await db.delete(user)
#     await db.commit()
