
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bookstore-demo-key")

DATABASE = os.environ.get("DATABASE_PATH", "bookstore.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            FOREIGN KEY (book_id) REFERENCES books(id)
        )
    """)

    # Insert sample books only when the table is empty
    count = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    if count == 0:
        conn.executemany("""
            INSERT INTO books (title, author, price, stock)
            VALUES (?, ?, ?, ?)
        """, [
            ("Python Programming", "John Smith", 450, 10),
            ("Cloud Computing", "R. Kumar", 550, 8),
            ("Web Development", "Jane Wilson", 400, 15)
        ])

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return redirect(url_for("books"))


# READ: Display all books
@app.route("/books")
def books():
    conn = get_db()
    all_books = conn.execute(
        "SELECT * FROM books ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template("books.html", books=all_books)


# CREATE: Add a new book
@app.route("/books/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form["title"].strip()
        author = request.form["author"].strip()
        price = float(request.form["price"])
        stock = int(request.form["stock"])

        conn = get_db()
        conn.execute("""
            INSERT INTO books (title, author, price, stock)
            VALUES (?, ?, ?, ?)
        """, (title, author, price, stock))

        conn.commit()
        conn.close()

        flash("Book added successfully!")
        return redirect(url_for("books"))

    return render_template("add_book.html")


# UPDATE: Edit book details
@app.route("/books/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    conn = get_db()

    book = conn.execute(
        "SELECT * FROM books WHERE id = ?",
        (book_id,)
    ).fetchone()

    if book is None:
        conn.close()
        return "Book not found", 404

    if request.method == "POST":
        title = request.form["title"].strip()
        author = request.form["author"].strip()
        price = float(request.form["price"])
        stock = int(request.form["stock"])

        conn.execute("""
            UPDATE books
            SET title = ?, author = ?, price = ?, stock = ?
            WHERE id = ?
        """, (title, author, price, stock, book_id))

        conn.commit()
        conn.close()

        flash("Book updated successfully!")
        return redirect(url_for("books"))

    conn.close()
    return render_template("edit_book.html", book=book)


# DELETE: Remove a book
@app.route("/books/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    conn = get_db()

    # Do not delete a book referenced by an order
    order_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE book_id = ?",
        (book_id,)
    ).fetchone()[0]

    if order_count > 0:
        conn.close()
        flash("Cannot delete a book that has orders.")
        return redirect(url_for("books"))

    conn.execute(
        "DELETE FROM books WHERE id = ?",
        (book_id,)
    )

    conn.commit()
    conn.close()

    flash("Book deleted successfully!")
    return redirect(url_for("books"))


# READ: Display customer orders
@app.route("/orders")
def orders():
    conn = get_db()

    all_orders = conn.execute("""
        SELECT orders.id,
               orders.customer_name,
               books.title,
               orders.quantity,
               orders.status
        FROM orders
        JOIN books ON orders.book_id = books.id
        ORDER BY orders.id DESC
    """).fetchall()

    conn.close()

    return render_template("orders.html", orders=all_orders)


# CREATE: Add a customer order
@app.route("/orders/add", methods=["GET", "POST"])
def add_order():
    conn = get_db()

    available_books = conn.execute(
        "SELECT * FROM books WHERE stock > 0"
    ).fetchall()

    if request.method == "POST":
        customer_name = request.form["customer_name"].strip()
        book_id = int(request.form["book_id"])
        quantity = int(request.form["quantity"])

        book = conn.execute(
            "SELECT * FROM books WHERE id = ?",
            (book_id,)
        ).fetchone()

        if book is None or quantity <= 0 or quantity > book["stock"]:
            conn.close()
            flash("Invalid book or quantity. Check available stock.")
            return redirect(url_for("add_order"))

        conn.execute("""
            INSERT INTO orders (customer_name, book_id, quantity, status)
            VALUES (?, ?, ?, 'Pending')
        """, (customer_name, book_id, quantity))

        conn.execute("""
            UPDATE books
            SET stock = stock - ?
            WHERE id = ?
        """, (quantity, book_id))

        conn.commit()
        conn.close()

        flash("Order created successfully!")
        return redirect(url_for("orders"))

    conn.close()

    return render_template(
        "add_order.html",
        books=available_books
    )


# UPDATE: Change order status
@app.route("/orders/update/<int:order_id>", methods=["POST"])
def update_order(order_id):
    status = request.form["status"]

    allowed_statuses = [
        "Pending", "Processing", "Shipped", "Delivered", "Cancelled"
    ]

    if status not in allowed_statuses:
        flash("Invalid order status.")
        return redirect(url_for("orders"))

    conn = get_db()

    conn.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (status, order_id))

    conn.commit()
    conn.close()

    flash("Order status updated!")
    return redirect(url_for("orders"))


# DELETE: Remove an order
@app.route("/orders/delete/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    conn = get_db()

    order = conn.execute("""
        SELECT book_id, quantity
        FROM orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    if order:
        conn.execute("""
            UPDATE books
            SET stock = stock + ?
            WHERE id = ?
        """, (order["quantity"], order["book_id"]))

        conn.execute(
            "DELETE FROM orders WHERE id = ?",
            (order_id,)
        )

        conn.commit()

    conn.close()

    flash("Order deleted successfully!")
    return redirect(url_for("orders"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
