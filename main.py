from datetime import datetime
from enum import Enum
import random
import string
import time

import bcrypt
import jwt

from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, DateTime, desc, or_, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base


JWT_KEY = "83nh2k3j398324njk2dSDlkdf"
JWT_ISSUER = "Valeriy Lapshov"
JWT_ALGO = "HS512"



    

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настройка базы данных

SQLALCHEMY_DATABASE_URL = "sqlite:///./todo.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



# Настройка шаблонов

def format_datetime(value, format='%d.%m.%Y %H:%M'):
    return value.strftime(format)

templates = Jinja2Templates(directory="templates")
templates.env.filters['format_datetime'] = format_datetime

# Модели данных

class Status(Enum):
    WAIT = 0
    IN_PROGRESS = 1
    DONE = 2

class Priority(Enum):
    LOW = 0
    MED = 1
    HIGH = 2

class Todo(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    status = Column(Integer)
    priority = Column(Integer,default=0)
    created_at = Column(DateTime, default=datetime.now)
    author_id = Column(Integer, ForeignKey("todo_users.id"))

class TodoUser(Base):
    __tablename__ = "todo_users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    password = Column(String)

Base.metadata.create_all(bind=engine)

# 
    


def sign_up(login, password):
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    db = SessionLocal()
    user = TodoUser(name=login, password=pw_hash.decode('utf-8'))
    db.add(user)
    db.commit()
    db.close()

    # udb.add_user(User(login=login, pw_hash=pw_hash.decode('utf-8')))


def create_token(login):
    rnd = "".join(
        random.choice(string.printable) for _ in range(24)
    )
    now = int(time.time())
    return jwt.encode({
        "issued_at": now,
        "not_before": now,
        "expiry": now + 3600,
        "token_id": rnd,
        "issuer": JWT_ISSUER, 
        "data": {"login": login}
    }, JWT_KEY, algorithm=JWT_ALGO)


def verify_token(request):
    try:
        token = request.cookies.get("JWT")
        decoded = jwt.decode(token, JWT_KEY, algorithms=[JWT_ALGO])
        return decoded
    except:
        return None



##############################################
#            WEB PAGES (GET запрсы)          #
##############################################

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {'request': request})

@app.get("/logout", response_class=HTMLResponse)
async def login(request: Request, response: Response):
    response =  RedirectResponse(url="/", status_code=302)
    response.delete_cookie('JWT')
    return response



@app.post("/login-post", response_class=HTMLResponse)
async def login_post(request: Request, response: Response, login:str=Form(...), password:str=Form(...)):
    db = SessionLocal()
    u = db.query(TodoUser).filter_by(name=login).first()
    if u:
        valid = bcrypt.checkpw(
            password.encode("utf-8"),
            u.password.encode("utf-8")
        )
        if valid:
            print('password correct')
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(key='JWT', value=create_token(u.name))
            return response
        else:
            print('password incorrect')
    
    # response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return RedirectResponse(url="/", status_code=302)

async def check_logged_user(request):

    db = SessionLocal()
    logged_as = verify_token(request)

    if logged_as:
        logged_as=logged_as['data']['login']
    else:
        return None

    return db.query(TodoUser).filter_by(name=logged_as).first()


@app.get("/", response_class=HTMLResponse)
async def todos(request: Request, order: str='id', reverse:bool=False, search:str='', top:int=0):
    db = SessionLocal()

    u = await check_logged_user(request)
    if u is None:
        return RedirectResponse('/login', status_code=302)
   
    if top:
        todos = db.query(Todo).filter_by(author_id=u.id).order_by(desc(Todo.priority)).limit(top)

    else:

        if order=='id':
            if reverse:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(desc(Todo.id))
            else:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(Todo.id)
        elif order=='title':
            if reverse:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(desc(Todo.title))
            else:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(Todo.title)
        elif order=='date':
            if reverse:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(desc(Todo.created_at))
            else:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(Todo.created_at)
        elif order=='priority':
            if reverse:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(desc(Todo.priority))
            else:
                todos = db.query(Todo).filter_by(author_id=u.id).order_by(Todo.priority)

    if search:
        todos = todos.filter_by(author_id=u.id).filter(or_(Todo.title.contains(search), Todo.description.contains(search)))

    db.close()
    return templates.TemplateResponse("todos.html", {
        "request": request, "todos": todos, "search": search, "top": top, "logged_as": u.name
    })

@app.get("/add", response_class=HTMLResponse)
async def add_todo(request: Request):
    u = await check_logged_user(request)
    if u is None:
        return RedirectResponse('/login', status_code=302)
    
    return templates.TemplateResponse("add.html", {"request": request})

@app.get("/edit/{todo_id}", response_class=HTMLResponse)
async def edit_todo(todo_id: int, request: Request):

    u = await check_logged_user(request)
    if u is None:
        return RedirectResponse('/login', status_code=302)
    
    db = SessionLocal()
    
    todo = db.query(Todo).filter_by(id=todo_id).first()
    db.close()
    if todo is None:
        return templates.TemplateResponse("not_found.html", {"request": request})
    return templates.TemplateResponse("edit.html", {"request": request, "todo": todo})



##############################################
#         ENDPOINTS (POST запросы)           #
##############################################

@app.post("/create-todo", response_class=HTMLResponse)
async def create_todo(request: Request, title: str = Form(...), description: str = Form(...), status: int = Form(...), priority: int = Form(...)):

    u = await check_logged_user(request)
    if u is None:
        return RedirectResponse('/', status_code=302)
    
    db = SessionLocal()
    todo = Todo(title=title, description=description, status=status, priority=priority, author_id=u.id)
    db.add(todo)
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=302)

@app.post("/update-todo/{todo_id}", response_class=HTMLResponse)
async def update_todo(request: Request, todo_id: int, title: str = Form(...), description: str = Form(...), status: int = Form(...), priority: int = Form(...)):

    u = await check_logged_user(request)
    if u is None:
        return RedirectResponse('/', status_code=302)
    
    db = SessionLocal()
    db.query(Todo).filter_by(id=todo_id, author_id=u.id).update({
        "title": title,
        "description": description,
        "status": status,
        "priority": priority
    })
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=302)

@app.get("/delete/{todo_id}/", response_class=HTMLResponse)
async def delete_todo(request: Request, todo_id: int):

    u = await check_logged_user(request)
    if u is None:
        return RedirectResponse('/', status_code=302)
    
    db = SessionLocal()
    db_todo = db.query(Todo).filter_by(id=todo_id, author_id=u.id).first()
    if db_todo is not None:
        db.delete(db_todo)
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=302)



def register_user(login, password):
    """Демонстрационная функция для добавления временных пользователей"""
    db = SessionLocal()
    u = db.query(TodoUser).filter_by(name=login).first()
    if u:
        print('user exists: ', u.name)
    else:
        sign_up(login, password)
    db.close()


if __name__ == "__main__":

    # Создаем пользователей в демонстрационных целях
    register_user('admin', '12345')
    register_user('user1', '23456')
    register_user('user2', '34567')

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
