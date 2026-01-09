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
app.config['MYSQL_DB'] = 'etr_python'
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
            user_id = cur.lastrowid  # Get newly created user ID
            cur.close()

            return redirect(url_for('set_security_questions', user_id=user_id))

    return render_template('register.html', errors=errors, form_data=form_data)
@app.route('/set_security_questions/<int:user_id>', methods=['GET', 'POST'])
def set_security_questions(user_id):
    questions_list = [
        "What was your childhood nickname?",
        "What is the name of your favorite childhood friend?",
        "What was the name of your first pet?",
        "What is your mother's maiden name?",
        "What city were you born in?"
    ]

    errors = {}

    if request.method == 'POST':
        selected_questions = [
            request.form.get('question1'),
            request.form.get('question2'),
            request.form.get('question3')
        ]
        answers = [
            request.form.get('answer1', '').strip(),
            request.form.get('answer2', '').strip(),
            request.form.get('answer3', '').strip()
        ]

        # Validation
        if len(set(selected_questions)) < 3:
            errors['questions'] = "Please select 3 different questions."
        if not all(answers):
            errors['answers'] = "Please provide answers for all questions."

        if not errors:
            cur = mysql.connection.cursor()
            for q, a in zip(selected_questions, answers):
                cur.execute(
                    "INSERT INTO user_security_questions (user_id, question, answer) VALUES (%s, %s, %s)",
                    (user_id, q, a)
                )
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('login'))  # After setting questions, go to login

    return render_template(
        'set_security_questions.html',
        questions_list=questions_list,
        errors=errors
    )


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
                    session['login_success'] = True
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
    errors = {}
    step = 1  # Step 1: email input
    user = None
    security_questions = []

    if request.method == 'POST':
        step_post = request.form.get('step', '1')

        # ------------------- STEP 1: Enter Email -------------------
        if step_post == '1':
            email = request.form.get('email', '').strip()
            if not email:
                errors['email'] = "Email is required"
            else:
                cur = mysql.connection.cursor()
                cur.execute("SELECT id FROM users WHERE email=%s", [email])
                user_data = cur.fetchone()
                cur.close()

                if not user_data:
                    errors['email'] = "Email not registered"
                else:
                    user = user_data[0]
                    step = 2  # Go to security questions step
                    # Fetch security questions
                    cur = mysql.connection.cursor()
                    cur.execute("SELECT question FROM user_security_questions WHERE user_id=%s ORDER BY id ASC", [user])
                    security_questions = [row[0] for row in cur.fetchall()]
                    cur.close()

        # ------------------- STEP 2: Answer Security Questions -------------------
        elif step_post == '2':
            user_id = request.form.get('user_id')
            answers = [
                request.form.get('answer1', '').strip(),
                request.form.get('answer2', '').strip(),
                request.form.get('answer3', '').strip()
            ]
            contact_number = request.form.get('contact_number', '').strip()

            if not all(answers):
                errors['answers'] = "Please answer all security questions"
            if not contact_number:
                errors['contact_number'] = "Please provide a number for admin contact"

            # Verify answers
            cur = mysql.connection.cursor()
            cur.execute("SELECT answer FROM user_security_questions WHERE user_id=%s ORDER BY id ASC", [user_id])
            correct_answers = [row[0] for row in cur.fetchall()]
            cur.close()

            if answers != correct_answers:
                errors['answers'] = "Security answers do not match"
            else:
                # Save request in database
                cur = mysql.connection.cursor()
                cur.execute(
                    "INSERT INTO password_reset_requests (user_id, contact_number) VALUES (%s, %s)",
                    (user_id, contact_number)
                )
                mysql.connection.commit()
                cur.close()

                return render_template('forgot_password_success.html', contact_number=contact_number)

    return render_template(
        'forgot_password.html',
        errors=errors,
        step=step,
        security_questions=security_questions,
        user_id=user
    )


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
            flash('Admin login successful!', 'success')  
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials!', 'error')  
            return redirect(url_for('admin_login'))

    return render_template('admin_login.html')
# -------------------- ADMIN DASHBOARD --------------------
from datetime import datetime


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()

    # --------------------
    # CATEGORY FILTER (from query string)
    # --------------------
    selected_category = request.args.get("category", "")

    # Fetch UNIQUE categories from products table
    cur.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category IS NOT NULL AND category != ''
    """)
    categories = [row[0] for row in cur.fetchall()]

    # --------------------
    # PRODUCTS (filtered by category if selected)
    # --------------------
    if selected_category:
        cur.execute("""
            SELECT *
            FROM products
            WHERE is_active = 1 AND category = %s
        """, [selected_category])
    else:
        cur.execute("""
            SELECT *
            FROM products
            WHERE is_active = 1
        """)

    products = cur.fetchall()

    products_with_variations = []
    for p in products:
        cur.execute("""
            SELECT 
                pvo.value,
                pvo.stock,
                pvo.extra_price
            FROM product_variations pv
            JOIN product_variation_options pvo
                ON pv.id = pvo.variation_id
            WHERE pv.product_id = %s
        """, [p[0]])

        variations = cur.fetchall()

        products_with_variations.append({
            "product": p,
            "variations": variations
        })

    # --------------------
    # USERS
    # --------------------
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
# --------------------
# PASSWORD RESET REQUESTS (Pending)
# --------------------
    cur.execute("""
        SELECT pr.id, u.name, u.email, pr.contact_number, pr.status, pr.created_at
        FROM password_reset_requests pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.status = 'Pending'
        ORDER BY pr.created_at DESC
    """)
    pending_password_resets = cur.fetchall()

    # --------------------
    # PENDING / ACTIVE ORDERS
    # --------------------
    # --------------------
# PENDING / ACTIVE ORDERS
# --------------------
    cur.execute("""
        SELECT 
            o.id,
            u.name,
            u.email,
            o.total,
            o.status,
            o.created_at
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.status NOT IN ('Delivered', 'Declined', 'Completed','Cancelled')  -- only pending
        ORDER BY o.created_at DESC
    """)
    pending_orders = cur.fetchall()

    # --------------------
    # COMPLETED ORDERS
    # --------------------
    cur.execute("""
        SELECT 
            o.id,
            u.name,
            u.email,
            o.total,
            o.status,
            o.created_at
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.status = 'Completed'  -- only delivered/completed
        ORDER BY o.created_at DESC
    """)
    completed_orders = cur.fetchall()


    # --------------------
    # DATE FILTER
    # --------------------
    selected_date = request.args.get("date")
    if not selected_date:
        selected_date = datetime.today().strftime("%Y-%m-%d")

    # --------------------
    # SALES SUMMARY
    # --------------------
    cur.execute("""
        SELECT 
            COALESCE(SUM(
                CASE 
                    WHEN DATE(created_at) = %s THEN total
                END
            ), 0),

            COALESCE(SUM(
                CASE 
                    WHEN YEARWEEK(created_at, 1) = YEARWEEK(%s, 1) THEN total
                END
            ), 0),

            COALESCE(SUM(
                CASE 
                    WHEN MONTH(created_at) = MONTH(%s)
                     AND YEAR(created_at) = YEAR(%s)
                    THEN total
                END
            ), 0)
        FROM orders
        WHERE LOWER(status) LIKE '%%deliver%%'
    """, (selected_date, selected_date, selected_date, selected_date))

    daily_sales, weekly_sales, monthly_sales = cur.fetchone()

    cur.close()

    return render_template(
        "admin_dashboard.html",
        products=products_with_variations,
        categories=categories,
        selected_category=selected_category,
        users=users,
        pending_orders=pending_orders,
            completed_orders=completed_orders,  # ✅ add this
          pending_password_resets=pending_password_resets,  # <--- add this
        daily_sales=daily_sales,
        weekly_sales=weekly_sales,
        monthly_sales=monthly_sales,
        selected_date=selected_date
    )

@app.route("/admin/change_request_password", methods=["POST"])
def change_request_password():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"})

    data = request.get_json()
    request_id = data.get("request_id")
    new_password = data.get("new_password")

    cur = mysql.connection.cursor()

    # Get the user_id for this request
    cur.execute("SELECT user_id FROM password_reset_requests WHERE id=%s", (request_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"success": False, "message": "Request not found"})

    user_id = row[0]

    # Hash the new password
    hashed_pw = generate_password_hash(new_password)  # from werkzeug.security import generate_password_hash

    # Update user password
    cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_pw, user_id))

    # Mark request as Done
    cur.execute("UPDATE password_reset_requests SET status='Done' WHERE id=%s", (request_id,))
    mysql.connection.commit()

    return jsonify({"success": True})

@app.route("/admin/change_user_password", methods=["POST"])
def admin_change_user_password():
    if not session.get('admin'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    user_id = data.get("user_id")
    new_password = data.get("new_password")

    if not user_id or not new_password:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    # Hash the password (using werkzeug.security)
    from werkzeug.security import generate_password_hash
    hashed_pw = generate_password_hash(new_password)

    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_pw, user_id))
        mysql.connection.commit()
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        cur.close()

    return jsonify({"success": True})

@app.route('/admin/fetch_products')
def fetch_products():
    if not session.get('admin'):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    category = request.args.get("category", "").strip()
    search = request.args.get("search", "").strip()

    cur = mysql.connection.cursor()

    query = "SELECT * FROM products WHERE is_active = 1"
    params = []

    if category:
        query += " AND category = %s"
        params.append(category)

    if search:
        query += " AND name LIKE %s"
        params.append(f"%{search}%")

    cur.execute(query, params)
    products = cur.fetchall()

    # Fetch variations
    products_with_variations = []
    for p in products:
        cur.execute("""
            SELECT pvo.value, pvo.stock, pvo.extra_price
            FROM product_variations pv
            JOIN product_variation_options pvo ON pv.id = pvo.variation_id
            WHERE pv.product_id = %s
        """, [p[0]])
        variations = cur.fetchall()
        products_with_variations.append({
            "product": p,
            "variations": variations
        })

    cur.close()
    return jsonify({"success": True, "products": products_with_variations})

    
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

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Fetch products in the order (only delivered orders)
    cur.execute("""
        SELECT o.user_id, oi.product_id, p.name
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.id = %s AND o.status = 'Delivered'
    """, (order_id,))
    products = cur.fetchall()

    # Unauthorized if no products or order doesn't belong to user
    if not products or products[0][0] != user_id:
        cur.close()
        return "Unauthorized", 403

    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment'].strip()
        media = request.files.get("media")

        media_path = None
        media_type = None

        if media and media.filename != "":
            ext = media.filename.rsplit(".", 1)[1].lower()
            filename = secure_filename(media.filename)
            upload_folder = os.path.join(app.root_path, "static/review_uploads")
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, filename)
            media.save(save_path)

            media_path = "review_uploads/" + filename
            if ext in ALLOWED_IMAGE:
                media_type = "image"
            elif ext in ALLOWED_VIDEO:
                media_type = "video"

        # Insert review for each product (if not already reviewed)
        for _, product_id, _ in products:
            cur.execute("SELECT id FROM review WHERE user_id=%s AND product_id=%s", (user_id, product_id))
            
            cur.execute("""
                    INSERT INTO review (user_id, product_id, rating, comment, media_type, media_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, product_id, rating, comment, media_type, media_path))

        mysql.connection.commit()

        # Check if all products now have reviews; if so, mark order completed
        cur.execute("""
            SELECT COUNT(*) 
            FROM order_items oi
            LEFT JOIN review r ON oi.product_id = r.product_id AND r.user_id = %s
            WHERE oi.order_id = %s AND r.id IS NULL
        """, (user_id, order_id))
        remaining = cur.fetchone()[0]

        if remaining == 0:
            cur.execute("UPDATE orders SET status='Completed' WHERE id=%s", (order_id,))
            mysql.connection.commit()

        cur.close()

        # Pass success flag to template
        return render_template(
            'add_review.html',
            order_id=order_id,
            products=products,
            success=True  # <--- flag
        )

    # For GET requests
    return render_template(
        'add_review.html',
        order_id=order_id,
        products=products
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

# app.py

from flask import request, jsonify, session, url_for, redirect
from werkzeug.utils import secure_filename
import os



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
            # VARIATIONS
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

                # Insert variation options
                option_names = request.form.getlist(f'variation_options_{idx}[]')
                option_stocks = request.form.getlist(f'variation_stock_{idx}[]')
                option_prices = request.form.getlist(f'variation_price_{idx}[]')

                for opt_name, opt_stock, opt_price in zip(option_names, option_stocks, option_prices):
                    if not opt_name.strip():
                        continue

                    # Safe conversion with defaults
                    try:
                        stock_val = int(opt_stock)
                    except:
                        stock_val = 0

                    try:
                        price_val = float(opt_price)
                    except:
                        price_val = 0.0

                    cur.execute("""
                        INSERT INTO product_variation_options (variation_id, value, stock, extra_price)
                        VALUES (%s, %s, %s, %s)
                    """, (variation_id, opt_name, stock_val, price_val))

            # Everything succeeded
            mysql.connection.commit()
            flash("✅ Product added successfully with variations!", "success")
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            mysql.connection.rollback()
            print("ADD PRODUCT ERROR:", e)
            flash(f"❌ Failed to add product: {str(e)}")  # show actual error for debugging

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
        # Remove stock check so products with 0 stock are included

        # Get product images
        cur.execute("SELECT image_url FROM product_images WHERE product_id = %s", [p[0]])
        images = cur.fetchall()

        product_list.append({
            'id': p[0],
            'name': p[1],
            'price': p[2],
            'description': p[3],
            'stock': p[4],
            'category': p[5],
            'images': [img[0] for img in images]
        })
    cur.close()
    return render_template('catalog.html', products=product_list)

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/cancel_order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first."})

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Get JSON data from request
    data = request.get_json()
    reason = data.get("reason", "No reason provided")  # default if none provided

    # Ensure the order belongs to the user and is still pending
    cur.execute("SELECT status FROM orders WHERE id=%s AND user_id=%s", (order_id, user_id))
    order = cur.fetchone()

    if not order or order[0].lower() != 'pending':
        return jsonify({"success": False, "message": "Order cannot be cancelled."})

    # Update order status to Cancelled and save decline reason
    cur.execute(
        "UPDATE orders SET status=%s, decline_reason=%s WHERE id=%s",
        ("Cancelled", reason, order_id)
    )
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
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        action = request.form.get("action")

        # ==========================
        # UPDATE DETAILS (NAME + IMAGE)
        # ==========================
        if action == "update_details":
            name = request.form.get("name", "").strip()
            profile_img = request.files.get("profile_img")

            if name:
                cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, user_id))

            if profile_img and profile_img.filename:
                ext = profile_img.filename.rsplit(".", 1)[1].lower()
                if ext in {"png", "jpg", "jpeg", "gif"}:
                    filename = secure_filename(profile_img.filename)
                    upload_folder = os.path.join(app.root_path, "static/profile_imgs")
                    os.makedirs(upload_folder, exist_ok=True)
                    profile_img.save(os.path.join(upload_folder, filename))

                    profile_img_path = f"profile_imgs/{filename}"
                    cur.execute(
                        "UPDATE users SET profile_img=%s WHERE id=%s",
                        (profile_img_path, user_id)
                    )

        # ==========================
        # UPDATE ADDRESS ONLY
        # ==========================
        elif action == "update_address":
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()

            cur.execute("SELECT user_id FROM user_details WHERE user_id=%s", (user_id,))
            if cur.fetchone():
                cur.execute("""
                    UPDATE user_details
                    SET phone=%s, address=%s
                    WHERE user_id=%s
                """, (phone, address, user_id))
            else:
                cur.execute("""
                    INSERT INTO user_details (user_id, phone, address)
                    VALUES (%s, %s, %s)
                """, (user_id, phone, address))

        mysql.connection.commit()
        cur.close()

        if is_ajax:
            return jsonify({"success": True, "message": "Profile updated successfully"})

        flash("Profile updated successfully")
        return redirect(url_for("profile"))



    # --------------------
    # Fetch user details
    # --------------------
    cur.execute("""
        SELECT u.name, u.email, ud.phone, ud.address, u.profile_img
        FROM users u
        LEFT JOIN user_details ud ON u.id = ud.user_id
        WHERE u.id = %s
    """, (user_id,))
    user_details = cur.fetchone()

    # --------------------
    # Fetch orders
    # --------------------
    cur.execute("""
        SELECT 
            o.id, o.total, o.status, o.created_at,
            o.payment_method, o.name, o.phone, o.address, o.decline_reason
        FROM orders o
        WHERE o.user_id = %s
        ORDER BY o.created_at DESC
    """, (user_id,))
    orders = cur.fetchall()

    # --------------------
    # Fetch ALL order items (FIXED)
    # --------------------
    order_items = {}

    cur.execute("""
        SELECT
            oi.order_id,
            p.name,
            p.description,
            oi.qty,
            oi.price,
            pv.name AS variation_name,
            pvo.value AS option_value
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        LEFT JOIN product_variations pv ON oi.variation_id = pv.id
        LEFT JOIN product_variation_options pvo ON oi.option_id = pvo.id
        WHERE oi.order_id IN (
            SELECT id FROM orders WHERE user_id = %s
        )
        ORDER BY oi.order_id DESC
    """, (user_id,))

    items = cur.fetchall()

    for row in items:
        order_id = row[0]

        if order_id not in order_items:
            order_items[order_id] = []

        order_items[order_id].append((
            row[1],  # product name
            row[2],  # description
            row[3],  # qty
            row[4],  # price (already includes extra_price if added at checkout)
            row[5],  # variation name
            row[6],  # option value
        ))

    cur.close()

    return render_template(
        "profile.html",
        user=user_details,
        orders=orders,
        order_items=order_items
    )
@app.route("/order/<int:order_id>")
def order_details(order_id):
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Fetch order info
    cur.execute("""
        SELECT id, total, status, created_at, payment_method, name, phone, address, decline_reason, voucher_code, discount
        FROM orders
        WHERE id=%s AND user_id=%s
    """, (order_id, user_id))
    order = cur.fetchone()
    if not order:
        flash("Order not found.")
        return redirect(url_for("profile"))

    # Fetch order items
    cur.execute("""
        SELECT p.name, p.description, oi.qty, oi.price, pv.name, pvo.value
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        LEFT JOIN product_variations pv ON oi.variation_id = pv.id
        LEFT JOIN product_variation_options pvo ON oi.option_id = pvo.id
        WHERE oi.order_id=%s
    """, (order_id,))
    items = cur.fetchall()
    cur.close()

    return render_template("order_details.html", order=order, items=items)

from PIL import Image, ImageDraw, ImageFont
from flask import send_file
import io
from datetime import datetime

@app.route("/download_receipt/<int:order_id>")
def download_receipt(order_id):
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # -----------------------------
    # Fetch order info
    # -----------------------------
    cur.execute("""
        SELECT name, phone, address, total, payment_method, created_at, voucher_code, discount
        FROM orders
        WHERE id=%s AND user_id=%s
    """, (order_id, user_id))
    order = cur.fetchone()
    if not order:
        flash("Order not found.")
        return redirect(url_for("profile"))

    # -----------------------------
    # Fetch order items
    # -----------------------------
    cur.execute("""
        SELECT p.name, p.description, oi.qty, oi.price, pv.name, pvo.value
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        LEFT JOIN product_variations pv ON oi.variation_id = pv.id
        LEFT JOIN product_variation_options pvo ON oi.option_id = pvo.id
        WHERE oi.order_id=%s
    """, (order_id,))
    items = cur.fetchall()
    cur.close()

    # -----------------------------
    # Image dimensions
    # -----------------------------
    width = 800
    line_height = 30
    header_height = 140
    footer_height = 80
    items_height = line_height * (len(items) + 1)  # +1 for table header
    total_height = header_height + items_height + footer_height + 150

    img = Image.new("RGB", (width, total_height), "white")
    draw = ImageDraw.Draw(img)

    # -----------------------------
    # Fonts
    # -----------------------------
    try:
        font_bold = ImageFont.truetype("arialbd.ttf", 20)
        font_regular = ImageFont.truetype("arial.ttf", 16)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except:
        font_bold = ImageFont.load_default()
        font_regular = ImageFont.load_default()
        font_small = ImageFont.load_default()

    y = 20

    # -----------------------------
    # Header
    # -----------------------------
    draw.text((20, y), "🌟 My Shop 🌟", font=font_bold, fill="black")
    y += 35
    draw.text((20, y), f"Receipt - Order #{order_id}", font=font_regular, fill="black")
    y += 25
    draw.text((20, y), f"Date: {order[5].strftime('%B %d, %Y %I:%M %p')}", font=font_regular, fill="black")
    y += 30

    # -----------------------------
    # Customer info
    # -----------------------------
    draw.text((20, y), "Customer Information:", font=font_bold, fill="black")
    y += 25
    draw.text((30, y), f"Name: {order[0]}", font=font_regular, fill="black")
    y += 20
    draw.text((30, y), f"Phone: {order[1]}", font=font_regular, fill="black")
    y += 20
    draw.text((30, y), f"Address: {order[2]}", font=font_regular, fill="black")
    y += 25
    draw.text((20, y), f"Payment Method: {order[4]}", font=font_regular, fill="black")
    y += 35

    # -----------------------------
    # Table header
    # -----------------------------
    draw.text((20, y), "Product", font=font_bold, fill="black")
    draw.text((400, y), "Qty", font=font_bold, fill="black")
    draw.text((480, y), "Price", font=font_bold, fill="black")
    draw.text((580, y), "Subtotal", font=font_bold, fill="black")
    y += 5
    draw.line((20, y, width-20, y), fill="black", width=2)
    y += 15

    # -----------------------------
    # Table rows
    # -----------------------------
    for item in items:
        name, desc, qty, price, var_name, option_value = item
        product_text = f"{name} ({var_name}:{option_value})" if var_name else f"{name}"
        subtotal = qty * price
        draw.text((20, y), product_text, font=font_regular, fill="black")
        draw.text((400, y), str(qty), font=font_regular, fill="black")
        draw.text((480, y), f"₱{price:.2f}", font=font_regular, fill="black")
        draw.text((580, y), f"₱{subtotal:.2f}", font=font_regular, fill="black")
        y += line_height

    y += 10
    draw.line((20, y, width-20, y), fill="black", width=2)
    y += 15

    # -----------------------------
    # Discount / Voucher
    # -----------------------------
    total_amount = order[3]
    if order[6]:  # voucher_code
        discount = order[7] or 0
        draw.text((400, y), f"Discount ({order[6]}):", font=font_regular, fill="black")
        draw.text((580, y), f"-₱{discount:.2f}", font=font_regular, fill="black")
        total_amount -= discount
        y += line_height

    # -----------------------------
    # Total
    # -----------------------------
    draw.text((400, y), "Total:", font=font_bold, fill="black")
    draw.text((580, y), f"₱{total_amount:.2f}", font=font_bold, fill="black")
    y += 40

    # -----------------------------
    # Footer
    # -----------------------------
    draw.line((20, y, width-20, y), fill="black", width=2)
    y += 10
    draw.text((20, y), "Thank you for your purchase!", font=font_regular, fill="black")
    y += 20
    draw.text((20, y), "For inquiries, contact us at: support@myshop.com", font=font_small, fill="black")

    # -----------------------------
    # Save to memory and send
    # -----------------------------
    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/png",
                     as_attachment=True,
                     download_name=f"receipt_order_{order_id}.png")
 
@app.route("/change_password", methods=["POST"])
def change_password():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    user_id = session["user_id"]
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not current_password or not new_password or not confirm_password:
        return jsonify({"success": False, "message": "All fields are required"})

    if new_password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match"})

    cur = mysql.connection.cursor()
    cur.execute("SELECT password FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    if not user or not check_password_hash(user[0], current_password):
        return jsonify({"success": False, "message": "Current password is incorrect"})

    hashed_password = generate_password_hash(new_password)
    cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, user_id))
    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True})


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
        flash("Product updated successfully!", "success")
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
@app.route("/admin/delete_product_option/<int:option_id>", methods=["POST"])
def delete_product_option(option_id):
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM product_variation_options WHERE id=%s", [option_id])
    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True})
@app.route("/cart_count")
def cart_count():
    if 'user_id' not in session:
        return jsonify({"success": True, "count": 0})  # guest user

    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT SUM(qty) FROM cart WHERE user_id=%s", [user_id])
    total = cur.fetchone()[0] or 0
    cur.close()
    return jsonify({"success": True, "count": total})

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
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    payment_method = request.form.get("payment_method", "").strip()
    voucher_code = request.form.get("voucher", "").strip().lower()
    selected_ids = request.form.getlist("selected_ids")

    if not selected_ids:
        flash("No items selected.")
        return redirect(url_for("cart"))

    receipt_file = request.files.get("receipt")
    receipt_filename = None

    # -------------------- CASHLESS RECEIPT CHECK --------------------
    if payment_method == "Cashless":
        if not receipt_file or receipt_file.filename == "":
            flash("Receipt is required for cashless payment.")
            return redirect(url_for("cart"))

        filename = secure_filename(receipt_file.filename)
        upload_folder = os.path.join(app.root_path, "static/uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        receipt_file.save(file_path)
        receipt_filename = f"uploads/{filename}"

    cur = mysql.connection.cursor()
    order_id = None

    try:
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
                COALESCE(pvo.extra_price, 0) AS extra_price,
                pvo.stock
            FROM cart c
            JOIN products p ON p.id = c.product_id
            LEFT JOIN product_variation_options pvo ON pvo.id = c.option_id
            WHERE c.id IN ({placeholders})
        """, selected_ids)

        cart_items = cur.fetchall()
        if not cart_items:
            flash("Cart items not found.")
            return redirect(url_for("cart"))

        # -------------------- VALIDATE STOCK --------------------
        for item in cart_items:
            _, _, _, _, qty, _, _, stock = item
            if stock is not None and qty > stock:
                flash(f"Not enough stock for a product. Available: {stock}")
                return redirect(url_for("cart"))

        # -------------------- SAVE OR UPDATE USER DETAILS --------------------
        # -------------------- SAVE OR UPDATE USER DETAILS --------------------
        cur.execute("SELECT user_id FROM user_details WHERE user_id=%s", (user_id,))
        if cur.fetchone():
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


        # -------------------- CALCULATE TOTAL --------------------
        subtotal = sum((float(price) + float(extra_price or 0)) * qty for _, _, _, _, qty, price, extra_price, _ in cart_items)

        # -------------------- APPLY VOUCHER --------------------
        discount = 0
        if voucher_code == "papasalahat":
            discount = min(subtotal * 0.15, 1000)  # 15% capped at 1000
        total = subtotal - discount

        # -------------------- CREATE ORDER --------------------
        cur.execute("""
            INSERT INTO orders (user_id, name, phone, address, payment_method, total, receipt_img, discount, voucher_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, name, phone, address, payment_method, total, receipt_filename, discount, voucher_code or None))

        order_id = cur.lastrowid  # ✅ Must assign here

        # -------------------- INSERT ORDER ITEMS & REDUCE STOCK --------------------
        for item in cart_items:
            cart_id, product_id, variation_id, option_id, qty, price, extra_price, stock = item
            total_price = float(price) + float(extra_price or 0)

            cur.execute("""
                INSERT INTO order_items 
                (order_id, product_id, variation_id, option_id, qty, price)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (order_id, product_id, variation_id, option_id, qty, total_price))

            # Reduce stock
            if option_id:
                cur.execute("UPDATE product_variation_options SET stock = stock - %s WHERE id = %s", (qty, option_id))
            else:
                cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, product_id))

        # -------------------- REMOVE FROM CART --------------------
        cur.execute(f"DELETE FROM cart WHERE id IN ({placeholders})", selected_ids)

        # -------------------- COMMIT --------------------
        mysql.connection.commit()
        flash(f"✅ Order placed successfully! Voucher discount applied: ₱{discount:.2f}")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error placing order: {str(e)}")
        return redirect(url_for("cart"))

    finally:
        cur.close()

    return redirect(url_for("profile"))
@app.route("/api/my_orders")
def api_my_orders():
    if 'user_id' not in session:
        return jsonify({"success": False}), 401

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, total, status, created_at, payment_method, name, phone, address, decline_reason
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    orders = cur.fetchall()

    cur.close()

    return jsonify({
        "success": True,
        "orders": [
            {
                "id": o[0],
                "total": float(o[1]),
                "status": o[2],
                "created_at": o[3],
                "payment_method": o[4],
                "name": o[5],
                "phone": o[6],
                "address": o[7],
                "decline_reason": o[8]
            } for o in orders
        ]
    })


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
