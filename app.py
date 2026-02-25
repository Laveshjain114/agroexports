from flask import Flask, render_template, request, redirect, session
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'



# ----------------------------
# PUBLIC ROUTES
# ----------------------------

@app.route('/')
def home():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM categories")
    categories = cur.fetchall()
    cur.close()
    return render_template("home.html", categories=categories)

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        # For now we just print (you can later store in DB)
        print(name, email, subject, message)

        return redirect('/contact')

    return render_template("contact.html")

@app.route('/category/<int:category_id>')
def category_products(category_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products WHERE category_id = %s", (category_id,))
    products = cur.fetchall()
    cur.close()
    return render_template("products.html", products=products)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    cur = mysql.connection.cursor()

    # Product
    cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()

    # Specifications
    cur.execute("""
        SELECT spec_name, spec_value
        FROM product_specifications
        WHERE product_id = %s
    """, (product_id,))
    specifications = cur.fetchall()

    # Packaging
    cur.execute("""
        SELECT packaging_type, weight, container_20ft, container_40ft
        FROM product_packaging
        WHERE product_id = %s
    """, (product_id,))
    packaging = cur.fetchall()

    # Images
    cur.execute("""
        SELECT image_name
        FROM product_images
        WHERE product_id = %s
    """, (product_id,))
    images = cur.fetchall()

    cur.close()

    return render_template(
        "product_detail.html",
        product=product,
        specifications=specifications,
        packaging=packaging,
        images=images
    )


@app.route('/inquiry/<int:product_id>', methods=['GET', 'POST'])
def inquiry(product_id):
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        country = request.form['country']
        quantity = request.form['quantity']
        message = request.form['message']

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO inquiries
            (product_id, buyer_name, email, country, quantity, message)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (product_id, name, email, country, quantity, message))

        mysql.connection.commit()
        cur.close()

        return redirect('/')

    return render_template("inquiry.html", product_id=product_id)


# ----------------------------
# ADMIN AUTH
# ----------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE username = %s", (username,))
        admin = cur.fetchone()
        cur.close()

        if admin and check_password_hash(admin[2], password):
            session['admin_logged_in'] = True
            return redirect('/admin/dashboard')
        else:
            return "Invalid Credentials"

    return render_template("admin_login.html")


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/')


# ----------------------------
# ADMIN DASHBOARD
# ----------------------------

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM categories")
    total_categories = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM inquiries")
    total_inquiries = cur.fetchone()[0]

    cur.close()

    return render_template(
        "admin_dashboard.html",
        total_categories=total_categories,
        total_products=total_products,
        total_inquiries=total_inquiries
    )


@app.route('/admin/inquiries')
def view_inquiries():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM inquiries ORDER BY created_at DESC")
    inquiries = cur.fetchall()
    cur.close()

    return render_template("admin_inquiries.html", inquiries=inquiries)


# ----------------------------
# ADD PRODUCT (Enterprise)
# ----------------------------

@app.route('/admin/add-product', methods=['GET', 'POST'])
def add_product():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM categories")
    categories = cur.fetchall()

    if request.method == 'POST':

        name = request.form['name']
        category_id = request.form['category_id']
        description = request.form['description']
        packaging_general = request.form['packaging']
        moq = request.form['moq']

        # Insert Product (no main image anymore, gallery only)
        cur.execute("""
            INSERT INTO products
            (category_id, name, description, packaging, moq)
            VALUES (%s, %s, %s, %s, %s)
        """, (category_id, name, description, packaging_general, moq))

        product_id = cur.lastrowid

        # Insert Specifications
        spec_names = request.form.getlist('spec_name[]')
        spec_values = request.form.getlist('spec_value[]')

        for spec_name, spec_value in zip(spec_names, spec_values):
            if spec_name and spec_value:
                cur.execute("""
                    INSERT INTO product_specifications
                    (product_id, spec_name, spec_value)
                    VALUES (%s, %s, %s)
                """, (product_id, spec_name, spec_value))

        # Insert Packaging Rows
        pack_types = request.form.getlist('pack_type[]')
        weights = request.form.getlist('weight[]')
        container20 = request.form.getlist('container20[]')
        container40 = request.form.getlist('container40[]')

        for p, w, c20, c40 in zip(pack_types, weights, container20, container40):
            if p and w:
                cur.execute("""
                    INSERT INTO product_packaging
                    (product_id, packaging_type, weight, container_20ft, container_40ft)
                    VALUES (%s, %s, %s, %s, %s)
                """, (product_id, p, w, c20, c40))

        # Insert Multiple Images
        images = request.files.getlist('images')

        for image in images:
            if image and image.filename != '':
                filename = secure_filename(image.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)

                cur.execute("""
                    INSERT INTO product_images (product_id, image_name)
                    VALUES (%s, %s)
                """, (product_id, filename))

        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    cur.close()
    return render_template("admin_add_product.html", categories=categories)


# ----------------------------
# DELETE PRODUCT
# ----------------------------

@app.route('/admin/delete-product/<int:product_id>')
def delete_product(product_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    mysql.connection.commit()
    cur.close()

    return redirect('/admin/dashboard')


# ----------------------------

with app.app_context():
    try:
        init_db()
    except Exception as e:
        print("DB init error:", e)