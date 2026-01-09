from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret123'

# -------------------- MySQL CONFIG --------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'shop_db'
mysql = MySQL(app)

# -------------------- UPLOAD CONFIG --------------------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------- USER REGISTRATION --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        if cur.fetchone():
            flash('❌ Email already registered!')
            return redirect(url_for('register'))

        cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                    (name, email, password))
        mysql.connection.commit()
        cur.close()
        flash('✅ Registration successful!')
        return redirect(url_for('login'))
    return render_template('register.html')

# -------------------- USER LOGIN --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash('✅ Login successful!')
            return redirect(url_for('catalog'))
        else:
            flash('❌ Invalid credentials!')
            return redirect(url_for('login'))
    return render_template('login.html')

# -------------------- USER LOGOUT --------------------


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
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    cur.close()
    return render_template('admin_dashboard.html', products=products)

# -------------------- ADD PRODUCT (FIXED) --------------------

@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        description = request.form['description']

        files = request.files.getlist('images[]')  # Multiple files

        cur = mysql.connection.cursor()
        # Insert product
        cur.execute("INSERT INTO products (name, price, description) VALUES (%s, %s, %s)",
                    (name, price, description))
        mysql.connection.commit()
        product_id = cur.lastrowid

        # Ensure uploads folder exists
        upload_folder = os.path.join(app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)

        # Save files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_folder, filename))
                relative_path = os.path.join('uploads', filename).replace("\\", "/")
                cur.execute("INSERT INTO product_images (product_id, image_url) VALUES (%s, %s)",
                            (product_id, relative_path))
                mysql.connection.commit()

        cur.close()
        flash('✅ Product added successfully!')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_product.html')



# -------------------- ADMIN LOGOUT --------------------
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Admin logged out.')
    return redirect(url_for('admin_login'))

# -------------------- CATALOG --------------------
@app.route('/catalog')
def catalog():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    product_list = []
    for p in products:
        cur.execute("SELECT image_url FROM product_images WHERE product_id = %s", [p[0]])
        images = cur.fetchall()
        product_list.append({
            'id': p[0],
            'name': p[1],
            'price': p[2],
            'description': p[3],
            'images': [img[0] for img in images]
        })
    cur.close()
    return render_template('catalog.html', products=product_list)


# -------------------- ADD TO CART (DATABASE VERSION) --------------------
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash("❌ You must be logged in to add to cart.")
        return redirect(url_for('login'))

    user_id = session['user_id']

    cur = mysql.connection.cursor()

    # Check if product already in user's cart
    cur.execute("SELECT id, quantity FROM cart WHERE user_id=%s AND product_id=%s",
                (user_id, product_id))
    item = cur.fetchone()

    if item:
        # Update quantity
        new_qty = item[1] + 1
        cur.execute("UPDATE cart SET quantity=%s WHERE id=%s", (new_qty, item[0]))
    else:
        # Insert new cart item
        cur.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)",
                    (user_id, product_id, 1))

    mysql.connection.commit()
    cur.close()

    flash("🛒 Added to cart!")
    return redirect(url_for('catalog'))
# -------------------- VIEW CART (DATABASE VERSION) --------------------
@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT cart.id, products.name, products.price, cart.quantity
        FROM cart
        JOIN products ON products.id = cart.product_id
        WHERE cart.user_id = %s
    """, [user_id])

    items = cur.fetchall()
    cur.close()

    # Calculate total
    total = sum(item[2] * item[3] for item in items)

    return render_template('cart.html', items=items, total=total)


# -------------------- HOME --------------------
@app.route('/')
def home():
    return redirect(url_for('catalog'))

# -------------------- RUN APP --------------------
if __name__ == '__main__':
    app.run(debug=True)
