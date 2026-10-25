# The Folio Cellar

A personal library management web application built with **Python, Flask, and MySQL**, designed to help readers organise their physical book collections, track their reading journeys, and maintain a personal record of the books they own.

The Folio Cellar brings book cataloguing, reading progress, personal ratings, wishlists, and reading reflections together in one place, with a warm, book-inspired interface.

## Features

### Book Collection Management
- Add books with details such as title, authors, ISBN, publisher, publication year, edition, language, genre, and description.
- Upload book cover images.
- Record the printed retail price and its original currency.
- Enter Goodreads ratings manually.
- Edit book information and remove books from the collection.
- Browse book details in expandable library cards.

### Search, Filtering, and Sorting
- Search the collection by title, author, ISBN, genre, or publisher.
- Filter books by reading status and favourites.
- Sort books by title, date added, author, genre, or publisher.
- Choose ascending or descending order.
- Highlight recently added books.

### Reading Progress
- Track reading status using the following categories:
  - Want to Read
  - Currently Reading
  - Completed
  - On Hold
- Record current page and total page count.
- Track reading start and completion dates.
- View reading progress through page counts and progress indicators.

### Personal Ratings and Favourites
- Give books a personal rating from one to five stars.
- Update or clear personal ratings.
- Mark books as favourites and filter the collection accordingly.
- View rating and favourite statistics on the reading dashboard.

### Wishlist
- Maintain a separate wishlist for books you want to acquire.
- Store book titles, authors, ISBNs, and notes.
- Move wishlist entries into the main collection.
- Remove books from the wishlist.
- Check for potential duplicates when adding or moving books.

### Reading Dashboard
- View statistics about the collection and reading activity.
- Track total books, completed books, books currently being read, books on hold, and books waiting to be read.
- View favourite and personally rated book counts.
- See average personal ratings, represented genres, and recently completed books.

### Reading Journal
- Record reflections, memorable quotes, and lessons learned from books.
- Optionally associate journal entries with books in the collection.
- Record the author of a memorable quote.
- Create, edit, and delete journal entries.

### Currency Conversion
- View book prices in another supported currency without changing the original price stored in the database.
- Supported currencies: INR, GBP, USD, EUR, AUD, and CAD.
- Retrieve exchange rates from the Frankfurter API and cache them temporarily to reduce repeated requests.

### Interface and Usability
- A book-inspired visual design with a warm, vintage aesthetic.
- Responsive layouts for different screen sizes.
- Interactive book cards, reading progress controls, and rating updates.
- Client-side search, filtering, and sorting.
- Persistent library filter and sort preferences in the browser.
- Feedback messages and confirmation prompts for relevant actions.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and backend development |
| Flask | Web framework and routing |
| MySQL | Relational database for books, wishlists, and journal entries |
| HTML5 | Page structure and forms |
| CSS3 | Styling, layout, and responsive presentation |
| JavaScript | Interactive controls and client-side library operations |
| Jinja2 | Dynamic HTML rendering |
| mysql-connector-python | Connecting the Flask application to MySQL |
| python-dotenv | Loading environment configuration |
| Frankfurter API | Exchange-rate data for currency conversion |

## Database Design

The current database contains five tables:

- **`books`** â€” book metadata, cover paths, prices, reading status, reading progress, favourites, and personal ratings.
- **`wishlist`** â€” books the reader intends to acquire.
- **`reading_journal`** â€” reflections, memorable quotes, and lessons learned, with an optional reference to a book.
- **`users`** â€” username records.
- **`user_library`** â€” a library-association table containing ownership, copies, reading status, ratings, and notes.

The current application routes primarily use the `books`, `wishlist`, and `reading_journal` tables. The presence of `users` and `user_library` in the schema does not, by itself, mean that login or multi-user functionality is implemented.

## Getting Started

### Prerequisites

Install the following before running the application:

- Python
- MySQL Server
- Git (optional, for version control)

### 1. Clone the Repository

```bash
git clone https://github.com/aadithyakothandaraman/the-folio-cellar.git
cd the-folio-cellar
```

Clone the repository using the command above.

### 2. Create and Activate a Virtual Environment

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the Database

Create the MySQL database:

```sql
CREATE DATABASE personallibrarymanager;
```

Create the required tables using the project's database schema. Ensure that the tables, columns, indexes, and foreign-key relationships match the version expected by `app.py`.

### 5. Configure Environment Variables

Create a local `.env` file in the project root using `.env.example` as a reference.

Configure your MySQL connection:

```dotenv
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=personallibrarymanager
```

Replace the placeholder with your own MySQL password. Keep `.env` private and never commit real credentials to Git.

### 6. Run the Application

```bash
python app.py
```

Open the local address displayed by Flask in your terminal.

**Development note:** The current application entry point runs Flask in debug mode. Debug mode should not be enabled in a production deployment.

## Project Structure

The main components of the application are organised as follows:

```text
PersonalLibraryManager/
â”œâ”€â”€ app.py
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ .env.example
â”œâ”€â”€ .gitignore
â”œâ”€â”€ README.md
â”œâ”€â”€ templates/
â”‚   â”œâ”€â”€ home.html
â”‚   â”œâ”€â”€ index.html
â”‚   â”œâ”€â”€ add_book.html
â”‚   â”œâ”€â”€ edit_book.html
â”‚   â”œâ”€â”€ dashboard.html
â”‚   â”œâ”€â”€ wishlist.html
â”‚   â””â”€â”€ [reading journal templates]
â””â”€â”€ static/
    â”œâ”€â”€ css/
    â”‚   â””â”€â”€ style.css
    â””â”€â”€ uploads/
        â””â”€â”€ .gitkeep
```

The tree above illustrates the main structure; confirm the exact filenames and any additional assets in the repository before publishing the documentation.

## Security and Configuration

- Environment variables are used for database connection settings.
- `.env` is excluded from version control.
- `.env.example` documents the expected configuration without requiring real credentials.
- Uploaded cover images are restricted to supported image extensions and the application enforces a request-size limit.
- Uploaded file paths are checked when removing cover images.

This is currently a local development application. Authentication, authorisation, production deployment hardening, and other security requirements should be assessed before exposing it publicly.

## Current Limitations

- The current application is designed primarily around a personal library; full login and multi-user workflows are not implemented in the visible application routes.
- Goodreads ratings are entered manually rather than fetched automatically.
- Currency conversion depends on an external exchange-rate service.
- Book metadata entry is manual; automatic ISBN-based metadata retrieval should not be assumed.
- The application currently uses a single genre field per book.

## Learning Outcomes

This project provides practical experience with:

- Building a full-stack web application using Flask.
- Designing and querying a relational MySQL database.
- Implementing CRUD operations and server-side form validation.
- Integrating backend routes with dynamic Jinja2 templates.
- Using JavaScript and asynchronous requests to update interface elements.
- Managing file uploads and application configuration.
- Working with an external API and caching exchange-rate data.
- Using Git and GitHub for source control and project presentation.

## Future Improvements

Potential areas for future development include:

- User authentication and properly isolated multi-user libraries.
- Automated book metadata lookup using ISBNs.
- Automated testing and stronger error handling.
- Deployment to a production hosting environment.
- Additional reading analytics and library insights.
- Improved database migrations and setup automation.

## Project Status

**Status: Functional local web application under active development.**

The current version includes book collection management, reading progress tracking, personal ratings and favourites, a wishlist, a reading dashboard, a reading journal, and display-only currency conversion.

Further testing, documentation, and deployment preparation can be completed as the project evolves.



