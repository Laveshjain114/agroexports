from flask import Flask, render_template, request, redirect, session, g
from werkzeug.security import check_password_hash
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"


# =============================
# DATABASE CONNECTION
# =============================

def get_db():
    if "db" not in g:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise Exception("DATABASE_URL not set")
        g.db = psycopg2.connect(database_url)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# =============================
# AUTO CREATE TABLES
# =============================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
        name VARCHAR(200),
        description TEXT,
        packaging TEXT,
        moq VARCHAR(100)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_specifications (
        id SERIAL PRIMARY KEY,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        spec_name VARCHAR(100),
        spec_value VARCHAR(200)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_packaging (
        id SERIAL PRIMARY KEY,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        packaging_type VARCHAR(100),
        weight VARCHAR(100),
        container_20ft VARCHAR(100),
        container_40ft VARCHAR(100)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_images (
        id SERIAL PRIMARY KEY,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        image_name VARCHAR(200)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inquiries (
        id SERIAL PRIMARY KEY,
        product_id INTEGER REFERENCES products(id),
        buyer_name VARCHAR(150),
        email VARCHAR(150),
        country VARCHAR(150),
        quantity VARCHAR(100),
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE,
        password TEXT
    );
    """)

    conn.commit()
    cur.close()


# =============================
# PUBLIC ROUTES
# =============================

@app.route("/")
def home():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories")
    categories = cur.fetchall()
    cur.close()
    return render_template("home.html", categories=categories)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        return redirect("/contact")
    return render_template("contact.html")


@app.route("/category/<int:category_id>")
def category_products(category_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE category_id = %s", (category_id,))
    products = cur.fetchall()
    cur.close()
    return render_template("products.html", products=products)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()

    cur.execute("""
        SELECT spec_name, spec_value
        FROM product_specifications
        WHERE product_id = %s
    """, (product_id,))
    specifications = cur.fetchall()

    cur.close()

    return render_template(
        "product_detail.html",
        product=product,
        specifications=specifications,
        packaging=[],
        images=[]
    )


# =============================
# ADMIN AUTH
# =============================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM admin WHERE username = %s",
                    (request.form["username"],))
        admin = cur.fetchone()
        cur.close()

        if admin and check_password_hash(admin[2], request.form["password"]):
            session["admin_logged_in"] = True
            return redirect("/admin/dashboard")
        else:
            return "Invalid Credentials"

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM categories")
    total_categories = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    cur.close()

    return render_template(
        "admin_dashboard.html",
        total_categories=total_categories,
        total_products=total_products
    )


# =============================
# PRODUCTION INITIALIZATION
# =============================

with app.app_context():
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print("DB init error:", e)