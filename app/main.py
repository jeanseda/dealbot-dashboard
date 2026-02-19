"""
DealBot Dashboard - FastAPI Web App
Tracks Amazon deals via WhatsApp bot.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# DB path – use env var or fallback to deal-tracker project
DB_PATH = Path(
    os.getenv(
        "DEAL_TRACKER_DB",
        str(Path.home() / ".openclaw/workspace/deal-tracker/deal_tracker.db"),
    )
)

WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "+14155238886")
WHATSAPP_SANDBOX_JOIN = os.getenv("WHATSAPP_SANDBOX_JOIN", "join lucky-spoke")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="DealBot Dashboard")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Database helpers ──────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_phone(phone: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone_number = ?", (phone,)
        ).fetchone()
        return dict(row) if row else None


def get_products_for_user(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM tracked_products
               WHERE user_id = ? AND is_active = 1
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_product(product_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tracked_products WHERE id = ?", (product_id,)
        ).fetchone()
        return dict(row) if row else None


def get_price_history(product_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT price, recorded_at FROM price_history
               WHERE product_id = ?
               ORDER BY recorded_at ASC
               LIMIT 60""",
            (product_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_users_summary() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.phone_number,
                      COUNT(p.id) as product_count,
                      u.created_at
               FROM users u
               LEFT JOIN tracked_products p ON p.user_id = u.id AND p.is_active = 1
               GROUP BY u.id
               ORDER BY u.created_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def delete_product(product_id: int) -> bool:
    with get_db() as conn:
        conn.execute(
            "UPDATE tracked_products SET is_active = 0 WHERE id = ?", (product_id,)
        )
        conn.commit()
        return True


def update_target_price(product_id: int, target_price: float) -> bool:
    with get_db() as conn:
        conn.execute(
            "UPDATE tracked_products SET target_price = ? WHERE id = ?",
            (target_price, product_id),
        )
        conn.commit()
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
            stats["total_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            stats["total_products"] = conn.execute(
                "SELECT COUNT(*) FROM tracked_products WHERE is_active = 1"
            ).fetchone()[0]
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
            # Attach price status to each product
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

    # Build chart data
    chart_labels = [h["recorded_at"][:10] for h in history]
    chart_prices = [h["price"] for h in history]

    # Get user phone for back-link
    with get_db() as conn:
        user_row = conn.execute(
            "SELECT phone_number FROM users WHERE id = ?", (product["user_id"],)
        ).fetchone()
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
        user_row = conn.execute(
            "SELECT phone_number FROM users WHERE id = ?", (product["user_id"],)
        ).fetchone()
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
