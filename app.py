import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from collections import defaultdict


app = Flask(__name__, static_url_path='/static')
app.secret_key = "your_secret_key"

# File upload setup
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///catalog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    stock = db.Column(db.Integer)
    price = db.Column(db.Float)
    description = db.Column(db.String(255))
    image = db.Column(db.String(255))

# Customer order model
class CustomerOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    )
    total_amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    items = db.relationship('OrderItem', backref='order', lazy=True)
# Order item model
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('customer_order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)

    product = db.relationship('Product')  # <-- Add this line


# Initialize DB
with app.app_context():
    db.create_all()

    # Create default users if not exist
    if not User.query.filter_by(username="admin").first():
        db.session.add(User(username="admin", password="0123", is_admin=True))
    if not User.query.filter_by(username="user").first():
        db.session.add(User(username="user", password="4321", is_admin=False))
    db.session.commit()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/shop")
def shop():
    products = Product.query.all()
    total = sum(float(product.price) for product in products if product.price is not None)
    categorized = defaultdict(list)
    for product in products:
        categorized[product.category or "Uncategorized"].append(product)
    return render_template("shop.html", categorized_products=categorized, total=total)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user"] = True
            session["user_id"] = user.id
            session["username"] = user.username
            if user.is_admin:
                session["admin"] = True
                return redirect(url_for("admin_page"))
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already exists.")

        new_user = User(username=username, password=password, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/checkout", methods=["POST"])
def process_checkout():
    if not session.get('user'):
        return jsonify({'success': False, 'message': 'Please login first'})
    
    data = request.get_json()

    try:
        new_order = CustomerOrder(
            user_id=session['user_id'],
            total_amount=float(data['total']),
            status='pending'
        )
        db.session.add(new_order)
        db.session.flush()

        for item in data['items']:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route("/admin")
def admin_page():
    if not session.get("admin"):
        return redirect(url_for("login"))
    orders = CustomerOrder.query.order_by(CustomerOrder.created_at.desc()).limit(10).all()
    users = {u.id: u.username for u in User.query.all()}
    return render_template("admin.html", orders=orders, users=users)

@app.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if not session.get("admin"):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    data = request.get_json()
    order = CustomerOrder.query.get_or_404(order_id)
    old_status = order.status
    new_status = data['status']

    # ✅ Restore stock ONLY if switching to 'cancelled' from a status that is NOT 'completed' or 'cancelled'
    if old_status not in ['cancelled', 'completed'] and new_status == 'cancelled':
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.stock += item.quantity

    order.status = new_status
    db.session.commit()
    return jsonify({'success': True})


@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if not session.get("admin"):
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        order = CustomerOrder.query.get_or_404(order_id)

        # ✅ Restore stock ONLY if it wasn't already restored (i.e., order is still 'pending')
        if order.status == 'pending':
            for item in order.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.stock += item.quantity

        # Delete order items and the order itself
        OrderItem.query.filter_by(order_id=order.id).delete()
        db.session.delete(order)
        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})



@app.route("/admin/catalog")
def admin_catalog():
    if not session.get("admin"):
        return redirect(url_for("login"))
    products = Product.query.all()
    return render_template("admin_catalog.html", products=products)

@app.route("/admin/catalog/add", methods=["POST"])
def add_product():
    if not session.get("admin"):
        return redirect(url_for("login"))

    name = request.form["name"]
    category = request.form["category"]
    stock = int(request.form["stock"])
    price = float(request.form["price"])
    description = request.form["description"]

    image_file = request.files.get("image")
    image_filename = ""
    if image_file and image_file.filename:
        image_filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image_file.save(image_path)

    product = Product(
        name=name,
        category=category,
        stock=stock,
        price=price,
        description=description,
        image=image_filename
    )
    db.session.add(product)
    db.session.commit()
    return redirect(url_for("admin_catalog"))

@app.route("/admin/catalog/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        product.name = request.form["name"]
        product.category = request.form["category"]
        product.stock = int(request.form["stock"])
        product.price = float(request.form["price"])
        product.description = request.form["description"]

        image_file = request.files.get("image")
        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)
            product.image = image_filename

        db.session.commit()
        return redirect(url_for("admin_catalog"))

    return render_template("edit_product.html", product=product)

@app.route("/admin/catalog/delete/<int:product_id>")
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for("admin_catalog"))

@app.route('/decrease_stock/<int:product_id>', methods=['POST'])
def decrease_stock(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})

    if product.stock <= 0:
        return jsonify({'success': False, 'message': 'Out of stock'})

    product.stock -= 1
    db.session.commit()
    return jsonify({'success': True, 'remaining_stock': product.stock})

@app.route('/increase_stock/<int:product_id>', methods=['POST'])
def increase_stock(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})

    product.stock += 1
    db.session.commit()
    return jsonify({'success': True, 'new_stock': product.stock})

if __name__ == "__main__":
    app.run(debug=True)
