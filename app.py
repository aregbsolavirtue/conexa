from flask import Flask, render_template, request, redirect, url_for
import sqlite3


app = Flask(__name__)


def get_db_connection():

    conn = sqlite3.connect("database.db")

    conn.row_factory = sqlite3.Row

    return conn


def create_database():

    conn = get_db_connection()

    conn.execute(
        "CREATE TABLE IF NOT EXISTS artisans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, "
        "service TEXT NOT NULL, "
        "location TEXT NOT NULL, "
        "phone TEXT NOT NULL, "
        "experience TEXT NOT NULL, "
        "rating REAL DEFAULT 0, "
        "verified INTEGER DEFAULT 0"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS service_requests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "customer_name TEXT NOT NULL, "
        "phone TEXT NOT NULL, "
        "service TEXT NOT NULL, "
        "location TEXT NOT NULL, "
        "description TEXT NOT NULL, "
        "artisan_id INTEGER, "
        "status TEXT DEFAULT 'Pending', "
        "FOREIGN KEY (artisan_id) REFERENCES artisans(id)"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS reviews ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "artisan_id INTEGER NOT NULL, "
        "reviewer_name TEXT NOT NULL, "
        "rating INTEGER NOT NULL, "
        "comment TEXT NOT NULL, "
        "FOREIGN KEY (artisan_id) REFERENCES artisans(id)"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS verification_requests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "artisan_id INTEGER NOT NULL, "
        "full_name TEXT NOT NULL, "
        "service TEXT NOT NULL, "
        "location TEXT NOT NULL, "
        "phone TEXT NOT NULL, "
        "years_experience TEXT NOT NULL, "
        "verification_note TEXT NOT NULL, "
        "status TEXT DEFAULT 'Pending', "
        "FOREIGN KEY (artisan_id) REFERENCES artisans(id)"
        ")"
    )

    columns = conn.execute(
        "PRAGMA table_info(artisans)"
    ).fetchall()

    column_names = []

    for column in columns:
        column_names.append(column["name"])

    if "verified" not in column_names:

        conn.execute(
            "ALTER TABLE artisans "
            "ADD COLUMN verified INTEGER DEFAULT 0"
        )

    conn.commit()

    conn.close()


def add_sample_artisans():

    conn = get_db_connection()

    existing_artisans = conn.execute(
        "SELECT COUNT(*) AS total "
        "FROM artisans"
    ).fetchone()

    if existing_artisans["total"] == 0:

        sample_artisans = [
            (
                "Adewale Electrical Services",
                "Electrician",
                "Yaba",
                "08012345678",
                "5",
                3.5,
                0
            ),
            (
                "Chinedu Plumbing Services",
                "Plumber",
                "Surulere",
                "08023456789",
                "7",
                4.6,
                0
            ),
            (
                "Emeka Woodworks",
                "Carpenter",
                "Ikeja",
                "08034567890",
                "8",
                4.9,
                0
            ),
            (
                "Kunle AC Services",
                "AC Technician",
                "Lekki",
                "08045678901",
                "6",
                4.7,
                0
            )
        ]

        conn.executemany(
            "INSERT INTO artisans "
            "(name, service, location, phone, experience, rating, verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            sample_artisans
        )

        conn.commit()

    conn.close()


@app.route("/")
def home():

    return render_template("index.html")


@app.route("/search")
def search():

    service = request.args.get(
        "service",
        ""
    ).strip()

    location = request.args.get(
        "location",
        ""
    ).strip()

    conn = get_db_connection()

    query = (
        "SELECT "
        "artisans.*, "
        "COUNT(reviews.id) AS review_count "
        "FROM artisans "
        "LEFT JOIN reviews "
        "ON artisans.id = reviews.artisan_id "
        "WHERE 1 = 1 "
    )

    parameters = []

    if service:

        query += (
            "AND artisans.service LIKE ? "
        )

        parameters.append(
            "%" + service + "%"
        )

    if location:

        query += (
            "AND artisans.location LIKE ? "
        )

        parameters.append(
            "%" + location + "%"
        )

    query += (
        "GROUP BY artisans.id "
        "ORDER BY artisans.verified DESC, "
        "artisans.rating DESC"
    )

    artisans = conn.execute(
        query,
        parameters
    ).fetchall()

    conn.close()

    return render_template(
        "results.html",
        artisans=artisans,
        service=service,
        location=location
    )


@app.route("/artisan/<int:artisan_id>")
def artisan_profile(artisan_id):

    conn = get_db_connection()

    artisan = conn.execute(
        "SELECT * "
        "FROM artisans "
        "WHERE id = ?",
        (artisan_id,)
    ).fetchone()

    if artisan is None:

        conn.close()

        return "Artisan not found.", 404

    reviews = conn.execute(
        "SELECT * "
        "FROM reviews "
        "WHERE artisan_id = ? "
        "ORDER BY id DESC",
        (artisan_id,)
    ).fetchall()

    review_count = conn.execute(
        "SELECT COUNT(*) AS total "
        "FROM reviews "
        "WHERE artisan_id = ?",
        (artisan_id,)
    ).fetchone()["total"]

    conn.close()

    return render_template(
        "artisan.html",
        artisan=artisan,
        reviews=reviews,
        review_count=review_count
    )


@app.route(
    "/request/<int:artisan_id>",
    methods=["GET", "POST"]
)
def request_service(artisan_id):

    conn = get_db_connection()

    artisan = conn.execute(
        "SELECT * "
        "FROM artisans "
        "WHERE id = ?",
        (artisan_id,)
    ).fetchone()

    if artisan is None:

        conn.close()

        return "Artisan not found.", 404

    if request.method == "POST":

        customer_name = request.form.get(
            "customer_name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        if (
            not customer_name
            or not phone
            or not location
            or not description
        ):

            conn.close()

            return "Please fill in all required fields.", 400

        conn.execute(
            "INSERT INTO service_requests "
            "(customer_name, phone, service, location, description, artisan_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                customer_name,
                phone,
                artisan["service"],
                location,
                description,
                artisan_id
            )
        )

        conn.commit()

        conn.close()

        return render_template(
            "request_success.html",
            artisan=artisan
        )

    conn.close()

    return render_template(
        "request.html",
        artisan=artisan
    )


@app.route(
    "/review/<int:artisan_id>",
    methods=["POST"]
)
def submit_review(artisan_id):

    reviewer_name = request.form.get(
        "reviewer_name",
        ""
    ).strip()

    rating = request.form.get(
        "rating",
        ""
    ).strip()

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    if not reviewer_name or not rating or not comment:

        return "Please fill in all review fields.", 400

    try:

        rating = int(rating)

    except ValueError:

        return "Invalid rating.", 400

    if rating < 1 or rating > 5:

        return "Rating must be between 1 and 5.", 400

    conn = get_db_connection()

    artisan = conn.execute(
        "SELECT id "
        "FROM artisans "
        "WHERE id = ?",
        (artisan_id,)
    ).fetchone()

    if artisan is None:

        conn.close()

        return "Artisan not found.", 404

    conn.execute(
        "INSERT INTO reviews "
        "(artisan_id, reviewer_name, rating, comment) "
        "VALUES (?, ?, ?, ?)",
        (
            artisan_id,
            reviewer_name,
            rating,
            comment
        )
    )

    rating_data = conn.execute(
        "SELECT AVG(rating) AS average_rating "
        "FROM reviews "
        "WHERE artisan_id = ?",
        (artisan_id,)
    ).fetchone()

    average_rating = rating_data["average_rating"]

    conn.execute(
        "UPDATE artisans "
        "SET rating = ? "
        "WHERE id = ?",
        (
            average_rating,
            artisan_id
        )
    )

    conn.commit()

    conn.close()

    return render_template(
        "review_success.html"
    )


@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        service = request.form.get(
            "service",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        experience = request.form.get(
            "experience",
            ""
        ).strip()

        if (
            not name
            or not service
            or not location
            or not phone
            or not experience
        ):

            return "Please fill in all registration fields.", 400

        conn = get_db_connection()

        cursor = conn.execute(
            "INSERT INTO artisans "
            "(name, service, location, phone, experience, rating, verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                service,
                location,
                phone,
                experience,
                0,
                0
            )
        )

        artisan_id = cursor.lastrowid

        conn.commit()

        conn.close()

        return render_template(
            "success.html",
            artisan_id=artisan_id
        )

    return render_template(
        "register.html"
    )


@app.route(
    "/verify/<int:artisan_id>",
    methods=["GET", "POST"]
)
def verify_artisan(artisan_id):

    conn = get_db_connection()

    artisan = conn.execute(
        "SELECT * "
        "FROM artisans "
        "WHERE id = ?",
        (artisan_id,)
    ).fetchone()

    if artisan is None:

        conn.close()

        return "Artisan not found.", 404

    if artisan["verified"] == 1:

        conn.close()

        return "This artisan is already verified.", 400

    pending_request = conn.execute(
        "SELECT id "
        "FROM verification_requests "
        "WHERE artisan_id = ? "
        "AND status = 'Pending'",
        (artisan_id,)
    ).fetchone()

    if pending_request is not None:

        conn.close()

        return "A verification request is already pending.", 400

    if request.method == "POST":

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        service = request.form.get(
            "service",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        years_experience = request.form.get(
            "years_experience",
            ""
        ).strip()

        verification_note = request.form.get(
            "verification_note",
            ""
        ).strip()

        if (
            not full_name
            or not service
            or not location
            or not phone
            or not years_experience
            or not verification_note
        ):

            conn.close()

            return "Please fill in all verification fields.", 400

        conn.execute(
            "INSERT INTO verification_requests "
            "(artisan_id, full_name, service, location, phone, "
            "years_experience, verification_note, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artisan_id,
                full_name,
                service,
                location,
                phone,
                years_experience,
                verification_note,
                "Pending"
            )
        )

        conn.commit()

        conn.close()

        return render_template(
            "verification_success.html",
            artisan=artisan
        )

    conn.close()

    return render_template(
        "verification.html",
        artisan=artisan
    )


@app.route("/admin")
def admin():

    conn = get_db_connection()

    verification_requests = conn.execute(
        "SELECT * "
        "FROM verification_requests "
        "ORDER BY "
        "CASE "
        "WHEN status = 'Pending' THEN 1 "
        "ELSE 2 "
        "END, "
        "id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        requests=verification_requests
    )


@app.route(
    "/admin/verification/<int:request_id>/approve",
    methods=["POST"]
)
def approve_verification(request_id):

    conn = get_db_connection()

    verification_request = conn.execute(
        "SELECT artisan_id "
        "FROM verification_requests "
        "WHERE id = ?",
        (request_id,)
    ).fetchone()

    if verification_request is None:

        conn.close()

        return "Verification request not found.", 404

    artisan_id = verification_request["artisan_id"]

    conn.execute(
        "UPDATE verification_requests "
        "SET status = 'Approved' "
        "WHERE id = ?",
        (request_id,)
    )

    conn.execute(
        "UPDATE artisans "
        "SET verified = 1 "
        "WHERE id = ?",
        (artisan_id,)
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin")
    )


@app.route(
    "/admin/verification/<int:request_id>/reject",
    methods=["POST"]
)
def reject_verification(request_id):

    conn = get_db_connection()

    verification_request = conn.execute(
        "SELECT id "
        "FROM verification_requests "
        "WHERE id = ?",
        (request_id,)
    ).fetchone()

    if verification_request is None:

        conn.close()

        return "Verification request not found.", 404

    conn.execute(
        "UPDATE verification_requests "
        "SET status = 'Rejected' "
        "WHERE id = ?",
        (request_id,)
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin")
    )


@app.route("/admin/requests")
def admin_requests():

    conn = get_db_connection()

    service_requests = conn.execute(
        "SELECT "
        "service_requests.id, "
        "service_requests.customer_name, "
        "service_requests.phone, "
        "service_requests.service, "
        "service_requests.location, "
        "service_requests.description, "
        "service_requests.artisan_id, "
        "service_requests.status, "
        "artisans.name AS artisan_name "
        "FROM service_requests "
        "LEFT JOIN artisans "
        "ON service_requests.artisan_id = artisans.id "
        "ORDER BY "
        "CASE "
        "WHEN service_requests.status = 'Pending' THEN 1 "
        "WHEN service_requests.status = 'In Progress' THEN 2 "
        "ELSE 3 "
        "END, "
        "service_requests.id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "admin_requests.html",
        requests=service_requests
    )


@app.route(
    "/admin/request/<int:request_id>/status",
    methods=["POST"]
)
def update_request_status(request_id):

    status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Completed"
    ]

    if status not in allowed_statuses:

        return "Invalid request status.", 400

    conn = get_db_connection()

    service_request = conn.execute(
        "SELECT id "
        "FROM service_requests "
        "WHERE id = ?",
        (request_id,)
    ).fetchone()

    if service_request is None:

        conn.close()

        return "Service request not found.", 404

    conn.execute(
        "UPDATE service_requests "
        "SET status = ? "
        "WHERE id = ?",
        (
            status,
            request_id
        )
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin_requests")
    )


@app.route("/admin/artisans")
def admin_artisans():

    conn = get_db_connection()

    artisans = conn.execute(
        "SELECT "
        "artisans.*, "
        "COUNT(reviews.id) AS review_count "
        "FROM artisans "
        "LEFT JOIN reviews "
        "ON artisans.id = reviews.artisan_id "
        "GROUP BY artisans.id "
        "ORDER BY artisans.verified DESC, "
        "artisans.rating DESC, "
        "artisans.name ASC"
    ).fetchall()

    conn.close()

    return render_template(
        "admin_artisans.html",
        artisans=artisans
    )


@app.route(
    "/artisan/<int:artisan_id>/requests"
)
def artisan_requests(artisan_id):

    conn = get_db_connection()

    artisan = conn.execute(
        "SELECT "
        "id, "
        "name, "
        "service "
        "FROM artisans "
        "WHERE id = ?",
        (artisan_id,)
    ).fetchone()

    if artisan is None:

        conn.close()

        return "Artisan not found.", 404

    service_requests = conn.execute(
        "SELECT "
        "id, "
        "customer_name, "
        "phone, "
        "service, "
        "location, "
        "description, "
        "status "
        "FROM service_requests "
        "WHERE artisan_id = ? "
        "ORDER BY id DESC",
        (artisan_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "artisan_requests.html",
        artisan=artisan,
        requests=service_requests
    )


if __name__ == "__main__":

    create_database()

    add_sample_artisans()

    app.run(
        debug=True
    )