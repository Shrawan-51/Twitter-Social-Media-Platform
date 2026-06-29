from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status, Depends #depends for dependency injections
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fastapi.exception_handlers import request_validation_exception_handler,http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletHTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
# from models import User, Post
import models
from database import get_db, engine, Base
from datetime import datetime
from typing import Annotated
from routers import posts,users


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

app.include_router(users.router,prefix="/api/users",tags=["users"])
app.include_router(posts.router,prefix="/api/posts",tags=["posts"])

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
    result= await db.execute(select(models.Post)
                             .options(selectinload(models.Post.author))
                             .order_by(models.Post.date_posted.desc())
                             ,)
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


@app.get("/users/{user_id}/posts",include_in_schema=False, name="users_posts")
async def user_posts_page(request: Request, user_id: int, db: Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User)
                            .where(models.User.id == user_id)
                            .order_by(models.Post.date_posted.desc()),)
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

## login and register template_routes
@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Login"},
    )


@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request,
        "register.html",
        {"title": "Register"},
    )

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

