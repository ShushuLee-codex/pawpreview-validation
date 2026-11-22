import os
import re
import secrets
from collections import Counter
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

raw_db = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if raw_db.startswith("postgres://"):
    raw_db = "postgresql://" + raw_db[len("postgres://"):]

engine_kwargs = {"pool_pre_ping": True}
if raw_db.startswith("postgresql"):
    engine_kwargs["pool_size"] = 2
    engine_kwargs["max_overflow"] = 2
    if "sslmode=" not in raw_db and "localhost" not in raw_db and "127.0.0.1" not in raw_db:
        sep = "&" if "?" in raw_db else "?"
        raw_db = raw_db + sep + "sslmode=require"

engine = create_engine(raw_db, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    store_url: Mapped[str] = mapped_column(String(500), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_orders: Mapped[str] = mapped_column(String(40), nullable=False)
    pay_range: Mapped[str] = mapped_column(String(40), nullable=False)
    wanted_feature: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


Base.metadata.create_all(engine)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

CATEGORIES = [
    ("custom_portraits", "Custom pet portraits"),
    ("mugs", "Mugs and drinkware"),
    ("blankets_pillows", "Blankets, pillows, or home goods"),
    ("apparel", "T-shirts or apparel"),
    ("mixed_pod", "Mixed custom / POD pet gifts"),
    ("other", "Other pet custom products"),
]
ORDER_RANGES = [
    ("0-20", "0–20"),
    ("21-100", "21–100"),
    ("101-500", "101–500"),
    ("501-2000", "501–2,000"),
    ("2000+", "2,000+"),
]
PAY_RANGES = [
    ("free_only", "$0 / I would only use a free plan"),
    ("9-19", "$9–19"),
    ("19-49", "$19–49"),
    ("49+", "$49+"),
]
CATEGORY_LABELS = dict(CATEGORIES)
ORDER_LABELS = dict(ORDER_RANGES)
PAY_LABELS = dict(PAY_RANGES)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_store_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or "." not in parsed.netloc:
        return ""
    if len(value) > 500:
        return ""
    return value


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_ok"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


@app.get("/health")
def health():
    return {"ok": True}, 200


@app.get("/")
def index():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return render_template(
        "index.html",
        categories=CATEGORIES,
        order_ranges=ORDER_RANGES,
        pay_ranges=PAY_RANGES,
        csrf=session["csrf"],
    )


@app.post("/apply")
def apply():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    # Honeypot
    if (request.form.get("company_website") or "").strip():
        return redirect(url_for("index", sent=1) + "#trial")

    if request.form.get("csrf") != session.get("csrf"):
        flash("Please try again.")
        return redirect(url_for("index") + "#trial"), 303

    store_url = normalize_store_url(request.form.get("store_url", ""))
    email = (request.form.get("email") or "").strip().lower()
    category = (request.form.get("category") or "").strip()
    monthly_orders = (request.form.get("monthly_orders") or "").strip()
    pay_range = (request.form.get("pay_range") or "").strip()
    wanted_feature = (request.form.get("wanted_feature") or "").strip()[:2000]

    errors = []
    if not store_url:
        errors.append("Enter a valid store URL.")
    if not email or not EMAIL_RE.match(email) or len(email) > 320:
        errors.append("Enter a valid email address.")
    if category not in CATEGORY_LABELS:
        errors.append("Choose your main product type.")
    if monthly_orders not in ORDER_LABELS:
        errors.append("Choose a monthly order range.")
    if pay_range not in PAY_LABELS:
        errors.append("Choose a monthly price range.")

    if errors:
        for e in errors:
            flash(e)
        return redirect(url_for("index") + "#trial"), 303

    with SessionLocal() as db:
        db.add(
            Submission(
                store_url=store_url,
                email=email,
                category=category,
                monthly_orders=monthly_orders,
                pay_range=pay_range,
                wanted_feature=wanted_feature,
            )
        )
        db.commit()

    session["csrf"] = secrets.token_urlsafe(24)
    return redirect(url_for("index", sent=1) + "#trial")


@app.get("/admin/login")
def admin_login():
    if session.get("admin_ok"):
        return redirect(url_for("admin"))
    return render_template("admin_login.html")


@app.post("/admin/login")
def admin_login_post():
    password = request.form.get("password") or ""
    if not ADMIN_PASSWORD or not secrets.compare_digest(password, ADMIN_PASSWORD):
        flash("That password did not match.")
        return redirect(url_for("admin_login")), 303
    session["admin_ok"] = True
    session.permanent = True
    return redirect(url_for("admin"))


@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@require_admin
def admin():
    include_test = request.args.get("include_test") == "1"
    with SessionLocal() as db:
        rows = db.scalars(
            select(Submission)
            .where(Submission.is_deleted.is_(False))
            .order_by(Submission.created_at.desc())
        ).all()
    visible = [r for r in rows if include_test or not r.is_test]
    live = [r for r in rows if not r.is_test]
    pay_counts = Counter(r.pay_range for r in live)
    cat_counts = Counter(r.category for r in live)
    order_counts = Counter(r.monthly_orders for r in live)
    willing = len([r for r in live if r.pay_range != "free_only"])
    return render_template(
        "admin.html",
        rows=visible,
        total_live=len(live),
        total_test=len([r for r in rows if r.is_test]),
        willing=willing,
        free_only=pay_counts.get("free_only", 0),
        pay_counts=pay_counts,
        cat_counts=cat_counts,
        order_counts=order_counts,
        pay_labels=PAY_LABELS,
        category_labels=CATEGORY_LABELS,
        order_labels=ORDER_LABELS,
        include_test=include_test,
    )


@app.post("/admin/submissions/<int:sid>/mark-test")
@require_admin
def mark_test(sid: int):
    with SessionLocal() as db:
        row = db.get(Submission, sid)
        if not row or row.is_deleted:
            abort(404)
        row.is_test = True
        db.commit()
    return redirect(url_for("admin", include_test="1"))


@app.post("/admin/submissions/<int:sid>/delete")
@require_admin
def delete_submission(sid: int):
    with SessionLocal() as db:
        row = db.get(Submission, sid)
        if not row:
            abort(404)
        row.is_deleted = True
        db.commit()
    return redirect(url_for("admin", include_test=("1" if request.args.get("include_test") == "1" else None)))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
