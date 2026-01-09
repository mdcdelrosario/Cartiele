from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename
from flask import request, jsonify, session
app = Flask(__name__)
app.secret_key = 'secret123'

# -------------------- MySQL CONFIG --------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'spare_db'
mysql = MySQL(app)

# -------------------- UPLOAD CONFIG --------------------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

UPLOAD_FOLDER = "static/review_uploads/"
ALLOWED_IMAGE = {"png", "jpg", "jpeg"}
ALLOWED_VIDEO = {"mp4", "mov", "avi"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------- USER REGISTRATION --------------------
import re
from werkzeug.security import generate_password_hash

@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = {}
    form_data = {}
    registration_success = False

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        profile_img = request.files.get('profile_img')

        form_data = {"name": name, "email": email}

        # Validation
        if not name:
            errors['name'] = "Name is required"
        if not email:
            errors['email'] = "Email is required"
        if not password:
            errors['password'] = "Password is required"
        else:
            # Password must be at least 8 characters, contain at least 1 letter and 1 number
            if len(password) < 8:
                errors['password'] = "Password must be at least 8 characters"
            elif not re.search(r'[A-Za-z]', password):
                errors['password'] = "Password must contain at least one letter"
            elif not re.search(r'\d', password):
                errors['password'] = "Password must contain at least one number"

        # Check if email exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", [email])
        if cur.fetchone():
            errors['email'] = "Email already registered"
        cur.close()

        # Handle profile image
        profile_img_path = None
        if profile_img and profile_img.filename != "":
            ext = profile_img.filename.rsplit(".", 1)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors['profile_img'] = "Invalid image format"
            else:
                filename = secure_filename(profile_img.filename)
                upload_folder = os.path.join(app.root_path, 'static', 'profile_imgs')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, filename)
                profile_img.save(file_path)
                profile_img_path = f"profile_imgs/{filename}"

        # If no errors, insert user
        if not errors:
            hashed_password = generate_password_hash(password)
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users (name, email, password, profile_img) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, profile_img_path)
            )
            mysql.connection.commit()
            cur.close()
            registration_success = True
            form_data = {}  # clear form after success

    # Always pass variables to template
    return render_template('register.html', errors=errors, form_data=form_data, registration_success=registration_success)

# -------------------- USER LOGIN --------------------
from werkzeug.security import check_password_hash

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # for inline error messages

    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, password, status FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user:
            user_id, user_name, user_password, user_status = user

            # Always check password first
            if check_password_hash(user_password, password):
                # Then check status
                if str(user_status).strip().lower() != 'active':
                    error = "⚠️ Account is inactive. Please contact admin."
                else:
                    # Login successful
                    session['user_id'] = user_id
                    session['user_name'] = user_name
                    return redirect(url_for('catalog'))
            else:
                error = "❌ Invalid credentials."
        else:
            error = "❌ Invalid credentials."

    return render_template('login.html', error=error)



# -------------------- USER LOGOUT --------------------

import random
import string


# -------------------- FORGOT PASSWORD --------------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None

    if request.method == 'POST':
        email = request.form['email'].strip()
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", [email])
        user = cur.fetchone()

        if user:
            user_id = user[0]

            # Generate temporary password
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            hashed_temp = generate_password_hash(temp_password)

            # Update password in DB
            cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_temp, user_id))
            mysql.connection.commit()
            cur.close()

            # Show temporary password to user (for demo purposes)
            message = f"Your temporary password is: {temp_password}. Please login and change it immediately."
        else:
            message = "❌ Email not found."

    return render_template('forgot_password.html', message=message)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash('Logged out.')
    return redirect(url_for('login'))

# -------------------- ADMIN LOGIN --------------------
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            flash('✅ Admin login successful!')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('❌ Invalid admin credentials!')
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')

# -------------------- ADMIN DASHBOARD --------------------
from datetime import datetime

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()

    # PRODUCTS
    cur.execute("SELECT * FROM products WHERE is_active = 1")

    products = cur.fetchall()

    # USERS
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    # PENDING / ACTIVE ORDERS
    cur.execute("""
    SELECT orders.id, users.name, users.email, orders.total, orders.status, orders.created_at
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE orders.status NOT IN ('Delivered', 'Declined')
    ORDER BY orders.created_at DESC
    """)


    pending_orders = cur.fetchall()
# After fetching products
    products_with_variations = []
    for p in products:
        cur.execute("""
            SELECT pvo.value, pvo.stock, pvo.extra_price
            FROM product_variations pv
            JOIN product_variation_options pvo ON pv.id = pvo.variation_id
            WHERE pv.product_id=%s
        """, [p[0]])
        variations = cur.fetchall()  # list of tuples (value, stock, extra_price)
        products_with_variations.append({
            "product": p,
            "variations": variations
        })

    # 📅 SELECTED DATE (from calendar)
    selected_date = request.args.get("date")

    if not selected_date:
        selected_date = datetime.today().strftime("%Y-%m-%d")

    # DAILY / WEEKLY / MONTHLY SALES (BASED ON SELECTED DATE)
    cur.execute("""
    SELECT 
        COALESCE(SUM(
            CASE 
                WHEN DATE(STR_TO_DATE(created_at, '%%Y-%%m-%%d %%H:%%i:%%s')) = %s
                THEN total
            END
        ), 0),

        COALESCE(SUM(
            CASE 
                WHEN YEARWEEK(
                    STR_TO_DATE(created_at, '%%Y-%%m-%%d %%H:%%i:%%s'), 1
                ) = YEARWEEK(%s, 1)
                THEN total
            END
        ), 0),

        COALESCE(SUM(
            CASE 
                WHEN MONTH(STR_TO_DATE(created_at, '%%Y-%%m-%%d %%H:%%i:%%s')) = MONTH(%s)
                 AND YEAR(STR_TO_DATE(created_at, '%%Y-%%m-%%d %%H:%%i:%%s')) = YEAR(%s)
                THEN total
            END
        ), 0)
    FROM orders
    WHERE LOWER(status) LIKE '%%deliver%%'
""", (selected_date, selected_date, selected_date, selected_date))


    daily_sales, weekly_sales, monthly_sales = cur.fetchone()

    cur.close()

    return render_template(
    'admin_dashboard.html',
    products=products_with_variations,
    users=users,
    pending_orders=pending_orders,
    daily_sales=daily_sales,
    weekly_sales=weekly_sales,
    monthly_sales=monthly_sales,
    selected_date=selected_date
)
from flask import request, jsonify

@app.route("/admin/update_user_status", methods=["POST"])
def update_user_status():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.get_json()
    user_id = data.get("user_id")
    status = data.get("status")

    if status not in ["active", "inactive"]:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE users SET status=%s WHERE id=%s", (status, user_id))
        mysql.connection.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        cur.close()

@app.route("/admin/sales_summary")
def sales_summary():
    selected_date = request.args.get("date")
    if not selected_date:
        selected_date = datetime.today().strftime("%Y-%m-%d")

    cur = mysql.connection.cursor()

    # Calculate sales for the selected date
    cur.execute("""
        SELECT
            IFNULL(SUM(CASE WHEN DATE(created_at) = %s THEN total ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN YEARWEEK(created_at, 1) = YEARWEEK(%s, 1) THEN total ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN MONTH(created_at) = MONTH(%s) AND YEAR(created_at) = YEAR(%s) THEN total ELSE 0 END), 0)
        FROM orders
        WHERE LOWER(status) LIKE '%%deliver%%'
    """, (selected_date, selected_date, selected_date, selected_date))

    daily, weekly, monthly = cur.fetchone()
    cur.close()

    return {
        "daily": float(daily),
        "weekly": float(weekly),
        "monthly": float(monthly)
    }


@app.route('/admin/update_order_status_ajax', methods=['POST'])
def update_order_status_ajax():
    if not session.get('admin'):
        return {"success": False}, 403

    data = request.get_json()
    order_id = data.get("order_id")
    status = data.get("status")

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE orders SET status = %s WHERE id = %s",
        (status, order_id)
    )
    mysql.connection.commit()
    cur.close()

    return {"success": True}

@app.route('/admin/decline_order', methods=['POST'])
def decline_order():
    if not session.get('admin'):
        return {"success": False}, 403

    data = request.get_json()
    order_id = data.get("order_id")
    reason = data.get("reason")

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE orders
        SET status = 'Declined',
            decline_reason = %s
        WHERE id = %s
    """, (reason, order_id))

    mysql.connection.commit()
    cur.close()

    return {"success": True}
@app.route('/review/<int:order_id>', methods=['GET', 'POST'])
def add_review(order_id):
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # Get all products in the order
    cur.execute("""
        SELECT o.user_id, oi.product_id, p.name
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.id = %s AND o.status = 'Delivered'
    """, (order_id,))
    products = cur.fetchall()

    if not products or products[0][0] != session['user_id']:
        return "Unauthorized", 403

    user_id = session['user_id']

    if request.method == 'POST':
        rating = request.form['rating']
        comment = request.form['comment']
        media = request.files.get("media")

        media_path = None
        media_type = None

        if media and media.filename != "":
            ext = media.filename.rsplit(".", 1)[1].lower()
            filename = secure_filename(media.filename)

            save_path = os.path.join("static/review_uploads", filename)
            media.save(save_path)

            media_path = "review_uploads/" + filename

            if ext in ALLOWED_IMAGE:
                media_type = "image"
            elif ext in ALLOWED_VIDEO:
                media_type = "video"

        # Insert review for each product
        for _, product_id, _ in products:
            # Check if review already exists
            cur.execute("""
                SELECT id FROM review WHERE user_id = %s AND product_id = %s
            """, (user_id, product_id))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO review (user_id, product_id, rating, comment, media_type, media_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, product_id, rating, comment, media_type, media_path))

        # Commit reviews
        mysql.connection.commit()

        # Check if all products now have a review
        cur.execute("""
            SELECT COUNT(*) FROM order_items oi
            LEFT JOIN review r ON oi.product_id = r.product_id AND r.user_id = %s
            WHERE oi.order_id = %s AND r.id IS NULL
        """, (user_id, order_id))
        remaining = cur.fetchone()[0]

        # If no remaining products without a review, mark order as completed
        if remaining == 0:
            cur.execute("UPDATE orders SET status='Completed' WHERE id=%s", [order_id])
            mysql.connection.commit()

        cur.close()
        return redirect('/profile')

    # If GET, render review form (not shown here)
    return render_template('add_review.html', order_id=order_id, products=products)


    cur.close()
    return render_template(
        'add_review.html',
        product_name=product_name
    )
# @app.route('/admin/add_product', methods=['GET', 'POST'])
# def add_product():
#     if not session.get('admin'):
#         return redirect(url_for('admin_login'))

#     if request.method == 'POST':
#         name = request.form['name']
#         price = request.form['price']
#         description = request.form['description']
      
#         category = request.form['category']

#         files = request.files.getlist('images[]')
#         cur = mysql.connection.cursor()

#         # Insert product
#         cur.execute("""
#     INSERT INTO products (name, price, description, category)
#     VALUES (%s, %s, %s, %s)
# """, (name, price, description, category))

#         mysql.connection.commit()
#         product_id = cur.lastrowid

#         # Upload images
#         upload_folder = os.path.join(app.root_path, 'static', 'uploads')
#         os.makedirs(upload_folder, exist_ok=True)
#         for file in files:
#             if file and allowed_file(file.filename):
#                 filename = secure_filename(file.filename)
#                 file_path = os.path.join(upload_folder, filename)
#                 file.save(file_path)
#                 relative_path = os.path.join('uploads', filename).replace("\\", "/")
#                 cur.execute("""
#                     INSERT INTO product_images (product_id, image_url)
#                     VALUES (%s, %s)
#                 """, (product_id, relative_path))
#                 mysql.connection.commit()

#         # Handle variations
#         variation_names = request.form.getlist('variation_name[]')
#         for idx, var_name in enumerate(variation_names):
#             # Insert variation
#             cur.execute("INSERT INTO product_variations (product_id, name) VALUES (%s, %s)", (product_id, var_name))
#             mysql.connection.commit()
#             variation_id = cur.lastrowid

#             # Insert options for this variation
#             option_names = request.form.getlist(f'variation_options_{idx}[]')
#             option_stocks = request.form.getlist(f'variation_stock_{idx}[]')
#             for opt_name, opt_stock in zip(option_names, option_stocks):
#                 cur.execute("""
#                     INSERT INTO product_variation_options (variation_id, value, stock)
#                     VALUES (%s, %s, %s)
#                 """, (variation_id, opt_name, opt_stock))
#                 mysql.connection.commit()

#         cur.close()
#         flash("✅ Product added successfully with variations!")
#         return redirect(url_for('admin_dashboard'))

#     return render_template('add_product.html')

@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description')
        category = request.form.get('category')

        files = request.files.getlist('images[]')

        cur = mysql.connection.cursor()

        try:
            # ======================
            # INSERT PRODUCT
            # ======================
            cur.execute("""
                INSERT INTO products (name, price, description, category)
                VALUES (%s, %s, %s, %s)
            """, (name, price, description, category))
            product_id = cur.lastrowid

            # ======================
            # UPLOAD IMAGES
            # ======================
            upload_folder = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)

            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)

                    image_path = f"uploads/{filename}"
                    cur.execute("""
                        INSERT INTO product_images (product_id, image_url)
                        VALUES (%s, %s)
                    """, (product_id, image_path))

            # ======================
            # HANDLE VARIATIONS
            # ======================
            variation_names = request.form.getlist('variation_name[]')

            for idx, var_name in enumerate(variation_names):
                if not var_name.strip():
                    continue

                # Insert variation
                cur.execute("""
                    INSERT INTO product_variations (product_id, name)
                    VALUES (%s, %s)
                """, (product_id, var_name))
                variation_id = cur.lastrowid

                # Insert options
                # Insert options
                option_names = request.form.getlist(f'variation_options_{idx}[]')
                option_stocks = request.form.getlist(f'variation_stock_{idx}[]')
                option_prices = request.form.getlist(f'variation_price_{idx}[]')  # NEW

                for opt_name, opt_stock, opt_price in zip(option_names, option_stocks, option_prices):
                    if not opt_name.strip():
                        continue

                    cur.execute("""
                        INSERT INTO product_variation_options (variation_id, value, stock, extra_price)
                        VALUES (%s, %s, %s, %s)
                    """, (variation_id, opt_name, int(opt_stock), float(opt_price)))  # SAVE extra_price


            mysql.connection.commit()
            flash("✅ Product added successfully with variations!")
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            mysql.connection.rollback()
            print("ADD PRODUCT ERROR:", e)
            flash("❌ Failed to add product")

        finally:
            cur.close()

    return render_template('add_product.html')



# -------------------- ADMIN LOGOUT --------------------
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Admin logged out.')
    return redirect(url_for('admin_login'))

# -------------------- CATALOG --------------------
@app.route('/admin/update_order_status', methods=['POST'])
def update_order_status():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    order_id = request.form['order_id']
    status = request.form['status']

    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    mysql.connection.commit()
    cur.close()

    flash("Order status updated!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/product/<int:product_id>')
def product_details(product_id):
    cur = mysql.connection.cursor()

    # Product
    cur.execute("SELECT * FROM products WHERE id = %s", [product_id])
    product = cur.fetchone()
    if not product:
        return "Product not found", 404

    # Images
    cur.execute("SELECT image_url FROM product_images WHERE product_id = %s", [product_id])
    images = cur.fetchall()

    # Variations
    cur.execute("""
    SELECT pv.id, pv.name, pvo.id, pvo.value, pvo.stock, pvo.extra_price
    FROM product_variations pv
    JOIN product_variation_options pvo ON pv.id = pvo.variation_id
    WHERE pv.product_id = %s
""", [product_id])

    var_rows = cur.fetchall()

    # Organize variations
    variations = {}
    for var_id, var_name, opt_id, opt_value, opt_stock, extra_price in var_rows:
        if var_id not in variations:
            variations[var_id] = {'name': var_name, 'options': []}
        variations[var_id]['options'].append({
            'id': opt_id,
            'value': opt_value,
            'stock': opt_stock,
            'extra_price': float(extra_price) if extra_price else 0
        })


    # Reviews
    cur.execute("""
        SELECT u.name, r.rating, r.comment, r.created_at, r.media_type, r.media_path
        FROM review r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC
    """, [product_id])
    reviews = cur.fetchall()

    # Average rating
    cur.execute("SELECT AVG(rating), COUNT(*) FROM review WHERE product_id = %s", [product_id])
    avg, count = cur.fetchone()
    cur.close()

    product_data = {
        'id': product[0],
        'name': product[1],
        'price': product[2],
        'description': product[3],
        'stock': product[4],
        'images': [img[0] for img in images],
        'reviews': reviews,
        'avg_rating': round(avg, 1) if avg else 0,
        'review_count': count,
        'variations': variations
    }

    return render_template("product_details.html", product=product_data)


@app.route('/catalog')
def catalog():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products WHERE is_active = 1")

    products = cur.fetchall()

    product_list = []
    for p in products:
        if p[4] <= 0:  # p[4] is stock
            continue

        cur.execute("SELECT image_url FROM product_images WHERE product_id = %s", [p[0]])
        images = cur.fetchall()

        product_list.append({
            'id': p[0],
            'name': p[1],
            'price': p[2],
            'description': p[3],
            'stock': p[4],
            'category': p[5],  # <- add this line
            'images': [img[0] for img in images]
        })
    cur.close()
    return render_template('catalog.html', products=product_list)

@app.route("/cancel_order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first."})

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Ensure the order belongs to the user and is still pending
    cur.execute("SELECT status FROM orders WHERE id=%s AND user_id=%s", (order_id, user_id))
    order = cur.fetchone()

    if not order or order[0].lower() != 'pending':
        return jsonify({"success": False, "message": "Order cannot be cancelled."})

    # Update order status to Cancelled
    cur.execute("UPDATE orders SET status='Cancelled' WHERE id=%s", (order_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True})
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # --------------------
    # Handle profile update
    # --------------------
    if request.method == "POST":
        name = request.form.get("name").strip()
        phone = request.form.get("phone").strip()
        address = request.form.get("address").strip()
        profile_img = request.files.get("profile_img")

        profile_img_path = None
        if profile_img and profile_img.filename != "":
            ext = profile_img.filename.rsplit(".", 1)[1].lower()
            if ext in {"png", "jpg", "jpeg", "gif"}:
                filename = secure_filename(profile_img.filename)
                upload_folder = os.path.join(app.root_path, "static/profile_imgs")
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, filename)
                profile_img.save(file_path)
                profile_img_path = f"profile_imgs/{filename}"

        # Check if user_details exists
        cur.execute("SELECT user_id FROM user_details WHERE user_id=%s", [user_id])
        exists = cur.fetchone()
        if exists:
            cur.execute("""
                UPDATE user_details
                SET name=%s, phone=%s, address=%s
                WHERE user_id=%s
            """, (name, phone, address, user_id))
        else:
            cur.execute("""
                INSERT INTO user_details (user_id, name, phone, address)
                VALUES (%s, %s, %s, %s)
            """, (user_id, name, phone, address))

        # Update profile image in users table if uploaded
        if profile_img_path:
            cur.execute("UPDATE users SET profile_img=%s WHERE id=%s", (profile_img_path, user_id))

        mysql.connection.commit()
        flash("✅ Profile updated successfully!")

    # --------------------
    # Fetch user details
    # --------------------
    cur.execute("SELECT u.name, u.email, ud.phone, ud.address, u.profile_img FROM users u LEFT JOIN user_details ud ON u.id=ud.user_id WHERE u.id=%s", [user_id])
    user_details = cur.fetchone()

    # --------------------
    # Fetch orders
    # --------------------
    cur.execute("""
    SELECT o.id, o.total, o.status, o.created_at, o.payment_method, o.name, o.phone, o.address, o.decline_reason
    FROM orders o
    WHERE o.user_id = %s
    ORDER BY o.created_at DESC
""", [user_id])
    orders = cur.fetchall()


    # Fetch order items for each order
    order_items = {}
    for order in orders:
        order_id = order[0]
        cur.execute("""
            SELECT 
                p.name, 
                p.description, 
                oi.qty, 
                oi.price, 
                pv.name AS variation_name, 
                pvo.value AS option_value, 
                COALESCE(pvo.extra_price, 0) AS extra_price
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            LEFT JOIN product_variations pv ON oi.variation_id = pv.id
            LEFT JOIN product_variation_options pvo ON oi.option_id = pvo.id
            WHERE oi.order_id = %s
        """, [order_id])
        order_items[order_id] = cur.fetchall()


    cur.close()
    return render_template("profile.html", user=user_details, orders=orders, order_items=order_items)


# @app.route("/profile")
# def profile():
#     if 'user_id' not in session:
#         flash("Please login first.")
#         return redirect(url_for('login'))

#     user_id = session['user_id']
#     cur = mysql.connection.cursor()

#     # Fetch user details
#     cur.execute("""
#         SELECT name, phone, address
#         FROM user_details
#         WHERE user_id = %s
#     """, [user_id])
#     user_details = cur.fetchone()

#     # Fallback to basic info if user_details not filled
#     if not user_details:
#         cur.execute("SELECT name, email FROM users WHERE id = %s", [user_id])
#         basic_user = cur.fetchone()
#         user_details = (basic_user[0], basic_user[1], '', '')

#     # Fetch pending orders
#     cur.execute("""
#         SELECT o.id, o.name, o.phone, o.address, o.total, o.created_at
#         FROM orders o
#         WHERE o.user_id = %s AND o.status = 'pending'
#         ORDER BY o.created_at DESC
#     """, [user_id])
#     pending_orders = cur.fetchall()

#     cur.close()
#     return render_template("profile.html", user=user_details, pending_orders=pending_orders)

# -------------------- ADD TO CART (DATABASE VERSION) --------------------
# @app.route('/add_to_cart/<int:product_id>')
# def add_to_cart(product_id):
#     if 'user_id' not in session:
#         flash("❌ You must be logged in to add to cart.")
#         return redirect(url_for('login'))

#     user_id = session['user_id']

#     cur = mysql.connection.cursor()

#     # Check if product already in user's cart
#     cur.execute("SELECT id, quantity FROM cart WHERE user_id=%s AND product_id=%s",
#                 (user_id, product_id))
#     item = cur.fetchone()

#     if item:
#         # Update quantity
#         new_qty = item[1] + 1
#         cur.execute("UPDATE cart SET quantity=%s WHERE id=%s", (new_qty, item[0]))
#     else:
#         # Insert new cart item
#         cur.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)",
#                     (user_id, product_id, 1))

#     mysql.connection.commit()
#     cur.close()

#     flash("🛒 Added to cart!")
#     return redirect(url_for('catalog'))
from flask import request, jsonify, session
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return {"success": False, "message": "Login required"}, 401

    data = request.get_json()
    qty = int(data.get("qty", 1))
    variation_id = data.get("variation_id")
    option_id = data.get("option_id")

    if not variation_id or not option_id:
        return {"success": False, "message": "Please select a variation"}, 400

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Get stock and extra price for selected option
    cur.execute("""
        SELECT stock, extra_price
        FROM product_variation_options
        WHERE id = %s
    """, [option_id])
    option = cur.fetchone()

    if not option or option[0] <= 0:
        cur.close()
        return {"success": False, "message": "Selected option is out of stock"}, 400

    stock, extra_price = option
    if qty > stock:
        cur.close()
        return {"success": False, "message": f"Only {stock} available"}, 400

    # Check if same product + variation exists in cart
    cur.execute("""
        SELECT id, quantity
        FROM cart
        WHERE user_id = %s AND product_id = %s AND variation_id = %s AND option_id = %s
    """, (user_id, product_id, variation_id, option_id))

    existing = cur.fetchone()

    if existing:
        new_qty = existing[1] + qty
        if new_qty > stock:
            cur.close()
            return {"success": False, "message": f"Only {stock} available"}, 400

        cur.execute("UPDATE cart SET quantity = %s WHERE id = %s", (new_qty, existing[0]))
    else:
        cur.execute("""
            INSERT INTO cart (user_id, product_id, variation_id, option_id, quantity, extra_price)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, product_id, variation_id, option_id, qty, extra_price))

    mysql.connection.commit()
    cur.close()

    return {"success": True, "message": "Added to cart"}

@app.route("/admin/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    cur = mysql.connection.cursor()

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        description = request.form["description"]
        category = request.form["category"]

        # --- Update Product ---
        cur.execute("""
            UPDATE products
            SET name=%s, price=%s, description=%s, category=%s
            WHERE id=%s
        """, (name, price, description, category, product_id))

        # --- Delete options marked for removal ---
        delete_option_ids = request.form.getlist("delete_option_id[]")
        for oid in delete_option_ids:
            cur.execute("DELETE FROM product_variation_options WHERE id=%s", [oid])

        # --- Update existing options ---
        option_ids = request.form.getlist("option_id[]")
        option_stocks = request.form.getlist("option_stock[]")
        option_extra_prices = request.form.getlist("option_extra_price[]")

        for oid, stock, extra in zip(option_ids, option_stocks, option_extra_prices):
            cur.execute("""
                UPDATE product_variation_options
                SET stock=%s, extra_price=%s
                WHERE id=%s
            """, (int(stock), float(extra), int(oid)))

        # --- Add new variations and options ---
        new_variation_names = request.form.getlist("new_variation_name[]")
        for idx, var_name in enumerate(new_variation_names, start=1):
            cur.execute("INSERT INTO product_variations (product_id, name) VALUES (%s, %s)", (product_id, var_name))
            variation_id = cur.lastrowid

            option_values = request.form.getlist(f"new_option_value[{idx}][]")
            option_extra_prices = request.form.getlist(f"new_option_extra_price[{idx}][]")
            option_stocks = request.form.getlist(f"new_option_stock[{idx}][]")

            for value, extra, stock in zip(option_values, option_extra_prices, option_stocks):
                cur.execute("""
                    INSERT INTO product_variation_options (variation_id, value, stock, extra_price)
                    VALUES (%s, %s, %s, %s)
                """, (variation_id, value, int(stock), float(extra)))

        # --- Handle Images ---
        files = request.files.getlist("new_images[]")
        upload_folder = os.path.join(app.root_path, "static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_folder, filename))
                cur.execute("INSERT INTO product_images (product_id, image_url) VALUES (%s, %s)", (product_id, f"uploads/{filename}"))

        mysql.connection.commit()
        cur.close()
        flash("✅ Product updated successfully!")
        return redirect(url_for("admin_dashboard"))


    # ---------------- FETCH DATA (GET) ----------------
    cur.execute("SELECT * FROM products WHERE id=%s", [product_id])
    product = cur.fetchone()

    cur.execute("SELECT id, image_url FROM product_images WHERE product_id=%s", [product_id])
    images = cur.fetchall()

    cur.execute("""
        SELECT pv.name, pvo.id, pvo.value, pvo.stock, pvo.extra_price
        FROM product_variations pv
        JOIN product_variation_options pvo ON pv.id = pvo.variation_id
        WHERE pv.product_id = %s
    """, [product_id])
    variations = cur.fetchall()

    cur.close()

    return render_template(
        "edit_product.html",
        product=product,
        images=images,
        variations=variations
    )

@app.route("/admin/delete_product_image/<int:image_id>", methods=["POST"])
def delete_product_image(image_id):
    if not session.get("admin"):
        return jsonify(success=False), 403

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM product_images WHERE id=%s", [image_id])
    mysql.connection.commit()
    cur.close()

    return jsonify(success=True)

# -------------------- VIEW CART (DATABASE VERSION) --------------------
@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Fetch cart items with extra price
    cur.execute("""
        SELECT 
            c.id,
            p.name,
            p.price,
            c.quantity,
            (SELECT image_url FROM product_images WHERE product_id = p.id LIMIT 1) AS img,
            pv.name AS variation_name,
            pvo.value AS option_value,
            c.extra_price
        FROM cart c
        JOIN products p ON p.id = c.product_id
        LEFT JOIN product_variations pv ON pv.id = c.variation_id
        LEFT JOIN product_variation_options pvo ON pvo.id = c.option_id
        WHERE c.user_id = %s
    """, [user_id])

    items = cur.fetchall()
    cart_items = []

    for item in items:
        cart_id, name, base_price, qty, img, var_name, opt_value, extra_price = item

        # --- FIX HERE ---
        # Convert DECIMAL to float first to avoid TypeError
        base_price = float(base_price)
        extra_price = float(extra_price) if extra_price else 0.0

        variation_display = f"{var_name}: {opt_value}" if var_name and opt_value else ""
        final_price = base_price + extra_price

        cart_items.append({
            "cart_id": cart_id,
            "name": name,
            "price": final_price,
            "qty": qty,
            "img": img,
            "variation": variation_display
        })

    cur.close()
    total = sum(item['price'] * item['qty'] for item in cart_items)

    return render_template("cart.html", items=cart_items, total=total)
@app.route("/checkout", methods=["POST"])
def checkout():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    selected_ids = request.form.getlist("selected_items")

    if not selected_ids:
        flash("Please select items to checkout.")
        return redirect(url_for("cart"))

    cur = mysql.connection.cursor()
    placeholders = ",".join(["%s"] * len(selected_ids))

    # =======================
    # FETCH CART ITEMS (WITH EXTRA PRICE)
    # =======================
    cur.execute(f"""
        SELECT 
            c.id AS cart_id,
            p.name,
            p.description,
            p.price,
            c.extra_price,
            c.quantity,
            pv.name AS variation_name,
            pvo.value AS option_value
        FROM cart c
        JOIN products p ON p.id = c.product_id
        LEFT JOIN product_variations pv ON pv.id = c.variation_id
        LEFT JOIN product_variation_options pvo ON pvo.id = c.option_id
        WHERE c.id IN ({placeholders})
    """, selected_ids)

    rows = cur.fetchall()
    items = []

    for row in rows:
        (
            cart_id,
            name,
            description,
            base_price,
            extra_price,
            qty,
            var_name,
            opt_value
        ) = row

        base_price = float(base_price)
        extra_price = float(extra_price or 0)
        final_price = base_price + extra_price

        variation_text = f"{var_name}: {opt_value}" if var_name and opt_value else ""

        items.append({
            "cart_id": cart_id,
            "name": name,
            "description": description,
            "price": final_price,
            "qty": qty,
            "variations": variation_text
        })

    # =======================
    # FETCH SAVED USER DETAILS
    # =======================
    cur.execute("""
        SELECT name, phone, address
        FROM user_details
        WHERE user_id = %s
    """, [user_id])
    saved = cur.fetchone()

    cur.close()

    total = sum(item["price"] * item["qty"] for item in items)

    return render_template(
        "checkout_address.html",
        items=items,
        selected_ids=selected_ids,
        saved=saved,
        total=total
    )


@app.route("/confirm_order", methods=["POST"])
def confirm_order():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']

    name = request.form["name"]
    phone = request.form["phone"]
    address = request.form["address"]
    payment_method = request.form["payment_method"]
    selected_ids = request.form.getlist("selected_ids")

    receipt_file = request.files.get("receipt")
    receipt_filename = None

    # -------------------- CASHLESS RECEIPT CHECK --------------------
    if payment_method == "Cashless":
        if not receipt_file or receipt_file.filename == "":
            flash("Receipt is required for cashless payment.")
            return redirect(url_for("cart"))

        filename = secure_filename(receipt_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        receipt_file.save(file_path)
        receipt_filename = "uploads/" + filename

    cur = mysql.connection.cursor()

    # -------------------- FETCH CART ITEMS --------------------
    placeholders = ",".join(["%s"] * len(selected_ids))
    cur.execute(f"""
        SELECT 
            c.id,
            c.product_id,
            c.variation_id,
            c.option_id,
            c.quantity,
            p.price,
            pvo.stock
        FROM cart c
        JOIN products p ON p.id = c.product_id
        JOIN product_variation_options pvo ON pvo.id = c.option_id
        WHERE c.id IN ({placeholders})
    """, selected_ids)

    cart_items = cur.fetchall()

    if not cart_items:
        flash("Cart items not found.")
        return redirect(url_for("cart"))

    # -------------------- STOCK VALIDATION --------------------
    for item in cart_items:
        _, _, _, _, qty, _, stock = item
        if qty > stock:
            flash("Some items are out of stock.")
            return redirect(url_for("cart"))

    # -------------------- CALCULATE TOTAL --------------------
    total = sum(item[4] * item[5] for item in cart_items)

    # -------------------- SAVE / UPDATE USER DETAILS --------------------
    cur.execute("SELECT user_id FROM user_details WHERE user_id=%s", [user_id])
    exists = cur.fetchone()

    if exists:
        cur.execute("""
            UPDATE user_details
            SET name=%s, phone=%s, address=%s
            WHERE user_id=%s
        """, (name, phone, address, user_id))
    else:
        cur.execute("""
            INSERT INTO user_details (user_id, name, phone, address)
            VALUES (%s, %s, %s, %s)
        """, (user_id, name, phone, address))

    # -------------------- CREATE ORDER --------------------
    cur.execute("""
        INSERT INTO orders (user_id, name, phone, address, total, payment_method, receipt_img)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (user_id, name, phone, address, total, payment_method, receipt_filename))

    order_id = cur.lastrowid

    # -------------------- INSERT ORDER ITEMS + DEDUCT VARIATION STOCK --------------------
    for item in cart_items:
        cart_id, product_id, variation_id, option_id, qty, price, _ = item

        # Save order item
        cur.execute("""
            INSERT INTO order_items 
            (order_id, product_id, variation_id, option_id, qty, price)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (order_id, product_id, variation_id, option_id, qty, price))

        # Deduct variation option stock
        cur.execute("""
            UPDATE product_variation_options
            SET stock = stock - %s
            WHERE id = %s
        """, (qty, option_id))

    # -------------------- REMOVE FROM CART --------------------
    cur.execute(f"DELETE FROM cart WHERE id IN ({placeholders})", selected_ids)

    mysql.connection.commit()
    cur.close()

    flash(f"✅ Order #{order_id} placed successfully!")
    return redirect(url_for("catalog"))




@app.route('/remove_cart_item/<int:cart_id>')
def remove_cart_item(cart_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM cart WHERE id = %s", [cart_id])
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('cart'))
@app.route('/update_cart_qty_ajax', methods=['POST'])
def update_cart_qty_ajax():
    data = request.get_json()
    cart_id = data['cart_id']
    action = data['action']

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT c.quantity, pvo.stock
        FROM cart c
        JOIN product_variation_options pvo ON pvo.id = c.option_id
        WHERE c.id = %s
    """, [cart_id])

    row = cur.fetchone()
    if not row:
        return jsonify(success=False, message="Item not found")

    qty, stock = row

    if action == "plus":
        if qty + 1 > stock:
            return jsonify(success=False, message="Stock limit reached")
        qty += 1

    elif action == "minus":
        qty -= 1
        if qty <= 0:
            cur.execute("DELETE FROM cart WHERE id=%s", [cart_id])
            mysql.connection.commit()
            cur.close()
            return jsonify(success=True, qty=0)

    cur.execute("UPDATE cart SET quantity=%s WHERE id=%s", (qty, cart_id))
    mysql.connection.commit()
    cur.close()

    return jsonify(success=True, qty=qty)
@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if not session.get("admin"):
        return jsonify(success=False), 403

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE products 
        SET is_active = 0 
        WHERE id = %s
    """, (product_id,))
    mysql.connection.commit()

    affected = cur.rowcount
    cur.close()

    if affected == 0:
        return jsonify(success=False, message="Product not found")

    return jsonify(success=True)


# -------------------- HOME --------------------
@app.route('/')
def home():
    return redirect(url_for('catalog'))

# -------------------- RUN APP --------------------
if __name__ == '__main__':
    app.run(debug=True)
