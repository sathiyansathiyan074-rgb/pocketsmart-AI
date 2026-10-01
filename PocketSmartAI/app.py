import os
import secrets

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import jwt

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    Request,
    Form,
    File,
    UploadFile,
    HTTPException
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse
)

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates

from fastapi.middleware.cors import CORSMiddleware

from PIL import Image

from services.database import (
    init_db,
    create_user,
    get_user_by_username,
    get_user_by_id,
    save_recommendation,
    list_recommendations,
    get_recommendation
)

from services.gemini_utils import (
    generate_home_recommendations,
    generate_party_recommendations,
    generate_jewelry_recommendations
)


# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env"
)

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    secrets.token_urlsafe(32)
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "60"
    )
)

UPLOAD_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==================================================
# APP
# ==================================================

app = FastAPI(
    title="PocketSmart AI",
    description=(
        "AI-powered smart budget planning assistant"
    ),
    version="1.0.0"
)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


# ==================================================
# STATIC + TEMPLATES
# ==================================================

app.mount(
    "/static",
    StaticFiles(
        directory=BASE_DIR / "static"
    ),
    name="static"
)

templates = Jinja2Templates(
    directory=str(
        BASE_DIR / "templates"
    )
)


# ==================================================
# DATABASE STARTUP
# ==================================================

@app.on_event("startup")
def startup_event():

    init_db()


# ==================================================
# PASSWORD HASHING
# ==================================================

import hashlib
import base64


def hash_password(password: str) -> str:

    salt = secrets.token_bytes(16)

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        120000
    )

    return (
        "pbkdf2_sha256$"
        + base64.urlsafe_b64encode(
            salt
        ).decode()
        + "$"
        + base64.urlsafe_b64encode(
            derived
        ).decode()
    )


def verify_password(
    password: str,
    stored_hash: str
):

    try:

        algorithm, salt_text, hash_text = (
            stored_hash.split("$")
        )

        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.urlsafe_b64decode(
            salt_text.encode()
        )

        expected = base64.urlsafe_b64decode(
            hash_text.encode()
        )

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            120000
        )

        return secrets.compare_digest(
            actual,
            expected
        )

    except Exception:

        return False


# ==================================================
# JWT
# ==================================================

def create_token(
    user_id: int,
    username: str
):

    expiration = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=
            ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expiration
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def decode_token(token: str):

    try:

        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

    except jwt.PyJWTError:

        return None


# ==================================================
# USER
# ==================================================

def get_current_user(
    request: Request
):

    token = request.cookies.get(
        "access_token"
    )

    if not token:
        return None

    payload = decode_token(token)

    if not payload:
        return None

    try:

        user_id = int(
            payload["sub"]
        )

    except Exception:

        return None

    return get_user_by_id(
        user_id
    )


def require_user(
    request: Request
):

    user = get_current_user(
        request
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    return user


# ==================================================
# TEMPLATE RENDER
# ==================================================

def render(
    request: Request,
    template: str,
    **context: Any
):

    context["request"] = request

    context["current_user"] = (
        get_current_user(request)
    )

    return templates.TemplateResponse(
        template,
        context
    )


# ==================================================
# HOME
# ==================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home(
    request: Request
):

    return render(
        request,
        "index.html"
    )


# ==================================================
# REGISTER
# ==================================================

@app.get(
    "/register",
    response_class=HTMLResponse
)
async def register_page(
    request: Request
):

    return render(
        request,
        "register.html"
    )


@app.post("/register")
async def register(
    request: Request,

    username: str = Form(...),

    email: str = Form(...),

    password: str = Form(...),

    confirm_password: str = Form(...)
):

    username = username.strip()

    email = email.strip().lower()

    if len(username) < 3:

        return render(
            request,
            "register.html",
            error=(
                "Username must contain "
                "at least 3 characters."
            )
        )

    if password != confirm_password:

        return render(
            request,
            "register.html",
            error="Passwords do not match."
        )

    if len(password) < 6:

        return render(
            request,
            "register.html",
            error=(
                "Password must contain "
                "at least 6 characters."
            )
        )

    if get_user_by_username(
        username
    ):

        return render(
            request,
            "register.html",
            error="Username already exists."
        )

    password_hash = hash_password(
        password
    )

    create_user(
        username,
        email,
        password_hash
    )

    return RedirectResponse(
        "/login?registered=1",
        status_code=303
    )


# ==================================================
# LOGIN
# ==================================================

@app.get(
    "/login",
    response_class=HTMLResponse
)
async def login_page(
    request: Request
):

    return render(
        request,
        "login.html",
        registered=(
            request.query_params.get(
                "registered"
            ) == "1"
        )
    )


@app.post("/login")
async def login(
    request: Request,

    username: str = Form(...),

    password: str = Form(...)
):

    user = get_user_by_username(
        username.strip()
    )

    if (
        not user
        or not verify_password(
            password,
            user["password_hash"]
        )
    ):

        return render(
            request,
            "login.html",
            error=(
                "Invalid username or password."
            )
        )

    token = create_token(
        user["id"],
        user["username"]
    )

    response = RedirectResponse(
        "/dashboard",
        status_code=303
    )

    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=(
            ACCESS_TOKEN_EXPIRE_MINUTES
            * 60
        )
    )

    return response


# ==================================================
# LOGOUT
# ==================================================

@app.get("/logout")
async def logout():

    response = RedirectResponse(
        "/login",
        status_code=303
    )

    response.delete_cookie(
        "access_token"
    )

    return response


# ==================================================
# TOKEN
# ==================================================

@app.get("/token")
async def token_info(
    request: Request
):

    user = require_user(request)

    return {
        "logged_in": True,
        "username": user["username"],
        "token_type": "bearer"
    }


# ==================================================
# DASHBOARD
# ==================================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse
)
async def dashboard(
    request: Request
):

    user = require_user(
        request
    )

    history = list_recommendations(
        user["id"],
        limit=6
    )

    return render(
        request,
        "dashboard.html",
        user=user,
        history=history
    )


# ==================================================
# PLANNER PAGES
# ==================================================

@app.get(
    "/home-planner",
    response_class=HTMLResponse
)
async def home_planner(
    request: Request
):

    require_user(request)

    return render(
        request,
        "home_planner.html"
    )


@app.get(
    "/party-planner",
    response_class=HTMLResponse
)
async def party_planner(
    request: Request
):

    require_user(request)

    return render(
        request,
        "party_planner.html"
    )


@app.get(
    "/jewelry-planner",
    response_class=HTMLResponse
)
async def jewelry_planner(
    request: Request
):

    require_user(request)

    return render(
        request,
        "jewelry_planner.html"
    )


# ==================================================
# HOME GENERATION
# ==================================================

@app.post(
    "/generate-home",
    response_class=HTMLResponse
)
async def generate_home(
    request: Request,

    budget: float = Form(...),

    room_type: str = Form(...),

    lights: int = Form(0),

    fans: int = Form(0),

    furniture: int = Form(0),

    dining_tables: int = Form(0),

    preferences: str = Form("")
):

    user = require_user(
        request
    )

    if budget <= 0:

        return render(
            request,
            "home_planner.html",
            error=(
                "Budget must be greater than zero."
            )
        )

    data = {
        "budget": budget,
        "room_type": room_type,
        "lights": lights,
        "fans": fans,
        "furniture": furniture,
        "dining_tables": dining_tables,
        "preferences": preferences
    }

    result = (
        generate_home_recommendations(
            data
        )
    )

    recommendation_id = (
        save_recommendation(
            user["id"],
            "home",
            data,
            result
        )
    )

    return render(
        request,
        "recommendations.html",

        title=(
            "Your Personalized "
            "Budget Plan"
        ),

        category="Home Interior",

        result=result,

        recommendation_id=
            recommendation_id
    )


# ==================================================
# PARTY GENERATION
# ==================================================

@app.post(
    "/generate-party",
    response_class=HTMLResponse
)
async def generate_party(
    request: Request,

    budget: float = Form(...),

    guests: int = Form(...),

    event_type: str = Form(...),

    venue_type: str = Form(...),

    catering: bool = Form(False),

    decoration: bool = Form(False),

    entertainment: bool = Form(False),

    requirements: str = Form("")
):

    user = require_user(
        request
    )

    if (
        budget <= 0
        or guests <= 0
    ):

        return render(
            request,
            "party_planner.html",
            error=(
                "Budget and guest count "
                "must be greater than zero."
            )
        )

    data = {
        "budget": budget,
        "guests": guests,
        "event_type": event_type,
        "venue_type": venue_type,
        "catering": catering,
        "decoration": decoration,
        "entertainment": entertainment,
        "requirements": requirements
    }

    result = (
        generate_party_recommendations(
            data
        )
    )

    recommendation_id = (
        save_recommendation(
            user["id"],
            "party",
            data,
            result
        )
    )

    return render(
        request,
        "recommendations.html",

        title="Your Party Budget Plan",

        category="Party Planning",

        result=result,

        recommendation_id=
            recommendation_id
    )


# ==================================================
# JEWELRY GENERATION
# ==================================================

@app.post(
    "/generate-jewelry",
    response_class=HTMLResponse
)
async def generate_jewelry(
    request: Request,

    budget: float = Form(...),

    occasion: str = Form(...),

    preferences: str = Form(...),

    image: Optional[UploadFile] = File(None)
):

    user = require_user(
        request
    )

    if budget <= 0:

        return render(
            request,
            "jewelry_planner.html",
            error=(
                "Budget must be greater than zero."
            )
        )

    image_path = None

    # ------------------------------
    # IMAGE UPLOAD
    # ------------------------------

    if (
        image
        and image.filename
    ):

        extension = (
            Path(
                image.filename
            ).suffix.lower()
        )

        allowed = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        }

        if extension not in allowed:

            return render(
                request,
                "jewelry_planner.html",
                error=(
                    "Upload JPG, PNG "
                    "or WEBP only."
                )
            )

        safe_filename = (
            f"{user['id']}_"
            f"{secrets.token_hex(8)}"
            f"{extension}"
        )

        target = (
            UPLOAD_DIR
            / safe_filename
        )

        content = await image.read()

        if len(content) > (
            8 * 1024 * 1024
        ):

            return render(
                request,
                "jewelry_planner.html",
                error=(
                    "Image must be "
                    "8 MB or smaller."
                )
            )

        target.write_bytes(
            content
        )

        try:

            with Image.open(
                target
            ) as img:

                img.verify()

        except Exception:

            target.unlink(
                missing_ok=True
            )

            return render(
                request,
                "jewelry_planner.html",
                error="Invalid image file."
            )

        image_path = str(
            target
        )

    data = {
        "budget": budget,
        "occasion": occasion,
        "preferences": preferences
    }

    result = (
        generate_jewelry_recommendations(
            data,
            image_path
        )
    )

    if image_path:

        result["outfit_image"] = (
            "/static/uploads/"
            + Path(
                image_path
            ).name
        )

    recommendation_id = (
        save_recommendation(
            user["id"],
            "jewelry",
            data,
            result
        )
    )

    return render(
        request,
        "recommendations.html",

        title=(
            "Your Personalized "
            "Jewelry Recommendations"
        ),

        category="Jewelry",

        result=result,

        recommendation_id=
            recommendation_id
    )


# ==================================================
# HISTORY
# ==================================================

@app.get(
    "/history",
    response_class=HTMLResponse
)
async def history(
    request: Request
):

    user = require_user(
        request
    )

    return render(
        request,
        "history.html",

        history=
            list_recommendations(
                user["id"],
                limit=50
            )
    )


# ==================================================
# RECOMMENDATION DETAILS
# ==================================================

@app.get(
    "/recommendations/{recommendation_id}",
    response_class=HTMLResponse
)
async def recommendation_detail(
    request: Request,
    recommendation_id: int
):

    user = require_user(
        request
    )

    item = get_recommendation(
        recommendation_id,
        user["id"]
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail=(
                "Recommendation not found"
            )
        )

    return render(
        request,
        "recommendations.html",

        title="Recommendation Details",

        category=
            item["category"].title(),

        result=item["result"],

        recommendation_id=
            item["id"]
    )


@app.get(
    "/recommendations-details"
)
async def recommendation_details(
    request: Request,
    id: int
):

    user = require_user(
        request
    )

    item = get_recommendation(
        id,
        user["id"]
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail=(
                "Recommendation not found"
            )
        )

    return item["result"]


# ==================================================
# SESSION APIs
# ==================================================

@app.get("/session-info")
async def session_info(
    request: Request
):

    user = require_user(
        request
    )

    return {
        "logged_in": True,
        "user_id": user["id"],
        "username": user["username"]
    }


@app.get("/session-data")
async def session_data(
    request: Request
):

    user = require_user(
        request
    )

    return {
        "user": user["username"],

        "recent_recommendations":
            list_recommendations(
                user["id"],
                limit=10
            )
    }


# ==================================================
# STARTUP CHECK
# ==================================================

@app.get("/startup")
async def startup_status():

    return {
        "status": "ok",
        "service": "PocketSmart AI"
    }


# ==================================================
# RUN DIRECTLY
# ==================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )