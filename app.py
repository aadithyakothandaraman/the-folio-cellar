
import json
import math
import os
import time
import uuid
from datetime import date, datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

# Maximum upload request size: 10 MB.
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

ALLOWED_CURRENCIES = {"INR", "GBP", "USD", "EUR", "AUD", "CAD"}

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "GBP": "£",
    "USD": "$",
    "EUR": "€",
    "AUD": "A$",
    "CAD": "CA$",
}

READING_STATUSES = {
    "Want to Read",
    "Currently Reading",
    "Completed",
    "On Hold",
}

DEFAULT_DISPLAY_CURRENCY = "INR"
EXCHANGE_RATE_CACHE_SECONDS = 60 * 60

# In-memory cache: one entry per target currency.
# The original book prices are never modified.
_exchange_rate_cache = {}


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def get_home_redirect():
    """Return to My Books while preserving the selected sort order."""
    sort_by = request.form.get("sort_by", "title").strip().lower()

    if sort_by == "recent":
        sort_by = "date_added"

    if sort_by not in {
        "title", "date_added", "author", "genre", "publisher"
    }:
        sort_by = "title"

    sort_order = request.form.get("sort_order", "asc").strip().lower()

    if sort_order not in {"asc", "desc"}:
        sort_order = "asc"

    return redirect(
        url_for("library", sort=sort_by, order=sort_order)
    )


def is_ajax_request():
    """Identify requests that expect a JSON response."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def get_exchange_rates(target_currency):
    """
    Return exchange rates expressed as units of each source currency
    per one unit of the selected target currency.

    Rates are cached for one hour. If the service is unavailable,
    a previously cached rate may be used as a fallback.
    """
    if target_currency not in ALLOWED_CURRENCIES:
        return None, None

    now = time.time()
    cached = _exchange_rate_cache.get(target_currency)

    if cached and now - cached["fetched_at"] < EXCHANGE_RATE_CACHE_SECONDS:
        return cached["rates"], cached["fetched_at"]

    symbols = ",".join(
        sorted(ALLOWED_CURRENCIES - {target_currency})
    )

    url = (
        "https://api.frankfurter.dev/v1/latest"
        f"?base={target_currency}&symbols={symbols}"
    )

    try:
        req = Request(
            url,
            headers={"User-Agent": "PersonalLibraryManager/1.0"},
        )

        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        rates = data.get("rates", {})
        rates[target_currency] = 1.0

        cleaned_rates = {}

        for currency, rate in rates.items():
            if currency not in ALLOWED_CURRENCIES:
                continue

            try:
                numeric_rate = float(rate)
            except (TypeError, ValueError):
                continue

            if math.isfinite(numeric_rate) and numeric_rate > 0:
                cleaned_rates[currency] = numeric_rate

        if target_currency not in cleaned_rates:
            raise ValueError("The exchange-rate response was incomplete.")

        fetched_at = time.time()

        _exchange_rate_cache[target_currency] = {
            "rates": cleaned_rates,
            "fetched_at": fetched_at,
        }

        return cleaned_rates, fetched_at

    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        app.logger.warning(
            "Exchange-rate service unavailable for %s.",
            target_currency,
        )

        if cached:
            return cached["rates"], cached["fetched_at"]

        return None, None


def parse_book_form():
    """Read and validate the shared Add/Edit book form fields."""
    title = request.form.get("title", "").strip()
    authors = request.form.get("authors", "").strip()

    if not title or not authors:
        raise ValueError("Book title and author are required.")

    isbn = request.form.get("isbn", "").strip() or None

    if isbn and len(isbn) > 40:
        raise ValueError("ISBN must not exceed 40 characters.")

    currency = request.form.get("currency", "INR").strip().upper()

    if currency not in ALLOWED_CURRENCIES:
        raise ValueError("Please select a supported currency.")

    year_text = request.form.get("publication_year", "").strip()
    mrp_text = request.form.get("mrp", "").strip()
    rating_text = request.form.get("goodreads_rating", "").strip()

    try:
        publication_year = int(year_text) if year_text else None
    except ValueError:
        raise ValueError("Publication year must be a whole number.")

    if publication_year is not None and not (
        1901 <= publication_year <= 2155
    ):
        raise ValueError("Publication year must be between 1901 and 2155.")

    try:
        mrp = float(mrp_text) if mrp_text else None
    except ValueError:
        raise ValueError("Enter a valid MRP.")

    if mrp is not None and (not math.isfinite(mrp) or mrp < 0):
        raise ValueError("MRP must be a valid, non-negative number.")

    try:
        goodreads_rating = float(rating_text) if rating_text else None
    except ValueError:
        raise ValueError("Enter a valid Goodreads rating.")

    if goodreads_rating is not None and (
        not math.isfinite(goodreads_rating)
        or not 0 <= goodreads_rating <= 5
    ):
        raise ValueError("Goodreads rating must be between 0 and 5.")

    return {
        "title": title,
        "authors": authors,
        "isbn": isbn,
        "publisher": request.form.get("publisher", "").strip() or None,
        "publication_year": publication_year,
        "language": request.form.get("language", "").strip() or "English",
        "genre": request.form.get("genre", "").strip() or None,
        "description": request.form.get("description", "").strip() or None,
        "mrp": mrp,
        "currency": currency,
        "goodreads_rating": goodreads_rating,
    }


def parse_optional_date(value, label):
    """Parse an optional HTML date input."""
    value = value.strip()

    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} must be a valid date.")


def parse_non_negative_integer(value, label, allow_blank=False):
    """Parse an integer while rejecting negative and malformed values."""
    value = value.strip()

    if not value and allow_blank:
        return None

    if not value:
        raise ValueError(f"{label} is required.")

    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.")

    if number < 0:
        raise ValueError(f"{label} cannot be negative.")

    return number


def save_cover_upload(cover_file):
    """Save an optional cover and return its relative path and full path."""
    if not cover_file or not cover_file.filename:
        return None, None

    safe_name = secure_filename(cover_file.filename)
    extension = os.path.splitext(safe_name)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Cover must be JPG, JPEG, PNG, or WebP.")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{extension}"
    full_path = os.path.join(UPLOAD_FOLDER, unique_filename)

    cover_file.save(full_path)

    return f"uploads/{unique_filename}", full_path


def remove_new_cover_if_needed(full_path, saved):
    """Remove a newly uploaded image if its database operation failed."""
    if full_path and not saved and os.path.isfile(full_path):
        try:
            os.remove(full_path)
        except OSError:
            app.logger.exception("Could not clean up uploaded cover.")


def remove_old_cover(relative_path):
    """Remove an uploaded cover without touching files outside uploads."""
    if not relative_path or not relative_path.startswith("uploads/"):
        return

    upload_root = os.path.realpath(UPLOAD_FOLDER)
    old_full_path = os.path.realpath(
        os.path.join(app.root_path, "static", relative_path)
    )

    try:
        if (
            os.path.commonpath([upload_root, old_full_path]) == upload_root
            and os.path.isfile(old_full_path)
        ):
            os.remove(old_full_path)
    except (OSError, ValueError):
        app.logger.exception("Could not remove old cover image.")


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    """Display the new homepage."""
    return render_template("home.html")


# ---------------------------------------------------------
# READING DASHBOARD
# ---------------------------------------------------------

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Display statistics calculated from the existing book collection."""
    connection = None
    cursor = None

    stats = {
        "total_books": 0,
        "completed": 0,
        "currently_reading": 0,
        "want_to_read": 0,
        "on_hold": 0,
        "favorites": 0,
        "rated_books": 0,
        "average_rating": None,
        "total_pages": 0,
        "genres": 0,
    }

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                COUNT(*) AS total_books,
                COALESCE(SUM(reading_status = 'Completed'), 0)
                    AS completed,
                COALESCE(SUM(reading_status = 'Currently Reading'), 0)
                    AS currently_reading,
                COALESCE(SUM(reading_status = 'Want to Read'), 0)
                    AS want_to_read,
                COALESCE(SUM(reading_status = 'On Hold'), 0)
                    AS on_hold,
                COALESCE(SUM(is_favorite = 1), 0) AS favorites,
                COUNT(personal_rating) AS rated_books,
                AVG(personal_rating) AS average_rating,
                COALESCE(SUM(
                    CASE
                        WHEN reading_status = 'Completed'
                        THEN COALESCE(total_pages, current_page, 0)
                        ELSE 0
                    END
                ), 0) AS total_pages,
                COUNT(DISTINCT NULLIF(TRIM(genre), '')) AS genres
            FROM books
        """)

        result = cursor.fetchone() or {}

        for key in stats:
            stats[key] = result.get(key, stats[key])

        stats["average_rating"] = (
            round(float(stats["average_rating"]), 1)
            if stats["average_rating"] is not None
            else None
        )

        cursor.execute("""
            SELECT genre, COUNT(*) AS book_count
            FROM books
            WHERE genre IS NOT NULL AND TRIM(genre) <> ''
            GROUP BY genre
            ORDER BY book_count DESC, genre ASC
        """)
        genre_stats = cursor.fetchall()

        cursor.execute("""
            SELECT title, authors, completed_at
            FROM books
            WHERE reading_status = 'Completed'
            ORDER BY completed_at DESC, title ASC
            LIMIT 5
        """)
        recently_completed = cursor.fetchall()

        return render_template(
            "dashboard.html",
            stats=stats,
            genre_stats=genre_stats,
            recently_completed=recently_completed,
            error=False,
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load the reading dashboard.")
        return render_template(
            "dashboard.html",
            stats=stats,
            genre_stats=[],
            recently_completed=[],
            error=True,
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ---------------------------------------------------------
# READING JOURNAL
# ---------------------------------------------------------

@app.route("/journal", methods=["GET"])
def reading_journal():
    """Display saved journal entries."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                j.entry_id,
                j.book_id,
                j.entry_type,
                j.title,
                j.content,
                j.quote_author,
                j.created_at,
                b.title AS book_title
            FROM reading_journal AS j
            LEFT JOIN books AS b ON b.book_id = j.book_id
            ORDER BY j.created_at DESC, j.entry_id DESC
        """)
        entries = cursor.fetchall()

        return render_template(
            "journal.html",
            entries=entries,
            error=False,
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load the reading journal.")
        return render_template(
            "journal.html",
            entries=[],
            error=True,
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/journal/add", methods=["GET", "POST"])
def add_journal_entry():
    """Create a reflection, memorable quote, or lesson."""
    connection = None
    cursor = None

    if request.method == "GET":
        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT book_id, title, authors
                FROM books
                ORDER BY title ASC
            """)
            books = cursor.fetchall()

            return render_template(
                "journal_form.html",
                entry=None,
                books=books,
                action="Add",
            )

        except mysql.connector.Error:
            app.logger.exception("Could not load books for the journal.")
            flash("Unable to open the journal form. Please try again.")
            return redirect(url_for("reading_journal"))

        finally:
            if cursor is not None:
                cursor.close()

            if connection is not None and connection.is_connected():
                connection.close()

    try:
        entry_type = request.form.get("entry_type", "Reflection").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        quote_author = request.form.get("quote_author", "").strip() or None
        book_id_text = request.form.get("book_id", "").strip()

        if entry_type not in {
            "Reflection", "Memorable Quote", "Lesson Learned"
        }:
            raise ValueError("Please select a valid journal entry type.")

        if not title or not content:
            raise ValueError("Entry title and content are required.")

        if len(title) > 255:
            raise ValueError("Entry title must not exceed 255 characters.")

        if quote_author and len(quote_author) > 255:
            raise ValueError("Quote author must not exceed 255 characters.")

        if entry_type != "Memorable Quote":
            quote_author = None

        if book_id_text:
            try:
                book_id = int(book_id_text)
            except ValueError:
                raise ValueError("Please select a valid book.")
        else:
            book_id = None

        connection = get_db_connection()
        cursor = connection.cursor()

        if book_id is not None:
            cursor.execute(
                "SELECT book_id FROM books WHERE book_id = %s",
                (book_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("The selected book could not be found.")

        cursor.execute("""
            INSERT INTO reading_journal
                (book_id, entry_type, title, content, quote_author)
            VALUES (%s, %s, %s, %s, %s)
        """, (book_id, entry_type, title, content, quote_author))

        connection.commit()
        flash("Journal entry saved successfully!")
        return redirect(url_for("reading_journal"))

    except ValueError as error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        flash(str(error))
        return redirect(url_for("add_journal_entry"))

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        app.logger.exception("Could not save journal entry.")
        flash("Unable to save the journal entry. Please try again.")
        return redirect(url_for("reading_journal"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/journal/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_journal_entry(entry_id):
    """Edit an existing journal entry."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT entry_id, book_id, entry_type, title, content, quote_author
            FROM reading_journal
            WHERE entry_id = %s
        """, (entry_id,))
        entry = cursor.fetchone()

        if entry is None:
            flash("Journal entry not found.")
            return redirect(url_for("reading_journal"))

        if request.method == "GET":
            cursor.execute("""
                SELECT book_id, title, authors
                FROM books
                ORDER BY title ASC
            """)
            books = cursor.fetchall()

            return render_template(
                "journal_form.html",
                entry=entry,
                books=books,
                action="Edit",
            )

        entry_type = request.form.get("entry_type", "Reflection").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        quote_author = request.form.get("quote_author", "").strip() or None
        book_id_text = request.form.get("book_id", "").strip()

        if entry_type not in {
            "Reflection", "Memorable Quote", "Lesson Learned"
        }:
            raise ValueError("Please select a valid journal entry type.")

        if not title or not content:
            raise ValueError("Entry title and content are required.")

        if len(title) > 255:
            raise ValueError("Entry title must not exceed 255 characters.")

        if quote_author and len(quote_author) > 255:
            raise ValueError("Quote author must not exceed 255 characters.")

        if entry_type != "Memorable Quote":
            quote_author = None

        if book_id_text:
            try:
                book_id = int(book_id_text)
            except ValueError:
                raise ValueError("Please select a valid book.")
        else:
            book_id = None

        if book_id is not None:
            cursor.execute(
                "SELECT book_id FROM books WHERE book_id = %s",
                (book_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("The selected book could not be found.")

        cursor.execute("""
            UPDATE reading_journal
            SET book_id = %s,
                entry_type = %s,
                title = %s,
                content = %s,
                quote_author = %s
            WHERE entry_id = %s
        """, (book_id, entry_type, title, content, quote_author, entry_id))

        connection.commit()
        flash("Journal entry updated successfully!")

    except ValueError as error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        flash(str(error))

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        app.logger.exception("Could not update journal entry %s.", entry_id)
        flash("Unable to update the journal entry. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("reading_journal"))


@app.route("/journal/<int:entry_id>/delete", methods=["POST"])
def delete_journal_entry(entry_id):
    """Delete a journal entry."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM reading_journal WHERE entry_id = %s",
            (entry_id,),
        )

        if cursor.rowcount == 0:
            flash("Journal entry not found.")
        else:
            connection.commit()
            flash("Journal entry deleted.")

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        app.logger.exception("Could not delete journal entry %s.", entry_id)
        flash("Unable to delete the journal entry. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("reading_journal"))

# ---------------------------------------------------------
# MY BOOKS
# ---------------------------------------------------------

@app.route("/books", methods=["GET"])
def library():
    """Display the existing library with sorting support."""
    connection = None
    cursor = None

    sort_by = request.args.get("sort", "title").strip().lower()

    if sort_by == "recent":
        sort_by = "date_added"

    if sort_by not in {
        "title", "date_added", "author", "genre", "publisher"
    }:
        sort_by = "title"

    sort_order = request.args.get("order", "asc").strip().lower()

    if sort_order not in {"asc", "desc"}:
        sort_order = "asc"

    sort_columns = {
        "title": "title",
        "date_added": "created_at",
        "author": "authors",
        "genre": "genre",
        "publisher": "publisher",
    }

    order_column = sort_columns[sort_by]
    sort_direction = "DESC" if sort_order == "desc" else "ASC"

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            f"""
            SELECT
                book_id,
                title,
                authors,
                isbn,
                publisher,
                publication_year,
                language,
                genre,
                description,
                mrp,
                currency,
                goodreads_rating,
                is_favorite,
                personal_rating,
                cover_image_path,
                created_at,
                reading_status,
                current_page,
                total_pages,
                started_at,
                completed_at
            FROM books
            ORDER BY
                {order_column} {sort_direction}, title ASC, book_id ASC
            """
        )

        books = cursor.fetchall()

        # Preserve Recently Added badge behaviour.
        now = datetime.now()
        recent_window = timedelta(days=7)

        for book in books:
            created_at = book.get("created_at")
            book["is_new"] = False

            if created_at is not None:
                if created_at.tzinfo is not None:
                    created_at = created_at.replace(tzinfo=None)

                age = now - created_at
                book["is_new"] = timedelta(0) <= age <= recent_window

            book["is_favorite"] = bool(book.get("is_favorite", False))

        return render_template(
            "index.html",
            books=books,
            error=False,
            reading_statuses=sorted(READING_STATUSES),
            currency_symbols=CURRENCY_SYMBOLS,
            allowed_currencies=sorted(ALLOWED_CURRENCIES),
            sort_by=sort_by,
            sort_order=sort_order,
        )

    except mysql.connector.Error:
        app.logger.exception("Could not retrieve books.")

        return render_template(
            "index.html",
            books=[],
            error=True,
            reading_statuses=sorted(READING_STATUSES),
            currency_symbols=CURRENCY_SYMBOLS,
            allowed_currencies=sorted(ALLOWED_CURRENCIES),
            sort_by=sort_by,
            sort_order=sort_order,
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ---------------------------------------------------------
# WISHLIST
# ---------------------------------------------------------

@app.route("/wishlist", methods=["GET"])
def wishlist():
    """Display books the user hopes to add to their collection."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT wishlist_id, title, authors, isbn, notes, created_at
            FROM wishlist
            ORDER BY created_at DESC, wishlist_id DESC
        """)

        wishlist_books = cursor.fetchall()

        return render_template(
            "wishlist.html",
            items=wishlist_books,
            error=False,
        )

    except mysql.connector.Error:
        app.logger.exception("Could not retrieve wishlist.")
        flash("Unable to load your Wishlist. Please try again.")
        return render_template("wishlist.html",items=[],error=True,)

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/wishlist/add", methods=["POST"])
def add_to_wishlist():
    """Add a book to the wishlist without adding it to owned books."""
    connection = None
    cursor = None

    title = request.form.get("title", "").strip()
    authors = request.form.get("authors", "").strip()
    isbn = request.form.get("isbn", "").strip() or None
    notes = request.form.get("notes", "").strip() or None

    if not title or not authors:
        flash("Book title and author are required.")
        return redirect(url_for("wishlist"))

    if len(title) > 255:
        flash("The title must not exceed 255 characters.")
        return redirect(url_for("wishlist"))

    if len(authors) > 255:
        flash("The author field must not exceed 255 characters.")
        return redirect(url_for("wishlist"))

    if isbn and len(isbn) > 40:
        flash("ISBN must not exceed 40 characters.")
        return redirect(url_for("wishlist"))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Avoid adding a book that's already in My Books.
        if isbn:
            cursor.execute(
                "SELECT book_id FROM books WHERE isbn = %s LIMIT 1",
                (isbn,),
            )
            if cursor.fetchone():
                flash("This book is already in your collection.")
                return redirect(url_for("wishlist"))

        cursor.execute(
            """
            SELECT wishlist_id
            FROM wishlist
            WHERE LOWER(title) = LOWER(%s)
              AND LOWER(authors) = LOWER(%s)
            LIMIT 1
            """,
            (title, authors),
        )

        if cursor.fetchone():
            flash("This book is already in your Wishlist.")
            return redirect(url_for("wishlist"))

        cursor.execute(
            """
            INSERT INTO wishlist (title, authors, isbn, notes)
            VALUES (%s, %s, %s, %s)
            """,
            (title, authors, isbn, notes),
        )

        connection.commit()
        flash(f'"{title}" was added to your Wishlist.')

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception("Could not add a wishlist item.")
        flash("Unable to add this book to your Wishlist. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("wishlist"))


@app.route("/wishlist/<int:wishlist_id>/remove", methods=["POST"])
def remove_from_wishlist(wishlist_id):
    """Remove a book from the wishlist."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT title FROM wishlist WHERE wishlist_id = %s",
            (wishlist_id,),
        )
        item = cursor.fetchone()

        if item is None:
            flash("Wishlist item not found.")
            return redirect(url_for("wishlist"))

        cursor.execute(
            "DELETE FROM wishlist WHERE wishlist_id = %s",
            (wishlist_id,),
        )

        connection.commit()
        flash(f'"{item["title"]}" was removed from your Wishlist.')

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception(
            "Could not remove wishlist item %s.", wishlist_id
        )
        flash("Unable to remove this item. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("wishlist"))


@app.route("/wishlist/<int:wishlist_id>/move", methods=["POST"])
def move_wishlist_to_library(wishlist_id):
    """Move a wishlist item into My Books, then remove it from Wishlist."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT wishlist_id, title, authors, isbn
            FROM wishlist
            WHERE wishlist_id = %s
            FOR UPDATE
            """,
            (wishlist_id,),
        )
        item = cursor.fetchone()

        if item is None:
            connection.rollback()
            flash("Wishlist item not found.")
            return redirect(url_for("wishlist"))

        # Check for an existing book before inserting.
        if item["isbn"]:
            cursor.execute(
                "SELECT book_id FROM books WHERE isbn = %s LIMIT 1",
                (item["isbn"],),
            )
            duplicate = cursor.fetchone()
        else:
            cursor.execute(
                """
                SELECT book_id
                FROM books
                WHERE LOWER(title) = LOWER(%s)
                  AND LOWER(authors) = LOWER(%s)
                LIMIT 1
                """,
                (item["title"], item["authors"]),
            )
            duplicate = cursor.fetchone()

        if duplicate:
            connection.rollback()
            flash(
                "This book is already in My Books. "
                "The Wishlist item has been kept."
            )
            return redirect(url_for("wishlist"))

        # The remaining book fields use the database's existing
        # defaults or nullable values, just as defined in your schema.
        cursor.execute(
            """
            INSERT INTO books (title, authors, isbn)
            VALUES (%s, %s, %s)
            """,
            (item["title"], item["authors"], item["isbn"]),
        )

        cursor.execute(
            "DELETE FROM wishlist WHERE wishlist_id = %s",
            (wishlist_id,),
        )

        connection.commit()
        flash(
            f'"{item["title"]}" was moved to My Books successfully.'
        )

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception(
            "Could not move wishlist item %s to My Books.",
            wishlist_id,
        )
        flash(
            "Unable to move this book. It remains in your Wishlist. "
            "Check your database schema and try again."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("wishlist"))


@app.route("/currency/convert", methods=["POST"])
def convert_book_currency():
    """Convert a price for display only; never modify the stored book."""
    payload = request.get_json(silent=True) or {}
    source_currency = str(payload.get("source_currency", "")).strip().upper()
    target_currency = str(payload.get("target_currency", "")).strip().upper()

    if (
        source_currency not in ALLOWED_CURRENCIES
        or target_currency not in ALLOWED_CURRENCIES
    ):
        return jsonify({
            "success": False,
            "error": "Unsupported currency.",
        }), 400

    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Invalid amount.",
        }), 400

    if not math.isfinite(amount) or amount < 0:
        return jsonify({
            "success": False,
            "error": "Invalid amount.",
        }), 400

    if source_currency == target_currency:
        return jsonify({
            "success": True,
            "amount": amount,
            "currency": target_currency,
        })

    rates, _ = get_exchange_rates(target_currency)
    source_rate = rates.get(source_currency) if rates else None

    if not source_rate or source_rate <= 0:
        return jsonify({
            "success": False,
            "error": "Exchange rates are temporarily unavailable.",
        }), 503

    converted_amount = amount / source_rate

    if not math.isfinite(converted_amount):
        return jsonify({
            "success": False,
            "error": "Conversion failed.",
        }), 503

    return jsonify({
        "success": True,
        "amount": converted_amount,
        "currency": target_currency,
    })


# ---------------------------------------------------------
# FAVORITES
# ---------------------------------------------------------

@app.route("/books/<int:book_id>/favorite", methods=["POST"])
def toggle_favorite(book_id):
    """
    Toggle a book's favorite status.

    AJAX requests receive JSON and do not require a page redirect.
    Regular form submissions retain redirect behaviour as a fallback.
    """
    ajax = is_ajax_request()
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT title, is_favorite
            FROM books
            WHERE book_id = %s
            """,
            (book_id,),
        )

        book = cursor.fetchone()

        if book is None:
            message = "Book not found."

            if ajax:
                return jsonify({
                    "success": False,
                    "error": message,
                }), 404

            flash(message)
            return get_home_redirect()

        new_favorite_status = not bool(book["is_favorite"])

        cursor.execute(
            """
            UPDATE books
            SET is_favorite = %s
            WHERE book_id = %s
            """,
            (new_favorite_status, book_id),
        )

        connection.commit()

        if new_favorite_status:
            message = f'"{book["title"]}" added to Favorites.'
        else:
            message = f'"{book["title"]}" removed from Favorites.'

        if ajax:
            return jsonify({
                "success": True,
                "book_id": book_id,
                "is_favorite": new_favorite_status,
                "message": message,
            })

        flash(message)
        return get_home_redirect()

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception(
            "Could not update favorite status for book %s.",
            book_id,
        )

        message = "Unable to update Favorites. Please try again."

        if ajax:
            return jsonify({
                "success": False,
                "error": message,
            }), 500

        flash(message)
        return get_home_redirect()

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()



# ---------------------------------------------------------
# PERSONAL RATINGS
# ---------------------------------------------------------

@app.route("/books/<int:book_id>/personal-rating", methods=["POST"])
def update_personal_rating(book_id):
    """
    Save a personal rating between 1 and 5.

    An empty rating clears the personal rating.
    Goodreads ratings remain unchanged.

    AJAX requests receive JSON without a page redirect.
    Regular form submissions retain redirect behaviour.
    """
    ajax = is_ajax_request()
    connection = None
    cursor = None

    try:
        rating_text = request.form.get("personal_rating", "").strip()

        if rating_text == "":
            personal_rating = None
        else:
            try:
                personal_rating = int(rating_text)
            except ValueError:
                raise ValueError("Please select a valid personal rating.")

            if personal_rating not in {1, 2, 3, 4, 5}:
                raise ValueError("Personal rating must be between 1 and 5.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT book_id, title FROM books WHERE book_id = %s",
            (book_id,),
        )
        book = cursor.fetchone()

        if book is None:
            message = "Book not found."

            if ajax:
                return jsonify({
                    "success": False,
                    "error": message,
                }), 404

            flash(message)
            return get_home_redirect()

        cursor.execute(
            """
            UPDATE books
            SET personal_rating = %s
            WHERE book_id = %s
            """,
            (personal_rating, book_id),
        )

        connection.commit()

        if personal_rating is None:
            message = "Your personal rating has been cleared."
        else:
            message = (
                f"Your {personal_rating}-star rating has been saved."
            )

        if ajax:
            return jsonify({
                "success": True,
                "book_id": book_id,
                "personal_rating": personal_rating,
                "message": message,
            })

        flash(message)
        return get_home_redirect()

    except ValueError as error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        if ajax:
            return jsonify({
                "success": False,
                "error": str(error),
            }), 400

        flash(str(error))

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception(
            "Could not update personal rating for book %s.",
            book_id,
        )

        message = "Unable to save your personal rating. Please try again."

        if ajax:
            return jsonify({
                "success": False,
                "error": message,
            }), 500

        flash(message)

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return get_home_redirect()


@app.route("/books/add", methods=["GET", "POST"])
def add_book():
    if request.method == "GET":
        return render_template("add_book.html")

    new_cover_full_path = None
    saved_to_database = False
    connection = None
    cursor = None

    try:
        book = parse_book_form()

        cover_image_path, new_cover_full_path = save_cover_upload(
            request.files.get("cover_image")
        )

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO books (
                title, authors, isbn, publisher,
                publication_year, language, genre,
                description, mrp, currency, goodreads_rating,
                cover_image_path
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
            )
            """,
            (
                book["title"],
                book["authors"],
                book["isbn"],
                book["publisher"],
                book["publication_year"],
                book["language"],
                book["genre"],
                book["description"],
                book["mrp"],
                book["currency"],
                book["goodreads_rating"],
                cover_image_path,
            ),
        )

        connection.commit()
        saved_to_database = True

        flash("Book added successfully!")
        return redirect(url_for("library"))

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("add_book"))

    except (mysql.connector.Error, OSError):
        app.logger.exception("Could not save the book.")
        flash("Unable to save the book. Check the details and try again.")
        return redirect(url_for("add_book"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

        remove_new_cover_if_needed(
            new_cover_full_path, saved_to_database
        )


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    connection = None
    cursor = None
    new_cover_full_path = None
    saved_to_database = False

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM books WHERE book_id = %s",
            (book_id,),
        )
        book_record = cursor.fetchone()

        if book_record is None:
            flash("Book not found.")
            return redirect(url_for("library"))

        if not book_record.get("isbn"):
            old_isbn_13 = book_record.get("isbn_13")
            old_isbn_10 = book_record.get("isbn_10")

            if old_isbn_13 and old_isbn_10:
                book_record["isbn"] = f"{old_isbn_13}; {old_isbn_10}"
            else:
                book_record["isbn"] = old_isbn_13 or old_isbn_10 or ""

        if request.method == "GET":
            return render_template("edit_book.html", book=book_record)

        updated = parse_book_form()

        cover_image_path = book_record.get("cover_image_path")
        uploaded_path, new_cover_full_path = save_cover_upload(
            request.files.get("cover_image")
        )

        if uploaded_path:
            cover_image_path = uploaded_path

        cursor.execute(
            """
            UPDATE books
            SET
                title = %s,
                authors = %s,
                isbn = %s,
                publisher = %s,
                publication_year = %s,
                language = %s,
                genre = %s,
                description = %s,
                mrp = %s,
                currency = %s,
                goodreads_rating = %s,
                cover_image_path = %s
            WHERE book_id = %s
            """,
            (
                updated["title"],
                updated["authors"],
                updated["isbn"],
                updated["publisher"],
                updated["publication_year"],
                updated["language"],
                updated["genre"],
                updated["description"],
                updated["mrp"],
                updated["currency"],
                updated["goodreads_rating"],
                cover_image_path,
                book_id,
            ),
        )

        connection.commit()
        saved_to_database = True

        if uploaded_path:
            old_cover = book_record.get("cover_image_path")
            if old_cover and old_cover != uploaded_path:
                remove_old_cover(old_cover)

        flash("Book updated successfully!")
        return redirect(url_for("library"))

    except ValueError as error:
        flash(str(error))
        return redirect(url_for("edit_book", book_id=book_id))

    except (mysql.connector.Error, OSError):
        app.logger.exception("Could not update book %s.", book_id)
        flash("Unable to update the book. Please try again.")
        return redirect(url_for("edit_book", book_id=book_id))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

        remove_new_cover_if_needed(
            new_cover_full_path, saved_to_database
        )


@app.route("/books/<int:book_id>/reading", methods=["POST"])
def update_reading_progress(book_id):
    """Update reading progress without changing bibliographic details."""
    connection = None
    cursor = None

    try:
        status = request.form.get("reading_status", "").strip()

        if status not in READING_STATUSES:
            raise ValueError("Please select a valid reading status.")

        current_page = parse_non_negative_integer(
            request.form.get("current_page", "0"),
            "Current page",
        )

        total_pages = parse_non_negative_integer(
            request.form.get("total_pages", ""),
            "Total pages",
            allow_blank=True,
        )

        if total_pages == 0:
            raise ValueError("Total pages must be greater than zero.")

        if total_pages is not None and current_page > total_pages:
            raise ValueError(
                "Current page cannot exceed the total number of pages."
            )

        started_at = parse_optional_date(
            request.form.get("started_at", ""),
            "Start date",
        )
        completed_at = parse_optional_date(
            request.form.get("completed_at", ""),
            "Completion date",
        )

        today = date.today()

        if status == "Currently Reading" and started_at is None:
            started_at = today

        if status == "Completed":
            if total_pages is not None:
                current_page = total_pages

            if completed_at is None:
                completed_at = today

            if started_at is None:
                started_at = completed_at

        else:
            completed_at = None

        if (
            started_at is not None
            and completed_at is not None
            and completed_at < started_at
        ):
            raise ValueError(
                "Completion date cannot be earlier than the start date."
            )

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT book_id FROM books WHERE book_id = %s",
            (book_id,),
        )

        if cursor.fetchone() is None:
            flash("Book not found.")
            return get_home_redirect()

        cursor.execute(
            """
            UPDATE books
            SET
                reading_status = %s,
                current_page = %s,
                total_pages = %s,
                started_at = %s,
                completed_at = %s
            WHERE book_id = %s
            """,
            (
                status,
                current_page,
                total_pages,
                started_at,
                completed_at,
                book_id,
            ),
        )

        connection.commit()
        flash("Reading progress saved!")

    except ValueError as error:
        flash(str(error))

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception(
            "Could not update reading progress for book %s.",
            book_id,
        )
        flash("Unable to save reading progress. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return get_home_redirect()


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT book_id, title, cover_image_path
            FROM books
            WHERE book_id = %s
            """,
            (book_id,),
        )
        book = cursor.fetchone()

        if book is None:
            flash("Book not found. It may already have been deleted.")
            return redirect(url_for("library"))

        cover_image_path = book.get("cover_image_path")
        title = book["title"]

        cursor.execute(
            "DELETE FROM books WHERE book_id = %s",
            (book_id,),
        )
        connection.commit()

        if cover_image_path:
            cursor.execute(
                """
                SELECT COUNT(*) AS usage_count
                FROM books
                WHERE cover_image_path = %s
                """,
                (cover_image_path,),
            )
            result = cursor.fetchone()

            if result["usage_count"] == 0:
                remove_old_cover(cover_image_path)

        flash(f'"{title}" was deleted successfully!')
        return redirect(url_for("library"))

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception("Could not delete book %s.", book_id)
        flash("Unable to delete the book. Please try again.")
        return redirect(url_for("library"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.errorhandler(413)
def file_too_large(error):
    flash("The upload is too large. Please use an image under 10 MB.")
    return redirect(url_for("add_book"))


if __name__ == "__main__":
    # Development only. Do not expose this server publicly.
    app.run(debug=True)
