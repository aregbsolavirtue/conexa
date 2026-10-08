from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = "conexa-development-secret-key"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():
    conn = get_db_connection()

    # -----------------------------------------------------
    # ARTISANS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS artisans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            service TEXT NOT NULL,
            location TEXT NOT NULL,
            phone TEXT NOT NULL,
            experience TEXT NOT NULL,
            rating REAL DEFAULT 0,
            verified INTEGER DEFAULT 0
        )
    """)

    artisan_columns = [
        "email TEXT",
        "password_hash TEXT",
        "country TEXT",
        "state_region TEXT",
        "city_area TEXT"
    ]

    existing_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(artisans)"
        ).fetchall()
    ]

    for column_definition in artisan_columns:
        column_name = column_definition.split()[0]

        if column_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE artisans ADD COLUMN {column_definition}"
            )

    # -----------------------------------------------------
    # SERVICE REQUESTS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS service_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            service TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            artisan_id INTEGER,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (artisan_id)
                REFERENCES artisans(id)
        )
    """)

    # -----------------------------------------------------
    # REVIEWS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artisan_id INTEGER NOT NULL,
            reviewer_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            FOREIGN KEY (artisan_id)
                REFERENCES artisans(id)
        )
    """)

    # -----------------------------------------------------
    # VERIFICATION REQUESTS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS verification_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artisan_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            service TEXT NOT NULL,
            location TEXT NOT NULL,
            phone TEXT NOT NULL,
            years_experience TEXT NOT NULL,
            verification_note TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (artisan_id)
                REFERENCES artisans(id)
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# SEARCH
# =========================================================

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

    query = """
        SELECT *
        FROM artisans
        WHERE 1 = 1
    """

    params = []

    if service:
        query += " AND service LIKE ?"
        params.append(f"%{service}%")

    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")

    query += " ORDER BY verified DESC, rating DESC"

    artisans = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    return render_template(
        "results.html",
        artisans=artisans,
        service=service,
        location=location
    )


# =========================================================
# ARTISAN PROFILE
# =========================================================

@app.route("/artisan/<int:artisan_id>")
def artisan_profile(artisan_id):
    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (artisan_id,)
    ).fetchone()

    reviews = conn.execute(
        """
        SELECT *
        FROM reviews
        WHERE artisan_id = ?
        ORDER BY id DESC
        """,
        (artisan_id,)
    ).fetchall()

    review_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM reviews
        WHERE artisan_id = ?
        """,
        (artisan_id,)
    ).fetchone()[0]

    conn.close()

    if artisan is None:
        return "Artisan not found.", 404

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    is_owner = logged_in_artisan_id == artisan_id

    return render_template(
        "artisan.html",
        artisan=artisan,
        reviews=reviews,
        review_count=review_count,
        is_owner=is_owner
    )


# =========================================================
# CUSTOMER SERVICE REQUEST
# =========================================================

@app.route(
    "/request/<int:artisan_id>",
    methods=["GET", "POST"]
)
def request_service(artisan_id):

    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (artisan_id,)
    ).fetchone()

    conn.close()

    if artisan is None:
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

        service = request.form.get(
            "service",
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

        if not all([
            customer_name,
            phone,
            service,
            location,
            description
        ]):
            return render_template(
                "register_error.html",
                error_title="Missing Information",
                error_message=(
                    "Please fill in all the required "
                    "service request fields."
                )
            ), 400

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO service_requests (
                customer_name,
                phone,
                service,
                location,
                description,
                artisan_id,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_name,
                phone,
                service,
                location,
                description,
                artisan_id,
                "Pending"
            )
        )

        conn.commit()
        conn.close()

        return render_template(
            "request_success.html",
            artisan=artisan
        )

    return render_template(
        "request.html",
        artisan=artisan
    )


# =========================================================
# SUBMIT REVIEW
# =========================================================

@app.route(
    "/review/<int:artisan_id>",
    methods=["POST"]
)
def submit_review(artisan_id):

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    if logged_in_artisan_id == artisan_id:
        return (
            "Artisans cannot leave reviews for their own profiles.",
            403
        )

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
        return render_template(
            "register_error.html",
            error_title="Missing Review Information",
            error_message=(
                "Please complete all review fields."
            )
        ), 400

    try:
        rating = int(rating)

    except ValueError:
        return render_template(
            "register_error.html",
            error_title="Invalid Rating",
            error_message=(
                "Please provide a valid rating."
            )
        ), 400

    if rating < 1 or rating > 5:
        return render_template(
            "register_error.html",
            error_title="Invalid Rating",
            error_message=(
                "Rating must be between 1 and 5."
            )
        ), 400

    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (artisan_id,)
    ).fetchone()

    if artisan is None:
        conn.close()
        return "Artisan not found.", 404

    conn.execute(
        """
        INSERT INTO reviews (
            artisan_id,
            reviewer_name,
            rating,
            comment
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            artisan_id,
            reviewer_name,
            rating,
            comment
        )
    )

    average_rating = conn.execute(
        """
        SELECT AVG(rating)
        FROM reviews
        WHERE artisan_id = ?
        """,
        (artisan_id,)
    ).fetchone()[0]

    conn.execute(
        """
        UPDATE artisans
        SET rating = ?
        WHERE id = ?
        """,
        (
            round(average_rating or 0, 1),
            artisan_id
        )
    )

    conn.commit()
    conn.close()

    return render_template(
        "review_success.html",
        artisan=artisan
    )


# =========================================================
# ARTISAN REGISTRATION
# =========================================================

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

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        country = request.form.get(
            "country",
            ""
        ).strip()

        state_region = request.form.get(
            "state_region",
            ""
        ).strip()

        city_area = request.form.get(
            "city_area",
            ""
        ).strip()

        experience = request.form.get(
            "experience",
            ""
        ).strip()

        if not all([
            name,
            service,
            location,
            phone,
            password,
            country,
            state_region,
            city_area,
            experience
        ]):
            return render_template(
                "register_error.html",
                error_title="Missing Information",
                error_message=(
                    "Please complete all required "
                    "registration fields."
                )
            ), 400

        if len(password) < 6:
            return render_template(
                "register_error.html",
                error_title="Password Too Short",
                error_message=(
                    "Your password must be at least "
                    "6 characters long."
                )
            ), 400

        conn = get_db_connection()

        existing_phone = conn.execute(
            """
            SELECT id
            FROM artisans
            WHERE phone = ?
            """,
            (phone,)
        ).fetchone()

        if existing_phone:
            conn.close()

            return render_template(
                "register_error.html",
                error_title="Phone Number Already Registered",
                error_message=(
                    "An artisan account already exists "
                    "with this phone number."
                )
            ), 400

        if email:

            existing_email = conn.execute(
                """
                SELECT id
                FROM artisans
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

            if existing_email:
                conn.close()

                return render_template(
                    "register_error.html",
                    error_title="Email Already Registered",
                    error_message=(
                        "An artisan account already exists "
                        "with this email address."
                    )
                ), 400

        password_hash = generate_password_hash(
            password
        )

        cursor = conn.execute(
            """
            INSERT INTO artisans (
                name,
                service,
                location,
                phone,
                experience,
                rating,
                verified,
                email,
                password_hash,
                country,
                state_region,
                city_area
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                service,
                location,
                phone,
                experience,
                0,
                0,
                email or None,
                password_hash,
                country,
                state_region,
                city_area
            )
        )

        artisan_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return render_template(
            "success.html",
            artisan_id=artisan_id,
            name=name
        )

    return render_template(
        "register.html"
    )


# =========================================================
# ARTISAN LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if not phone or not password:
            return render_template(
                "register_error.html",
                error_title="Missing Login Information",
                error_message=(
                    "Please enter both your phone number "
                    "and password to sign in."
                )
            ), 400

        conn = get_db_connection()

        artisan = conn.execute(
            """
            SELECT *
            FROM artisans
            WHERE phone = ?
            """,
            (phone,)
        ).fetchone()

        conn.close()

        if artisan is None:
            return render_template(
                "register_error.html",
                error_title="Invalid Login Details",
                error_message=(
                    "The phone number or password you entered "
                    "is incorrect. Please check your details "
                    "and try again."
                )
            ), 401

        password_hash = artisan["password_hash"]

        if not password_hash:
            return render_template(
                "register_error.html",
                error_title="Account Setup Required",
                error_message=(
                    "This artisan account was created before "
                    "the Conexa login system was introduced. "
                    "Please create a new artisan account."
                )
            ), 401

        if not check_password_hash(
            password_hash,
            password
        ):
            return render_template(
                "register_error.html",
                error_title="Invalid Login Details",
                error_message=(
                    "The phone number or password you entered "
                    "is incorrect. Please check your details "
                    "and try again."
                )
            ), 401

        session.clear()

        session["artisan_id"] = artisan["id"]
        session["artisan_name"] = artisan["name"]

        return redirect(
            url_for("artisan_dashboard")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# ARTISAN DASHBOARD
# =========================================================

@app.route("/artisan/dashboard")
def artisan_dashboard():

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    if logged_in_artisan_id is None:
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (logged_in_artisan_id,)
    ).fetchone()

    conn.close()

    if artisan is None:
        session.clear()

        return redirect(
            url_for("login")
        )

    return render_template(
        "artisan_dashboard.html",
        artisan=artisan
    )


# =========================================================
# EDIT ARTISAN PROFILE
# =========================================================

@app.route(
    "/artisan/edit-profile",
    methods=["GET", "POST"]
)
def edit_profile():

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    if logged_in_artisan_id is None:
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (logged_in_artisan_id,)
    ).fetchone()

    conn.close()

    if artisan is None:
        session.clear()

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        service = request.form.get(
            "service",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        country = request.form.get(
            "country",
            ""
        ).strip()

        state_region = request.form.get(
            "state_region",
            ""
        ).strip()

        city_area = request.form.get(
            "city_area",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        experience = request.form.get(
            "experience",
            ""
        ).strip()

        if not all([
            name,
            service,
            phone,
            country,
            state_region,
            city_area,
            location,
            experience
        ]):
            return render_template(
                "register_error.html",
                error_title="Missing Information",
                error_message=(
                    "Please complete all required "
                    "profile fields."
                )
            ), 400

        conn = get_db_connection()

        existing_phone = conn.execute(
            """
            SELECT id
            FROM artisans
            WHERE phone = ?
            AND id != ?
            """,
            (
                phone,
                logged_in_artisan_id
            )
        ).fetchone()

        if existing_phone:
            conn.close()

            return render_template(
                "register_error.html",
                error_title="Phone Number Already Registered",
                error_message=(
                    "Another artisan account is already "
                    "using this phone number."
                )
            ), 400

        if email:

            existing_email = conn.execute(
                """
                SELECT id
                FROM artisans
                WHERE email = ?
                AND id != ?
                """,
                (
                    email,
                    logged_in_artisan_id
                )
            ).fetchone()

            if existing_email:
                conn.close()

                return render_template(
                    "register_error.html",
                    error_title="Email Already Registered",
                    error_message=(
                        "Another artisan account is already "
                        "using this email address."
                    )
                ), 400

        conn.execute(
            """
            UPDATE artisans
            SET
                name = ?,
                service = ?,
                phone = ?,
                email = ?,
                country = ?,
                state_region = ?,
                city_area = ?,
                location = ?,
                experience = ?
            WHERE id = ?
            """,
            (
                name,
                service,
                phone,
                email or None,
                country,
                state_region,
                city_area,
                location,
                experience,
                logged_in_artisan_id
            )
        )

        conn.commit()
        conn.close()

        session["artisan_name"] = name

        return redirect(
            url_for("artisan_dashboard")
        )

    return render_template(
        "edit_profile.html",
        artisan=artisan
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# ARTISAN SERVICE REQUESTS
# =========================================================

@app.route(
    "/artisan/<int:artisan_id>/requests"
)
def artisan_requests(artisan_id):

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    if logged_in_artisan_id is None:
        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # MAKE SURE ARTISAN CAN ONLY VIEW THEIR OWN REQUESTS
    # -----------------------------------------------------

    if logged_in_artisan_id != artisan_id:
        return (
            "You are not authorized to view these requests.",
            403
        )

    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (artisan_id,)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT *
        FROM service_requests
        WHERE artisan_id = ?
        ORDER BY id DESC
        """,
        (artisan_id,)
    ).fetchall()

    conn.close()

    if artisan is None:
        session.clear()

        return redirect(
            url_for("login")
        )

    return render_template(
        "artisan_requests.html",
        artisan=artisan,
        requests=requests
    )


# =========================================================
# ARTISAN UPDATE REQUEST STATUS
# =========================================================

@app.route(
    "/artisan/request/<int:request_id>/status",
    methods=["POST"]
)
def update_artisan_request_status(request_id):

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    # -----------------------------------------------------
    # ARTISAN MUST BE LOGGED IN
    # -----------------------------------------------------

    if logged_in_artisan_id is None:
        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # GET REQUESTED STATUS
    # -----------------------------------------------------

    status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Completed"
    ]

    # -----------------------------------------------------
    # VALIDATE STATUS
    # -----------------------------------------------------

    if status not in allowed_statuses:
        return (
            "Invalid request status.",
            400
        )

    conn = get_db_connection()

    # -----------------------------------------------------
    # FIND REQUEST AND VERIFY OWNERSHIP
    # -----------------------------------------------------

    service_request = conn.execute(
        """
        SELECT *
        FROM service_requests
        WHERE id = ?
        AND artisan_id = ?
        """,
        (
            request_id,
            logged_in_artisan_id
        )
    ).fetchone()

    if service_request is None:
        conn.close()

        return (
            "Service request not found or "
            "you are not authorized to manage it.",
            403
        )

    # -----------------------------------------------------
    # UPDATE REQUEST STATUS
    # -----------------------------------------------------

    conn.execute(
        """
        UPDATE service_requests
        SET status = ?
        WHERE id = ?
        AND artisan_id = ?
        """,
        (
            status,
            request_id,
            logged_in_artisan_id
        )
    )

    conn.commit()
    conn.close()

    # -----------------------------------------------------
    # RETURN TO ARTISAN REQUESTS
    # -----------------------------------------------------

    return redirect(
        url_for(
            "artisan_requests",
            artisan_id=logged_in_artisan_id
        )
    )


# =========================================================
# ARTISAN VERIFICATION
# =========================================================

@app.route(
    "/verify/<int:artisan_id>",
    methods=["GET", "POST"]
)
def verify_artisan(artisan_id):

    logged_in_artisan_id = session.get(
        "artisan_id"
    )

    if logged_in_artisan_id is None:
        return redirect(
            url_for("login")
        )

    if logged_in_artisan_id != artisan_id:
        return (
            "You are not authorized to submit "
            "verification for this artisan.",
            403
        )

    conn = get_db_connection()

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE id = ?
        """,
        (artisan_id,)
    ).fetchone()

    conn.close()

    if artisan is None:
        return "Artisan not found.", 404

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

        if not all([
            full_name,
            service,
            location,
            phone,
            years_experience,
            verification_note
        ]):
            return render_template(
                "register_error.html",
                error_title="Missing Verification Information",
                error_message=(
                    "Please complete all verification "
                    "fields before submitting."
                )
            ), 400

        conn = get_db_connection()

        existing_request = conn.execute(
            """
            SELECT id
            FROM verification_requests
            WHERE artisan_id = ?
            AND status = 'Pending'
            """,
            (artisan_id,)
        ).fetchone()

        if existing_request:
            conn.close()

            return render_template(
                "register_error.html",
                error_title="Verification Already Submitted",
                error_message=(
                    "You already have a pending verification "
                    "request. Please wait for an admin to "
                    "review it."
                )
            ), 400

        conn.execute(
            """
            INSERT INTO verification_requests (
                artisan_id,
                full_name,
                service,
                location,
                phone,
                years_experience,
                verification_note,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
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

    return render_template(
        "verification.html",
        artisan=artisan
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin():

    conn = get_db_connection()

    artisans = conn.execute(
        """
        SELECT *
        FROM artisans
        ORDER BY id DESC
        """
    ).fetchall()

    pending_verifications = conn.execute(
        """
        SELECT
            verification_requests.*,
            artisans.name AS artisan_name
        FROM verification_requests
        JOIN artisans
            ON verification_requests.artisan_id = artisans.id
        WHERE verification_requests.status = 'Pending'
        ORDER BY verification_requests.id DESC
        """
    ).fetchall()

    pending_requests = conn.execute(
        """
        SELECT *
        FROM service_requests
        WHERE status = 'Pending'
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        artisans=artisans,
        pending_verifications=pending_verifications,
        pending_requests=pending_requests
    )


# =========================================================
# ADMIN APPROVE VERIFICATION
# =========================================================

@app.route(
    "/admin/verification/<int:request_id>/approve"
)
def approve_verification(request_id):

    conn = get_db_connection()

    verification_request = conn.execute(
        """
        SELECT *
        FROM verification_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if verification_request is None:
        conn.close()

        return (
            "Verification request not found.",
            404
        )

    artisan_id = verification_request[
        "artisan_id"
    ]

    conn.execute(
        """
        UPDATE artisans
        SET verified = 1
        WHERE id = ?
        """,
        (artisan_id,)
    )

    conn.execute(
        """
        UPDATE verification_requests
        SET status = 'Approved'
        WHERE id = ?
        """,
        (request_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# ADMIN REJECT VERIFICATION
# =========================================================

@app.route(
    "/admin/verification/<int:request_id>/reject"
)
def reject_verification(request_id):

    conn = get_db_connection()

    verification_request = conn.execute(
        """
        SELECT *
        FROM verification_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if verification_request is None:
        conn.close()

        return (
            "Verification request not found.",
            404
        )

    conn.execute(
        """
        UPDATE verification_requests
        SET status = 'Rejected'
        WHERE id = ?
        """,
        (request_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# ADMIN SERVICE REQUESTS
# =========================================================

@app.route("/admin/requests")
def admin_requests():

    conn = get_db_connection()

    requests = conn.execute(
        """
        SELECT
            service_requests.*,
            artisans.name AS artisan_name
        FROM service_requests
        LEFT JOIN artisans
            ON service_requests.artisan_id = artisans.id
        ORDER BY service_requests.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_requests.html",
        requests=requests
    )


# =========================================================
# ADMIN UPDATE REQUEST STATUS
# =========================================================

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
        return (
            "Invalid request status.",
            400
        )

    conn = get_db_connection()

    service_request = conn.execute(
        """
        SELECT *
        FROM service_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if service_request is None:
        conn.close()

        return (
            "Service request not found.",
            404
        )

    conn.execute(
        """
        UPDATE service_requests
        SET status = ?
        WHERE id = ?
        """,
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


# =========================================================
# ADMIN ARTISANS
# =========================================================

@app.route("/admin/artisans")
def admin_artisans():

    conn = get_db_connection()

    artisans = conn.execute(
        """
        SELECT *
        FROM artisans
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_artisans.html",
        artisans=artisans
    )


# =========================================================
# CREATE DATABASE ON STARTUP
# =========================================================

create_database()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)