-- Laboratory copy of SQLiteDatabase.schemaV1 in MangaReader12, PR #90 HEAD 5ce810d2.
-- It is a SQL fixture; no paths, real library or user data.
CREATE TABLE IF NOT EXISTS manga (
    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    source_manga_id TEXT NOT NULL,
    title TEXT NOT NULL,
    cover TEXT,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    url TEXT,
    last_update REAL,
    date_added REAL NOT NULL,
    UNIQUE(source_id, source_manga_id)
);
CREATE TABLE IF NOT EXISTS library (
    manga_id INTEGER PRIMARY KEY,
    date_added REAL NOT NULL,
    last_checked REAL,
    FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS chapters (
    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    manga_id INTEGER NOT NULL,
    source_chapter_id TEXT NOT NULL,
    name TEXT NOT NULL,
    number REAL,
    volume REAL,
    url TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    last_page_read INTEGER NOT NULL DEFAULT 0,
    bookmarked INTEGER NOT NULL DEFAULT 0,
    downloaded INTEGER NOT NULL DEFAULT 0,
    UNIQUE(manga_id, source_chapter_id),
    FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS categories (
    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS manga_categories (
    manga_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY(manga_id, category_id),
    FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(internal_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS history (
    manga_id INTEGER PRIMARY KEY,
    chapter_id INTEGER,
    last_read_at REAL NOT NULL,
    FOREIGN KEY(manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE,
    FOREIGN KEY(chapter_id) REFERENCES chapters(internal_id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS downloads (
    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL UNIQUE,
    state TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    local_path TEXT,
    updated_at REAL NOT NULL,
    FOREIGN KEY(chapter_id) REFERENCES chapters(internal_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    lang TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    manifest_json TEXT NOT NULL,
    installed_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS repositories (
    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_refresh REAL
);
CREATE TABLE IF NOT EXISTS source_settings (
    source_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY(source_id, key),
    FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS migration_map (
    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_manga_id INTEGER NOT NULL,
    destination_manga_id INTEGER NOT NULL,
    migrated_at REAL NOT NULL,
    FOREIGN KEY(source_manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE,
    FOREIGN KEY(destination_manga_id) REFERENCES manga(internal_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_manga_source ON manga(source_id, source_manga_id);
CREATE INDEX IF NOT EXISTS idx_chapters_manga ON chapters(manga_id, number, volume);
CREATE INDEX IF NOT EXISTS idx_downloads_state ON downloads(state);
