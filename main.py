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



from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletHTTPException
from schemas import PostCreate, PostResponse
from datetime import datetime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

posts: list[dict] = [
    {
        "id": 1,
        "author": "Corey Schafer",
        "title": "FastAPI is Awesome",
        "content": "This framework is really easy to use and super fast.",
        "date_posted": "April 20, 2025",
    },
    {
        "id": 2,
        "author": "Jane Doe",
        "title": "Python is Great for Web Development",
        "content": "Python is a great language for web development, and FastAPI makes it even better.",
        "date_posted": "April 21, 2025",
    }
]


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"posts": posts, "title": "Home"},
    )


@app.get("/posts/{post_id}",include_in_schema=False)
def get_post_idhtml(request:Request, post_id:int):
    for post in posts:
        title = post["title"][:20]
        if post.get('id') == post_id:
            return templates.TemplateResponse(
                request,
                "post.html",
                {"post":post,"title":title}
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="not found")

@app.get("/api/posts",response_model=list[PostResponse])
def get_posts():
    return posts

@app.post("/api/posts",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
def make_post(post: PostCreate):
    id = max(p["id"] for p in posts) + 1 if posts else 1
    new_post = {
        "id":id,
        "author":post.author,
        "title":post.title,
        "content":post.content,
        "date_posted":"May 16 2026"
    }
    posts.append(new_post)
    print("post updated")
    return new_post

@app.get("/api/posts/{post_id}", response_model=PostResponse)
def get_post_byid(post_id: int):
    for post in posts:
        if post.get("id") == post_id:
            return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Id not found")


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