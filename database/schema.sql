
-- ============================================================
-- The Folio Cellar
-- Database schema for MySQL
-- ============================================================
-- This file defines the database structure only.
-- It does not contain personal book data.
--
-- For a fresh installation, run this script in MySQL.
-- Back up existing data before making schema changes.
-- ============================================================

CREATE DATABASE IF NOT EXISTS personallibrarymanager
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE personallibrarymanager;


-- ============================================================
-- 1. BOOKS
-- Stores book details and reading information.
-- ============================================================

CREATE TABLE IF NOT EXISTS books (
    book_id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    authors VARCHAR(255) NOT NULL,
    isbn_10 VARCHAR(10) DEFAULT NULL,
    isbn_13 VARCHAR(13) DEFAULT NULL,
    publisher VARCHAR(255) DEFAULT NULL,
    publication_year YEAR DEFAULT NULL,
    edition VARCHAR(100) DEFAULT NULL,
    language VARCHAR(100) DEFAULT 'English',
    genre VARCHAR(100) DEFAULT NULL,
    description TEXT,
    mrp DECIMAL(10,2) DEFAULT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    goodreads_rating DECIMAL(3,2) DEFAULT NULL,
    cover_image_path VARCHAR(500) DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    isbn VARCHAR(40) DEFAULT NULL,
    reading_status VARCHAR(20) NOT NULL DEFAULT 'Want to Read',
    current_page INT UNSIGNED NOT NULL DEFAULT 0,
    total_pages INT UNSIGNED DEFAULT NULL,
    started_at DATE DEFAULT NULL,
    completed_at DATE DEFAULT NULL,
    is_favorite TINYINT(1) NOT NULL DEFAULT 0,
    personal_rating TINYINT UNSIGNED DEFAULT NULL,

    PRIMARY KEY (book_id),
    UNIQUE KEY isbn_10 (isbn_10),
    UNIQUE KEY isbn_13 (isbn_13)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;


-- ============================================================
-- 2. USERS
-- Stores usernames.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    user_id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id),
    UNIQUE KEY username (username)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;


-- ============================================================
-- 3. USER_LIBRARY
-- Associates users with books and stores library-specific data.
-- ============================================================

CREATE TABLE IF NOT EXISTS user_library (
    user_library_id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    book_id INT NOT NULL,
    owns_book TINYINT(1) NOT NULL DEFAULT 1,
    copies_owned INT NOT NULL DEFAULT 1,
    is_wishlisted TINYINT(1) NOT NULL DEFAULT 0,
    reading_status ENUM('Unread', 'Currently Reading', 'Read')
        NOT NULL DEFAULT 'Unread',
    personal_rating DECIMAL(2,1) DEFAULT NULL,
    notes TEXT,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_library_id),
    UNIQUE KEY user_id (user_id, book_id),
    KEY book_id (book_id),

    CONSTRAINT user_library_ibfk_1
        FOREIGN KEY (user_id)
        REFERENCES users (user_id),

    CONSTRAINT user_library_ibfk_2
        FOREIGN KEY (book_id)
        REFERENCES books (book_id),

    CONSTRAINT user_library_chk_1
        CHECK (copies_owned >= 0),

    CONSTRAINT user_library_chk_2
        CHECK (
            personal_rating IS NULL
            OR (personal_rating >= 0 AND personal_rating <= 5)
        )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;


-- ============================================================
-- 4. WISHLIST
-- Stores books the reader wants to acquire.
-- ============================================================

CREATE TABLE IF NOT EXISTS wishlist (
    wishlist_id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    authors VARCHAR(255) NOT NULL,
    isbn VARCHAR(40) DEFAULT NULL,
    notes TEXT,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (wishlist_id),
    KEY idx_wishlist_title (title)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;


-- ============================================================
-- 5. READING_JOURNAL
-- Stores reflections, memorable quotes, and lessons learned.
-- ============================================================

CREATE TABLE IF NOT EXISTS reading_journal (
    entry_id INT NOT NULL AUTO_INCREMENT,
    book_id INT DEFAULT NULL,
    entry_type ENUM(
        'Reflection',
        'Memorable Quote',
        'Lesson Learned'
    ) NOT NULL DEFAULT 'Reflection',
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    quote_author VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (entry_id),
    KEY idx_journal_book (book_id),
    KEY idx_journal_created (created_at),

    CONSTRAINT fk_journal_book
        FOREIGN KEY (book_id)
        REFERENCES books (book_id)
        ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
