from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status,UploadFile,Query,BackgroundTasks
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import (PostResponse, UserCreate, UserPublic, UserPrivate, UserUpdate, Token, PaginatedPostResponse,
                     ForgotPasswordRequest,
                     ResetPasswordRequest,
                     ChangePasswordRequest,)

from datetime import timedelta,UTC,datetime
from fastapi.security import OAuth2PasswordRequestForm
from auth import(
    create_access_token,
    hash_Password,
    verify_Password,
    CurrentUser,
    generate_reset_token,
    hash_reset_token,
)
from PIL import UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from image_utils import delete_profile_image,process_profile_img
from sqlalchemy import delete as sql_delete
from email_utils import send_password_reset_email  

from config import settings
router = APIRouter()

@router.post("",response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate,db: Annotated[AsyncSession,Depends(get_db)]):#dependancy injection here using depends
    #it says before running this function call this get_db and pass the result as db parameter

    #for username should not be same check
    result=await db.execute(select(models.User).where(func.lower(models.User.username) == user.username.lower()),)
    existing_user=result.scalars().first()

    if existing_user:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User name Alredy exist",
        )
    
    #for email unique check
    result=await db.execute(select(models.User).where(func.lower(models.User.email) == user.email.lower()),)
    existing_email=result.scalars().first()

    if existing_email:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email Alredy exist",
        )
    new_user=models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash=hash_Password(user.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user #now when we return user the pidantic will auto convert it to a userresponse we write in api creation

#login for access token
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Look up user by email (case-insensitive)
    # Note: OAuth2PasswordRequestForm uses "username" field, but we treat it as email
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == form_data.username.lower(),
        ),
    )
    user = result.scalars().first()

    # Verify user exists and password is correct
    # Don't reveal which one failed (security best practice)
    if not user or not verify_Password(form_data.password,user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Username or Password",
            headers={"www-Authenticate": "Bearer"},
        ) 
    # Create access token with user id as subject
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub":str(user.id)},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token,token_type="bearer")

#get current user
@router.get("/me",response_model=UserPrivate)
async def get_current_user(
    current_user: CurrentUser,
):
    return current_user
    """Get the currently authenticated user."""
    # user_id = verify_access_token(token)
    # if user_id is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid or expired Token",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # try:
    #     user_id_int = int(user_id)
    # except (TypeError,ValueError):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid or expired token",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    
    # result = await db.execute(select(models.User).where(models.User.id == user_id_int))
    # user = result.scalars().first()
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="User not found",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # return user

@router.post("/forgot-password",status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request_data:ForgotPasswordRequest,
    background_tasks:BackgroundTasks,
    db: Annotated[AsyncSession,Depends(get_db)],
):
    result = await db.execute(select(models.User).where(
        func.lower(models.User.email) == request_data.email.lower(),
    ),)
    user = result.scalars().first()

    if user:
        await db.execute(
            sql_delete(models.PasswordResetToken).where(models.PasswordResetToken.user_id == user.id,),
        )

        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(UTC)+timedelta(
            minutes=settings.reset_token_expire_minutes
        )

        reset_token = models.PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.commit()

        background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,
            username=user.username,
            token=token
        )
    return {
        "message":"If an account exists with this email, you will receive password reset instructions."
    }

@router.post("/reset-password",status_code=status.HTTP_200_OK)
async def reset_password(
    request_data :ResetPasswordRequest,
    db:Annotated[AsyncSession,Depends(get_db)]
):
    toke_hash = hash_reset_token(request_data.token)
    result = await db.execute(
        select(models.PasswordResetToken).where(models.PasswordResetToken.token_hash == toke_hash,),
    )
    reset_token = result.scalars().first()
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    if reset_token.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        await db.delete(reset_token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or exired token",
        )

    result = await db.execute(
        select(models.User).where(models.User.id == reset_token.user_id),
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_Password(request_data.new_password)

    await db.execute(
        sql_delete(models.PasswordResetToken).where(models.PasswordResetToken.user_id == user.id,),
    )
    await db.commit()

    return {
        "message":"If an account exists with this email, you will receive password reset instructions."
    }

@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_Password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_Password(password_data.new_password)

    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == current_user.id,
        ),
    )

    await db.commit()
    return {"message": "Password changed successfully"}


@router.get("/{user_id}",response_model=UserPublic)
async def get_user(user_id: int,db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND ,
        detail="User Not Found"
    )

@router.get("/{user_id}/posts",response_model=PaginatedPostResponse)
async def get_user_posts(user_id: int, 
                         db: Annotated[AsyncSession,Depends(get_db)],
                         skip: Annotated[int,Query(ge=0)]=0,
                         limit: Annotated[int,Query(ge=1,le=100)]=10):
    result= await db.execute(select(models.User)
                             .where(models.User.id == user_id)
                             )
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    
    count_result = await db.execute(select(func.count()).select_from(models.Post).where(models.User.id == user_id))
    total = count_result.scalar() or 0

    result= await db.execute(select(models.Post)
                             .options(selectinload(models.Post.author))
                             .where(models.Post.user_id == user_id)
                             .order_by(models.Post.date_posted.desc())
                             .offset(skip)
                            .limit(limit))
    posts=result.scalars().all()
    has_more = skip+len(posts) < total

    return PaginatedPostResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        skip=skip,
        total=total,
        limit=limit,
        has_more=has_more,
    )

@router.patch("/{user_id}",response_model=UserPrivate)
async def update_user(user_id: int, user_update: UserUpdate,current_user: CurrentUser, db: Annotated[AsyncSession,Depends(get_db)]):
    
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update User"
        )
    res = await db.execute(select(models.User).where(models.User.id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found"
        )
    res = await db.execute(select(models.User).where(models.User.email==user_update.email))
    email = res.scalars().first()

    if user_update.username is not None and user.username.lower() != user_update.username.lower():
        result = await db.execute(select(models.User).where(func.lower(models.User.username) == user_update.username.lower()))
        existing_user=result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username already exists")
    if user_update.email is not None and user.email != user_update.email:
        result = await db.execute(select(models.User).where(func(models.User.email) == user_update.email.lower()))
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Email already exist")

    if user_update.email is not None:
        user.email = user_update.email.lower()
    if user_update.username is not None:
        user.username = user_update.username

    # update_data = user.model_dump(exclude_unset=True)
    # for field,val in update_data.items:
    #     setattr(user,field,val)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user:CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first()

    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete post",
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    old_filename = user.image_file
    
    await db.delete(user)
    await db.commit()
    if old_filename:
        delete_profile_image(old_filename) 
    return None
# @router.delete("api/users/{user_id}",status_code=status.HTTP_200_OK)
# async def delete_user(user_id: int,db: Annotated[AsyncSession,Depends(get_db)]):
#     result = await db.execute(select(models.User).where(models.User.id == user_id))
#     user = result.scalars().first()

#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found")
    
#     await db.delete(user)
#     await db.commit()


@router.patch("/{user_id}/picture",response_model=UserPrivate)
async def upload_profile_picture(
    user_id:int,
    file: UploadFile,
    current_user: CurrentUser,
    db : Annotated[AsyncSession,Depends(get_db)]
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's profile"
        )
    
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size_bytes // (1024 * 1024)}MB",
            )
    try:
        new_filename = await run_in_threadpool(process_profile_img,content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err
    
    old_filename = current_user.image_file
    current_user.image_file = new_filename

    await db.commit()
    await db.refresh(current_user)
    if old_filename:
        delete_profile_image(old_filename)
    
    return current_user

router.delete("/{user_id}/picture",response_model=UserPrivate)
async def delete_user_picture(
        user_id:int,
        current_user: CurrentUser,
        db: Annotated[AsyncSession,Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete profile picture"
        )
    old_file_name = current_user.image_file

    if old_file_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to Delete"
        )
    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_file_name)

    return current_user

