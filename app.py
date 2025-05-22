from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a secure key in production

# In-memory product list
products = [
    {
        "id": 1,
        "name": "University T-Shirt",
        "category": "Apparel",
        "stock": 10,
        "price": "15.00",
        "description": "High-quality cotton T-shirt with university logo"
    },
    {
        "id": 2,
        "name": "Campus Mug",
        "category": "Merch",
        "stock": 25,
        "price": "8.00",
        "description": "Ceramic mug with LangkiTap design"
    }
]

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "admin" and password == "1234":
            session["admin"] = True
            return redirect(url_for("admin_page"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
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
    return render_template("admin_catalog.html", products=products)

@app.route("/admin/catalog/add", methods=["POST"])
def add_product():
    if not session.get("admin"):
        return redirect(url_for("login"))
    
    name = request.form["name"]
    category = request.form["category"]
    stock = request.form["stock"]
    price = request.form["price"]
    description = request.form["description"]

    new_id = max([p["id"] for p in products], default=0) + 1
    products.append({
        "id": new_id,
        "name": name,
        "category": category,
        "stock": int(stock),
        "price": price,
        "description": description
    })

    return redirect(url_for("admin_catalog"))

@app.route("/admin/catalog/delete/<int:product_id>")
def delete_product(product_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    
    global products
    products = [p for p in products if p["id"] != product_id]
    return redirect(url_for("admin_catalog"))

if __name__ == "__main__":
    app.run(debug=True)
