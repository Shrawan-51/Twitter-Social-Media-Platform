from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status, Depends #depends for dependency injections
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fastapi.exception_handlers import request_validation_exception_handler,http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletHTTPException
from schemas import PostCreate, PostResponse, PostUpdate
from schemas import UserResponse,UserCreate, UserUpdate

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
# from models import User, Post
import models
from database import get_db, engine, Base
from datetime import datetime
from typing import Annotated

#Life span
@asynccontextmanager
async def lifespan(_app:FastAPI):
    #Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    #Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media",StaticFiles(directory="media"),name="media") #creates a media prefix for serving the files from that directory
templates = Jinja2Templates(directory="templates")

# posts: list[dict] = [
#     {
#         "id": 1,
#         "author": "Corey Schafer",
#         "title": "FastAPI is Awesome",
#         "content": "This framework is really easy to use and super fast.",
#         "date_posted": "April 20, 2025",
#     },
#     {
#         "id": 2,
#         "author": "Jane Doe",
#         "title": "Python is Great for Web Development",
#         "content": "Python is a great language for web development, and FastAPI makes it even better.",
#         "date_posted": "April 21, 2025",
#     }
# ]


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
async def home(request: Request,db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.Post).options(selectinload(models.Post.author)),)
    posts=result.scalars().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {"posts": posts, "title": "Home"},
    )


@app.get("/posts/{post_id}",include_in_schema=False)
async def get_post_idhtml(request:Request, post_id:int,db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.Post)
                             .options(selectinload(models.Post.author))
                             .where(models.Post.id == post_id),)
    post=result.scalars().first()
    if post:
        title=post.title[:50]
        return templates.TemplateResponse(
            request,
            "post.html",
            {"post":post,"title":title}
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="not found")

@app.get("/api/posts",response_model=list[PostResponse])
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.Post).options(selectinload(models.Post.author)))
    posts=result.scalars().all()
    return posts

@app.post("/api/users",response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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

@app.delete("/users/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int,db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NO_CONTENT,
            detail="User Not Found"
        )
    await db.delete(user)
    await db.commit()
    return None

@app.get("/api/users/{user_id}",response_model=UserResponse)
async def get_user(user_id: int,db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND ,
        detail="User Not Found"
    )

@app.patch("api/users/{user_id}",response_model=UserResponse)
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

@app.delete("api/users/{user_id}",status_code=status.HTTP_200_OK)
async def delete_user(user_id: int,db: Annotated[AsyncSession,Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found")
    
    await db.delete(user)
    await db.commit()

@app.get("/api/users/{user_id}/posts",response_model=list[PostResponse])
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

@app.get("/users/{user_id}/posts",include_in_schema=False, name="users_posts")
async def user_posts_page(request: Request, user_id: int, db: Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id == user_id))
    posts=result.scalar().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts":posts, "user": user, "title": f"{user.username}'s Posts"},
    )


@app.post("/api/posts",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, db: Annotated[AsyncSession,Depends(get_db)]):
    result= await db.execute(select(models.User).where(models.User.id == post.user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user Not Found"
        )
    
    new_post=models.Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])
    return new_post

@app.get("/api/posts/{post_id}", response_model=PostResponse)
async def get_post_byid(post_id: int,db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post=result.scalars().first()
    if post:
       return post 
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Id not found")

@app.put("/api/posts/{post_id}", response_model=PostResponse)
async def update_post_full(post_id: int, post_data: PostCreate ,db: Annotated[AsyncSession, Depends(get_db)]):
    result=await db.execute(select(models.Post).where(models.Post.id == post_id))
    post=result.scalars().first()
    if not post: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")

    if post_data.user_id != post.user_id:
        result= await db.execute(
            select(models.User).where(models.User.id == post_data.user_id),
        )
        user=result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found")
    
    post.title=post_data.title
    post.content=post_data.content
    post.user_id=post_data.user_id
    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post

@app.patch("/api/posts/{post_id}", response_model=PostResponse)
async def update_post_partial(post_id: int, post_data: PostUpdate ,db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.Post).where(models.Post.id == post_id))
    post=result.scalars().first()
    if not post: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")
    
    # if post_data.title :
    #     post.title = post_data.title
    # if post_data.content :
    #     post.content=post_data.content

    update_data = post_data.model_dump(exclude_unset=True)
    for field,value in update_data.values:
        setattr(post,field,value)
    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post

@app.delete("/posts/{post_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result= await db.execute(select(models.Post).where(models.Post.id == post_id))
    post=result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post Not found"
        )
    await db.delete(post)
    await db.commit()    


# Exception handler

@app.exception_handler(StarletHTTPException)
async def general_http_exception_handler(request: Request, exception:StarletHTTPException):
    
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request,exception)
    
    message = (
        exception.detail
        if exception.detail
        else "An error occured. Please check your request and try again"
    )
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code":exception.status_code,
            "title": exception.status_code,
            "message":message,
        },
        status_code=exception.status_code,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request,exception)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code":status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title":status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request parameter, please check your input",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )

