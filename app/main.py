"""
DealBot Dashboard - FastAPI Web App
Tracks Amazon deals via WhatsApp bot.
"""

import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import get_db, P, db_fetchone, db_fetchall, db_execute

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "+14155238886")
WHATSAPP_SANDBOX_JOIN = os.getenv("WHATSAPP_SANDBOX_JOIN", "join lucky-spoke")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://dealbot-dashboard.onrender.com")
TOKEN_EXPIRY_HOURS = 24

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="DealBot Dashboard")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Database helpers ──────────────────────────────────────────────────────────

def get_user_by_phone(phone: str) -> Optional[dict]:
    with get_db() as conn:
        return db_fetchone(
            conn,
            f"SELECT * FROM users WHERE phone_number = {P}",
            (phone,),
        )


def get_products_for_user(user_id: int) -> list[dict]:
    with get_db() as conn:
        return db_fetchall(
            conn,
            f"""SELECT * FROM tracked_products
               WHERE user_id = {P} AND is_active = 1
               ORDER BY created_at DESC""",
            (user_id,),
        )


def get_product(product_id: int) -> Optional[dict]:
    with get_db() as conn:
        return db_fetchone(
            conn,
            f"SELECT * FROM tracked_products WHERE id = {P}",
            (product_id,),
        )


def get_price_history(product_id: int) -> list[dict]:
    with get_db() as conn:
        return db_fetchall(
            conn,
            f"""SELECT price, recorded_at FROM price_history
               WHERE product_id = {P}
               ORDER BY recorded_at ASC
               LIMIT 60""",
            (product_id,),
        )


def get_all_users_summary() -> list[dict]:
    with get_db() as conn:
        return db_fetchall(
            conn,
            f"""SELECT u.phone_number,
                      COUNT(p.id) as product_count,
                      u.created_at
               FROM users u
               LEFT JOIN tracked_products p ON p.user_id = u.id AND p.is_active = 1
               GROUP BY u.id
               ORDER BY u.created_at DESC""",
        )


def delete_product(product_id: int) -> bool:
    with get_db() as conn:
        db_execute(
            conn,
            f"UPDATE tracked_products SET is_active = 0 WHERE id = {P}",
            (product_id,),
        )
    return True


def update_target_price(product_id: int, target_price: float) -> bool:
    with get_db() as conn:
        db_execute(
            conn,
            f"UPDATE tracked_products SET target_price = {P} WHERE id = {P}",
            (target_price, product_id),
        )
    return True


# ── Template helpers ──────────────────────────────────────────────────────────

def fmt_price(value) -> str:
    if value is None:
        return "—"
    return f"${value:,.2f}"


def fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = value
        return dt.strftime("%b %d, %Y %H:%M")
    except Exception:
        return str(value)


def price_status(current, target) -> str:
    """Return CSS class for price badge."""
    if current is None or target is None:
        return "neutral"
    if current <= target:
        return "deal"
    if current <= target * 1.1:
        return "close"
    return "high"


templates.env.filters["fmt_price"] = fmt_price
templates.env.filters["fmt_date"] = fmt_date
templates.env.globals["whatsapp_number"] = WHATSAPP_NUMBER
templates.env.globals["whatsapp_sandbox_join"] = WHATSAPP_SANDBOX_JOIN
templates.env.globals["now"] = datetime.utcnow


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page – explains DealBot and shows WhatsApp CTA."""
    stats = {"total_users": 0, "total_products": 0}
    try:
        with get_db() as conn:
            row = db_fetchone(conn, "SELECT COUNT(*) AS cnt FROM users")
            stats["total_users"] = row["cnt"] if row else 0
            row = db_fetchone(
                conn,
                "SELECT COUNT(*) AS cnt FROM tracked_products WHERE is_active = 1",
            )
            stats["total_products"] = row["cnt"] if row else 0
    except Exception:
        pass

    return templates.TemplateResponse(
        "landing.html",
        {"request": request, "stats": stats},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, phone: str = ""):
    """User dashboard – shows tracked products for a phone number."""
    user = None
    products = []
    error = None

    if phone:
        user = get_user_by_phone(phone)
        if user:
            products = get_products_for_user(user["id"])
            for p in products:
                p["status"] = price_status(p.get("current_price"), p.get("target_price"))
                p["savings"] = (
                    (p["current_price"] - p["target_price"])
                    if p.get("current_price") and p.get("target_price")
                    else None
                )
        else:
            error = f"No se encontró ningún usuario con el número {phone}"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "phone": phone,
            "user": user,
            "products": products,
            "error": error,
        },
    )


@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: int):
    """Product detail page with price history chart."""
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    history = get_price_history(product_id)

    chart_labels = [h["recorded_at"][:10] if isinstance(h["recorded_at"], str)
                    else str(h["recorded_at"])[:10] for h in history]
    chart_prices = [h["price"] for h in history]

    with get_db() as conn:
        user_row = db_fetchone(
            conn,
            f"SELECT phone_number FROM users WHERE id = {P}",
            (product["user_id"],),
        )
    user_phone = user_row["phone_number"] if user_row else ""

    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "product": product,
            "history": history,
            "chart_labels": chart_labels,
            "chart_prices": chart_prices,
            "user_phone": user_phone,
            "status": price_status(
                product.get("current_price"), product.get("target_price")
            ),
        },
    )


@app.post("/product/{product_id}/delete")
async def delete_product_route(product_id: int, request: Request):
    """Soft-delete a tracked product."""
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    with get_db() as conn:
        user_row = db_fetchone(
            conn,
            f"SELECT phone_number FROM users WHERE id = {P}",
            (product["user_id"],),
        )
    phone = user_row["phone_number"] if user_row else ""

    delete_product(product_id)
    return RedirectResponse(url=f"/dashboard?phone={phone}", status_code=303)


@app.post("/product/{product_id}/target")
async def update_target_route(
    product_id: int, target_price: float = Form(...)
):
    """Update target price for a product."""
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    update_target_price(product_id, target_price)
    return RedirectResponse(url=f"/product/{product_id}", status_code=303)


# ── HTMX partial: product row ─────────────────────────────────────────────────


@app.get("/partials/product-row/{product_id}", response_class=HTMLResponse)
async def product_row_partial(request: Request, product_id: int):
    """HTMX partial – single product row (for optimistic UI)."""
    product = get_product(product_id)
    if not product:
        return HTMLResponse("")
    product["status"] = price_status(
        product.get("current_price"), product.get("target_price")
    )
    return templates.TemplateResponse(
        "partials/product_row.html",
        {"request": request, "product": product},
    )


# ── Magic Link helpers ────────────────────────────────────────────────────────


def create_access_token(user_id: int) -> str:
    """Generate a cryptographically secure token and store it."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    with get_db() as conn:
        db_execute(
            conn,
            f"""INSERT INTO access_tokens (user_id, token, expires_at)
                VALUES ({P}, {P}, {P})""",
            (user_id, token, expires_at.isoformat()),
        )
    return token


def validate_token(token: str) -> Optional[dict]:
    """Return token row if valid and not expired, else None."""
    from app.database import USE_POSTGRES
    now_fn = "NOW()" if USE_POSTGRES else "datetime('now')"
    with get_db() as conn:
        row = db_fetchone(
            conn,
            f"""SELECT * FROM access_tokens
                WHERE token = {P}
                  AND expires_at > {now_fn}""",
            (token,),
        )
    return row


def mark_token_used(token: str):
    """Record when the token was first used."""
    with get_db() as conn:
        db_execute(
            conn,
            f"""UPDATE access_tokens
                SET used_at = NOW()
                WHERE token = {P} AND used_at IS NULL""",
            (token,),
        )


# ── Magic Link routes ─────────────────────────────────────────────────────────


class GenerateLinkRequest(BaseModel):
    phone: str


@app.post("/api/generate-link")
async def generate_link(body: GenerateLinkRequest):
    """
    Generate a magic link for a user by phone number.
    Body: {"phone": "+1234567890"}
    Returns: {"url": "...", "expires_in": "24h"}
    """
    phone = body.phone.strip()
    user = get_user_by_phone(phone)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró ningún usuario con el número {phone}",
        )

    token = create_access_token(user["id"])
    url = f"{DASHBOARD_URL}/d/{token}"

    return JSONResponse({
        "url": url,
        "expires_in": f"{TOKEN_EXPIRY_HOURS}h",
        "phone": phone,
    })


@app.get("/d/{token}", response_class=HTMLResponse)
async def magic_link_dashboard(request: Request, token: str):
    """
    Magic link entry point. Validates token and shows the user's dashboard.
    If invalid/expired: shows friendly error page.
    """
    token_row = validate_token(token)

    if not token_row:
        # Token inválido o expirado
        return templates.TemplateResponse(
            "token_error.html",
            {"request": request},
            status_code=410,
        )

    # Mark as used (first use)
    mark_token_used(token)

    user_id = token_row["user_id"]
    with get_db() as conn:
        user = db_fetchone(
            conn,
            f"SELECT * FROM users WHERE id = {P}",
            (user_id,),
        )

    if not user:
        return templates.TemplateResponse(
            "token_error.html",
            {"request": request},
            status_code=410,
        )

    products = get_products_for_user(user_id)
    for p in products:
        p["status"] = price_status(p.get("current_price"), p.get("target_price"))
        p["savings"] = (
            (p["current_price"] - p["target_price"])
            if p.get("current_price") and p.get("target_price")
            else None
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "phone": user["phone_number"],
            "user": user,
            "products": products,
            "error": None,
            "via_magic_link": True,
        },
    )
