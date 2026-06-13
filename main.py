# from fastapi import FastAPI,Request
# # from fastapi.responses import HTMLResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# app = FastAPI()
# app.mount("/static", StaticFiles(directory="static"), name="static")

# templates = Jinja2Templates(directory="templates")


# posts = [
#     {
#         "id":"123",
#         "name":"shrawan",
#         "type":"buignner",
#         "post":"my name is Shrawan"
#     },
#     {
#         "id":"321",
#         "name":"Ram",
#         "type":"Master",
#         "post":"I am everything"
#     }
# ]
# @app.get("/",include_in_schema=False)
# async def home(request: Request):
#     # return f"<h1>Hello World {plist[0]["name"]} </h1>"
#     return templates.TemplateResponse(request,"home.html",{"posts":posts,"title":"Mark"})


# @app.get("/posts")
# async def get_posts():
#     return plist



from fastapi import FastAPI, Request, HTTPException, status, Depends #depends for dependency injections
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletHTTPException
from schemas import PostCreate, PostResponse, PostUpdate
from schemas import UserResponse,UserCreate, UserUpdate

from sqlalchemy import select
from sqlalchemy.orm import Session

# from models import User, Post
import models
from database import get_db, engine, Base
from datetime import datetime
from typing import Annotated

Base.metadata.create_all(bind=engine)

app = FastAPI()

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
def home(request: Request,db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post))
    posts=result.scalars().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {"posts": posts, "title": "Home"},
    )


@app.get("/posts/{post_id}",include_in_schema=False)
def get_post_idhtml(request:Request, post_id:int,db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post).where(models.Post.id == post_id))
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
def get_posts(db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post))
    posts=result.scalars().all()
    return posts

@app.post("/api/users",response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate,db: Annotated[Session,Depends(get_db)]):#dependancy injection here using depends
    #it says before running this function call this get_db and pass the result as db parameter

    #for username should not be same check
    result=db.execute(select(models.User).where(models.User.username == user.username),)
    existing_user=result.scalars().first()

    if existing_user:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User name Alredy exist",
        )
    
    #for email unique check
    result=db.execute(select(models.User).where(models.User.email == user.email),)
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
    db.commit()
    db.refresh(new_user)

    return new_user #now when we return user the pidantic will auto convert it to a userresponse we write in api creation

@app.delete("/users/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int,db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NO_CONTENT,
            detail="User Not Found"
        )
    db.delete(user)
    db.commit()
    return None

@app.get("/api/users/{user_id}",response_model=UserResponse)
def get_user(user_id: int,db: Annotated[Session,Depends(get_db)]):
    result=db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND ,
        detail="User Not Found"
    )

@app.patch("api/users/{user_id}",response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, db: Annotated[Session,Depends(get_db)]):
    res = db.execute(select(models.User).where(models.User.id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found"
        )
    res = db.execute(select(models.User).where(models.User.email==user_update.email))
    email = res.scalars().first()

    if user_update.username is not None and user.username != user_update.username:
        result = db.execute(select(models.User).where(models.User.username == user_update.username))
        existing_user=result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Username already exists")
    if user_update.email is not None and user.email != user_update.email:
        result = db.execute(select(models.User).where(models.User.email == user_update.email))
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
    db.commit()
    db.refresh(user)
    return user

@app.delete("api/users/{user_id}",status_code=status.HTTP_200_OK)
def delete_user(user_id: int,db: Annotated[Session,Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found")
    
    db.delete(user)
    db.commit()

@app.get("/api/users/{user_id}/posts",response_model=list[PostResponse])
def get_user_posts(user_id: int, db: Annotated[Session,Depends(get_db)]):
    result=db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    result=db.execute(select(models.Post).where(models.Post.user_id == user_id))
    posts=result.scalars().all()
    return posts

@app.get("/users/{user_id}/posts",include_in_schema=False, name="users_posts")
def user_posts_page(request: Request, user_id: int, db: Annotated[Session,Depends(get_db)]):
    result=db.execute(select(models.User).where(models.User.id == user_id))
    user=result.scalars().first
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )
    result=db.execute(select(models.Post).where(models.Post.user_id == user_id))
    posts=result.scalar().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts":posts, "user": user, "title": f"{user.username}'s Posts"},
    )


@app.post("/api/posts",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate, db: Annotated[Session,Depends(get_db)]):
    result=db.execute(select(models.User).where(models.User.id == post.user_id))
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
    db.commit()
    db.refresh(new_post)
    return new_post

@app.get("/api/posts/{post_id}", response_model=PostResponse)
def get_post_byid(post_id: int,db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post).where(models.Post.id == post_id))
    post=result.scalars().first()
    if post:
       return post 
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Id not found")

@app.patch("/api/posts/{post_id}", response_model=PostResponse)
def update_post_full(post_id: int, post_data: PostCreate ,db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post).where(models.Post.id == post_id))
    post=result.scalars().first()
    if not post: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")

    if post_data.user_id != post.user_id:
        result=db.execute(
            select(models.User).where(models.User.id == post_data.user_id),
        )
        user=result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User Not Found")
    
    post.title=post_data.title
    post.content=post_data.content
    post.user_id=post_data.user_id
    db.commit()
    db.refresh(post)
    return post

@app.put("/api/posts/{post_id}", response_model=PostResponse)
def update_post_partial(post_id: int, post_data: PostUpdate ,db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post).where(models.Post.id == post_id))
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
    db.commit()
    db.refresh(post)
    return post

@app.delete("/posts/{post_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: Annotated[Session, Depends(get_db)]):
    result=db.execute(select(models.Post).where(models.Post.id == post_id))
    post=result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post Not found"
        )
    db.delete(post)
    db.commit()    


# Exception handler

@app.exception_handler(StarletHTTPException)
def general_http_exception_handler(request: Request, exception:StarletHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error occured. Please check your request and try again"
    )
    
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail":message},
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
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail":exception.errors()},
        )
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

