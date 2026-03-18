import os
import sqlite3
import random
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
DB_PATH = os.path.join(BASE_DIR, "app.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "images", "products", "uploads")
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "8828b1fdd8413ff1a5b82459d4e9490da05f9d1da85931345344741f42f7e5a7")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

SEED_PRODUCTS = [
    {"name": "Maker Classic Sneakers", "price": 18500, "tag": "Fashion", "image": "https://loremflickr.com/640/640/sneakers,fashion?lock=1", "featured": 1},
    {"name": "Smart Blender Pro", "price": 42000, "tag": "Home", "image": "https://loremflickr.com/640/640/blender,kitchen?lock=2", "featured": 1},
    {"name": "Wireless Earbuds", "price": 26900, "tag": "Electronics", "image": "https://loremflickr.com/640/640/earbuds,headphones?lock=3", "featured": 1},
    {"name": "Organic Glow Set", "price": 12800, "tag": "Beauty", "image": "https://loremflickr.com/640/640/skincare,beauty?lock=4", "featured": 0},
    {"name": "Office Chair Flex", "price": 55000, "tag": "Furniture", "image": "https://loremflickr.com/640/640/office,chair?lock=5", "featured": 0},
    {"name": "Weekend Bag", "price": 21500, "tag": "Travel", "image": "https://loremflickr.com/640/640/duffel,bag,travel?lock=6", "featured": 0},
]

ARTICLES = [
    {
        "title": "How to shop smarter on a budget",
        "excerpt": "A simple guide to picking quality items without overspending.",
        "tag": "Shopping Tips",
    },
    {
        "title": "5 essentials for a better home office",
        "excerpt": "Upgrade your work setup with practical, affordable upgrades.",
        "tag": "Lifestyle",
    },
    {
        "title": "Weekly deals you should not miss",
        "excerpt": "Fresh deals across categories every week.",
        "tag": "Deals",
    },
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now():
    return datetime.now(timezone.utc)


def format_price(value):
    return f"₦{value:,.0f}"


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            tag TEXT NOT NULL,
            image TEXT NOT NULL,
            featured INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            total INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            image TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    product_count = cur.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
    if product_count == 0:
        for p in SEED_PRODUCTS:
            cur.execute(
                "INSERT INTO products (name, price, tag, image, featured, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (p["name"], p["price"], p["tag"], p["image"], p["featured"], utc_now().isoformat()),
            )
    conn.commit()
    conn.close()
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def generate_otp():
    return "".join(str(random.randint(0, 9)) for _ in range(6))

def is_allowed_file(filename):
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS

def save_uploaded_image(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    filename = secure_filename(file_storage.filename)
    if not is_allowed_file(filename):
        return None
    _, ext = os.path.splitext(filename)
    unique_name = f"{uuid.uuid4().hex}{ext.lower()}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_storage.save(os.path.join(UPLOAD_DIR, unique_name))
    return f"uploads/{unique_name}"


def send_otp_email(to_email, code):
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, smtp_from]):
        print(f"OTP for {to_email}: {code}")
        return False, "SMTP config missing"

    msg = EmailMessage()
    msg["Subject"] = "Your Maker OTP"
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.set_content(f"Your verification code is {code}. It expires in 10 minutes.")

    print(f"DEBUG: Starting SMTP connection to {smtp_host}:{smtp_port}...")
    try:
        if smtp_port == 465:
            server_class = smtplib.SMTP_SSL
        else:
            server_class = smtplib.SMTP

        import time
        start_time = time.time()
        with server_class(smtp_host, smtp_port, timeout=10) as server:
            conn_time = time.time() - start_time
            print(f"DEBUG: Connected in {conn_time:.2f}s")
            
            if smtp_port != 465:
                server.starttls()
            
            auth_start = time.time()
            server.login(smtp_user, smtp_pass)
            auth_time = time.time() - auth_start
            print(f"DEBUG: Authenticated in {auth_time:.2f}s")
            
            server.send_message(msg)
            print("DEBUG: Message sent successfully")
        return True, None
    except Exception as exc:
        print(f"SMTP error: {exc}")
        return False, str(exc)


def get_message():
    return request.args.get("msg"), request.args.get("level", "success")


def is_admin_key_valid(key):
    admin_key = os.environ.get("ADMIN_KEY", "")
    return bool(admin_key) and key == admin_key


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("signup", msg="Please sign up to continue.", level="info"))
    
    message, level = get_message()
    conn = get_db()
    # Homepage shows featured products and recent articles
    featured_products = conn.execute("SELECT * FROM products WHERE featured = 1 ORDER BY id DESC LIMIT 4").fetchall()
    conn.close()
    return render_template("index.html", products=featured_products, articles=ARTICLES[:2], message=message, level=level, format_price=format_price, user_name=session.get("user_name"))


@app.route("/shop")
def shop():
    if "user_id" not in session:
        return redirect(url_for("signup", msg="Please sign up to continue.", level="info"))
    
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    message, level = get_message()
    conn = get_db()
    
    if q:
        products = conn.execute("SELECT * FROM products WHERE (name LIKE ? OR tag LIKE ?) ORDER BY featured DESC, id DESC", (f'%{q}%', f'%{q}%')).fetchall()
    elif tag:
        products = conn.execute("SELECT * FROM products WHERE tag LIKE ? ORDER BY featured DESC, id DESC", (f'%{tag}%',)).fetchall()
    else:
        products = conn.execute("SELECT * FROM products ORDER BY featured DESC, id DESC").fetchall()
        
    conn.close()
    return render_template("shop.html", products=products, message=message, level=level, format_price=format_price, query=q)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    if "user_id" not in session:
        return redirect(url_for("signup", msg="Please sign up to view details.", level="info"))
    
    message, level = get_message()
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return redirect(url_for("shop", msg="Product not found.", level="error"))
    
    reviews = conn.execute("SELECT * FROM reviews WHERE product_id = ? ORDER BY id DESC", (product_id,)).fetchall()
    
    # Simple recommendation: other products in same tag
    related = conn.execute("SELECT * FROM products WHERE tag = ? AND id != ? LIMIT 4", (product["tag"], product_id)).fetchall()
    
    conn.close()
    return render_template("product_detail.html", product=product, reviews=reviews, related=related, message=message, level=level, format_price=format_price)


@app.route("/submit-review/<int:product_id>", methods=["POST"])
def submit_review(product_id):
    if "user_id" not in session:
        return redirect(url_for("login", msg="Please log in to review.", level="error"))
    
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()
    user_name = session.get("user_name", "Anonymous")

    if not rating or not comment:
        return redirect(url_for("product_detail", product_id=product_id, msg="Please provide rating and comment.", level="error"))

    conn = get_db()
    conn.execute(
        "INSERT INTO reviews (product_id, user_name, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
        (product_id, user_name, rating, comment, utc_now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return redirect(url_for("product_detail", product_id=product_id, msg="Review submitted. Thank you!"))


@app.route("/journal")
def journal():
    if "user_id" not in session:
        return redirect(url_for("signup", msg="Please sign up to continue.", level="info"))
    
    message, level = get_message()
    return render_template("journal.html", articles=ARTICLES, message=message, level=level)


@app.route("/cart")
def cart():
    message, level = get_message()
    return render_template("cart.html", message=message, level=level)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        cart_json = request.form.get("cart_json", "")

        if not all([full_name, email, phone, address, city, cart_json]):
            return redirect(url_for("checkout", msg="Please fill in all fields.", level="error"))

        try:
            items = json.loads(cart_json)
        except json.JSONDecodeError:
            return redirect(url_for("cart", msg="Cart data invalid. Please try again.", level="error"))

        if not items:
            return redirect(url_for("cart", msg="Your cart is empty.", level="error"))

        total = sum(item["price"] * item["qty"] for item in items)

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (full_name, email, phone, address, city, total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (full_name, email, phone, address, city, total, utc_now().isoformat()),
        )
        order_id = cur.lastrowid
        for item in items:
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, name, price, qty, image) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, item["id"], item["name"], item["price"], item["qty"], item["image"]),
            )
        conn.commit()
        conn.close()

        return redirect(url_for("order_success", order_id=order_id))

    message, level = get_message()
    return render_template("checkout.html", message=message, level=level)


@app.route("/order-success/<int:order_id>")
def order_success(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    conn.close()
    return render_template("order_success.html", order=order, items=items, format_price=format_price)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not full_name or not email or not password:
            return redirect(url_for("signup", msg="Please fill in all fields.", level="error"))

        conn = get_db()
        cur = conn.cursor()
        existing = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            return redirect(url_for("login", msg="Email already registered. Please log in.", level="error"))

        password_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash, verified, created_at) VALUES (?, ?, ?, 0, ?)",
            (full_name, email, password_hash, utc_now().isoformat()),
        )

        code = generate_otp()
        expires_at = (utc_now() + timedelta(minutes=10)).isoformat()
        cur.execute("INSERT INTO otps (email, code, expires_at) VALUES (?, ?, ?)", (email, code, expires_at))
        conn.commit()
        conn.close()

        sent, err = send_otp_email(email, code)
        if sent:
            msg = "OTP sent to your email."
        else:
            msg = "OTP not sent. Check server log for SMTP error."
            if err == "SMTP config missing":
                msg = "SMTP config missing. OTP printed in server logs."
        return redirect(url_for("verify_otp", email=email, msg=msg, level="error" if not sent else "success"))

    message, level = get_message()
    return render_template("signup.html", message=message, level=level)


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = request.values.get("email", "").strip().lower()
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not email:
            return redirect(url_for("signup", msg="No signup session found. Please sign up again.", level="error"))

        conn = get_db()
        cur = conn.cursor()
        otp_row = cur.execute(
            "SELECT code, expires_at FROM otps WHERE email = ? ORDER BY id DESC LIMIT 1",
            (email,),
        ).fetchone()

        if not otp_row:
            conn.close()
            return redirect(url_for("verify_otp", email=email, msg="No OTP found. Please resend.", level="error"))

        expires_at = datetime.fromisoformat(otp_row["expires_at"])
        if utc_now() > expires_at:
            conn.close()
            return redirect(url_for("verify_otp", email=email, msg="OTP expired. Please resend.", level="error"))

        if code != otp_row["code"]:
            conn.close()
            return redirect(url_for("verify_otp", email=email, msg="Invalid OTP. Try again.", level="error"))

        cur.execute("UPDATE users SET verified = 1 WHERE email = ?", (email,))
        cur.execute("DELETE FROM otps WHERE email = ?", (email,))
        
        user = cur.execute("SELECT id, full_name FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        
        conn.commit()
        conn.close()

        return redirect(url_for("index", msg="Account verified. Welcome!"))

    message, level = get_message()
    return render_template("verify_otp.html", email=email, message=message, level=level)


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    email = request.form.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("signup", msg="No signup session found. Please sign up again.", level="error"))

    conn = get_db()
    cur = conn.cursor()
    code = generate_otp()
    expires_at = (utc_now() + timedelta(minutes=10)).isoformat()
    cur.execute("INSERT INTO otps (email, code, expires_at) VALUES (?, ?, ?)", (email, code, expires_at))
    conn.commit()
    conn.close()

    sent, err = send_otp_email(email, code)
    if sent:
        msg = "New OTP sent to your email."
    else:
        msg = "OTP not sent. Check server log for SMTP error."
        if err == "SMTP config missing":
            msg = "SMTP config missing. OTP printed in server logs."
    return redirect(url_for("verify_otp", email=email, msg=msg, level="error" if not sent else "success"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cur = conn.cursor()
        user = cur.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return redirect(url_for("login", msg="Invalid login details.", level="error"))

        if user["verified"] == 0:
            return redirect(url_for("verify_otp", email=email, msg="Please verify your OTP to continue.", level="error"))

        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        return redirect(url_for("index", msg="Welcome back!"))

    message, level = get_message()
    return render_template("login.html", message=message, level=level)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login", msg="You have been logged out."))


@app.route("/admin", methods=["GET", "POST"])
def admin_home():
    key = request.values.get("key", "")
    if request.method == "POST":
        key = request.form.get("key", "")
        if is_admin_key_valid(key):
            return redirect(url_for("admin_home", key=key))
        return render_template("admin_login.html", error="Invalid admin key")

    if not is_admin_key_valid(key):
        return render_template("admin_login.html", error=None)

    conn = get_db()
    product_count = conn.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
    order_count = conn.execute("SELECT COUNT(*) AS count FROM orders").fetchone()["count"]
    conn.close()
    return render_template("admin_dashboard.html", key=key, product_count=product_count, order_count=order_count)


@app.route("/admin/products")
def admin_products():
    key = request.args.get("key", "")
    if not is_admin_key_valid(key):
        return redirect(url_for("admin_home"))

    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_products.html", key=key, products=products, format_price=format_price)


@app.route("/admin/products/new", methods=["GET", "POST"])
def admin_product_new():
    key = request.values.get("key", "")
    if not is_admin_key_valid(key):
        return redirect(url_for("admin_home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = int(request.form.get("price", "0"))
        tag = request.form.get("tag", "").strip()
        image = request.form.get("image", "").strip()
        image_url = request.form.get("image_url", "").strip()
        featured = 1 if request.form.get("featured") == "on" else 0
        uploaded = save_uploaded_image(request.files.get("image_file"))
        if image_url:
            image = image_url
        elif uploaded:
            image = uploaded
        if not image:
            image = "sneakers.png"

        conn = get_db()
        conn.execute(
            "INSERT INTO products (name, price, tag, image, featured, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, price, tag, image, featured, utc_now().isoformat()),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_products", key=key))

    images = get_product_images()
    return render_template("admin_product_form.html", key=key, product=None, images=images)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
def admin_product_edit(product_id):
    key = request.values.get("key", "")
    if not is_admin_key_valid(key):
        return redirect(url_for("admin_home"))

    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = int(request.form.get("price", "0"))
        tag = request.form.get("tag", "").strip()
        image = product["image"]
        image_choice = request.form.get("image", "").strip()
        image_url = request.form.get("image_url", "").strip()
        featured = 1 if request.form.get("featured") == "on" else 0
        uploaded = save_uploaded_image(request.files.get("image_file"))
        if image_url:
            image = image_url
        elif uploaded:
            image = uploaded
        elif image_choice:
            image = image_choice
        conn.execute(
            "UPDATE products SET name = ?, price = ?, tag = ?, image = ?, featured = ? WHERE id = ?",
            (name, price, tag, image, featured, product_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_products", key=key))

    conn.close()
    images = get_product_images()
    return render_template("admin_product_form.html", key=key, product=product, images=images)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
def admin_product_delete(product_id):
    key = request.form.get("key", "")
    if not is_admin_key_valid(key):
        return redirect(url_for("admin_home"))

    conn = get_db()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_products", key=key))


@app.route("/admin/orders")
def admin_orders():
    key = request.args.get("key", "")
    if not is_admin_key_valid(key):
        return redirect(url_for("admin_home"))

    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    items = conn.execute("SELECT * FROM order_items ORDER BY order_id DESC").fetchall()
    conn.close()
    return render_template("admin_orders.html", key=key, orders=orders, items=items, format_price=format_price)


def get_product_images():
    img_dir = os.path.join(BASE_DIR, "static", "images", "products")
    if not os.path.isdir(img_dir):
        return []
    images = [f for f in os.listdir(img_dir) if f.lower().endswith(('.svg', '.png', '.jpg', '.jpeg', '.webp'))]
    uploads_dir = os.path.join(img_dir, "uploads")
    if os.path.isdir(uploads_dir):
        for f in os.listdir(uploads_dir):
            if os.path.splitext(f.lower())[1] in ALLOWED_EXTENSIONS:
                images.append(f"uploads/{f}")
@app.route("/test-images")
def test_images():
    return render_template("test_images.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
