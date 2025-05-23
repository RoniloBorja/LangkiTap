import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__, static_url_path='/static')
app.secret_key = "your_secret_key"

# File upload setup (absolute path)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///catalog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoid warning
db = SQLAlchemy(app)

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    stock = db.Column(db.Integer)
    price = db.Column(db.Float)
    description = db.Column(db.String(255))
    image = db.Column(db.String(255))

# Initialize DB (create tables)
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/shop")
def shop():
    products = Product.query.all()
    total = sum(float(product.price) for product in products if product.price is not None)
    return render_template("shop.html", products=products, total=total) 

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        if username == "admin" and password == "1234":
            session["admin"] = True
            return redirect(url_for("admin_page"))
        elif username == "user" and password == "4321":
            session["user"] = True
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    session.pop("user", None)
    return redirect(url_for("home"))

@app.route("/admin")
def admin_page():
    if not session.get("admin"):
        return redirect(url_for("login"))
    return render_template("admin.html")

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

    # Get and convert form data
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

if __name__ == "__main__":
    app.run(debug=True)
