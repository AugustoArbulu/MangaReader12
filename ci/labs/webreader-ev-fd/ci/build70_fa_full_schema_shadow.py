#!/usr/bin/env python3
"""FA: exact 11-table SQLite v1 shadow compatibility gate, synthetic-only.

Never accepts a path directly to a user DB. Creates a synthetic fixture from
an audited source schema and delegates shadow migration to EY. This is a schema
QA tool, not a v2 migration in the iOS app.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import sqlite3
from contextlib import closing

from build70_ey_shadow_schema_migration import make_shadow, migrate_shadow, validate_v2, EYUnsafe

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / 'fixture_build70_schema_v1_exact.sql'
TABLES = ('manga', 'library', 'chapters', 'categories', 'manga_categories',
          'history', 'downloads', 'sources', 'repositories', 'source_settings', 'migration_map')
EXPECTED_COLUMNS = {
 'manga': ('internal_id','source_id','source_manga_id','title','cover','description','status','url','last_update','date_added'),
 'library': ('manga_id','date_added','last_checked'),
 'chapters': ('internal_id','manga_id','source_chapter_id','name','number','volume','url','is_read','last_page_read','bookmarked','downloaded'),
 'categories': ('internal_id','name','sort_order'),
 'manga_categories': ('manga_id','category_id'),
 'history': ('manga_id','chapter_id','last_read_at'),
 'downloads': ('internal_id','chapter_id','state','progress','local_path','updated_at'),
 'sources': ('source_id','name','version','lang','enabled','manifest_json','installed_at','updated_at'),
 'repositories': ('internal_id','name','url','enabled','last_refresh'),
 'source_settings': ('source_id','key','value'),
 'migration_map': ('internal_id','source_manga_id','destination_manga_id','migrated_at'),
}
EXPECTED_INDEXES = ('idx_manga_source', 'idx_chapters_manga', 'idx_downloads_state')


def seed_full_v1(root: Path, *, with_rows: bool=True) -> Path:
    """Create only inside preexisting disposable root, never user files."""
    root = Path(root)
    marker = root / '.webreader_ev_disposable_marker'
    if root.is_symlink() or not root.is_dir() or marker.is_symlink() or not marker.is_file() or marker.read_bytes()!=b'EV_SYNTHETIC_ONLY\n':
        raise EYUnsafe('missing synthetic lab marker')
    app = root / 'synthetic_app'
    if app.exists() or app.is_symlink():
        raise EYUnsafe('never reuse synthetic app folder')
    app.mkdir(mode=0o700)
    legacy = app / 'legacy_library_v1.sqlite'
    import os
    fd = os.open(legacy, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os,'O_NOFOLLOW',0),0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(legacy)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(SCHEMA_PATH.read_text())
            if with_rows:
                # A connected fixture across all 11 real legacy tables.
                db.execute("INSERT INTO manga VALUES(1,'s','m','Synthetic title',NULL,NULL,'unknown',NULL,NULL,7)")
                db.execute('INSERT INTO library VALUES(1,7,8)')
                db.execute("INSERT INTO chapters VALUES(1,1,'c','Synthetic chapter',1.0,NULL,NULL,1,6,1,1)")
                db.execute("INSERT INTO chapters VALUES(2,1,'c2','Synthetic other',2.0,NULL,NULL,0,0,0,0)")
                db.execute("INSERT INTO categories VALUES(1,'Synthetic category',0)")
                db.execute('INSERT INTO manga_categories VALUES(1,1)')
                db.execute('INSERT INTO history VALUES(1,1,9)')
                db.execute("INSERT INTO downloads VALUES(1,1,'completed',1.0,'/obsolete-fake-container',10)")
                db.execute("INSERT INTO sources VALUES('s','Synthetic source','0.0','en',1,'{}',1,2)")
                db.execute("INSERT INTO repositories VALUES(1,'Synthetic repository','https://example.invalid/synthetic',1,1)")
                db.execute("INSERT INTO source_settings VALUES('s','test-key','synthetic-value')")
                db.execute('INSERT INTO migration_map VALUES(1,1,1,3)')
            db.execute('PRAGMA user_version=1')
            db.commit()
            validate_full_schema(db,version=1)
    except Exception:
        # Deliberately leave failed synthetic fixture for inspection.
        raise
    return legacy


def validate_full_schema(db: sqlite3.Connection, *,version: int, allow_copy_journal: bool=False) -> None:
    if db.execute('PRAGMA user_version').fetchone()!=(version,):
        raise EYUnsafe('unexpected full schema version')
    actual_tables = set(x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    expected_tables = set(TABLES) | ({'offline_deletion_journal'} if version==2 else set())
    if allow_copy_journal and version==2: expected_tables.add('offline_copy_journal')
    if actual_tables!=expected_tables:
        raise EYUnsafe(f'table set mismatch: {actual_tables ^ expected_tables}')
    for table, columns in EXPECTED_COLUMNS.items():
        actual=tuple(row[1] for row in db.execute(f'PRAGMA table_info({table})'))
        if actual!=columns:
            raise EYUnsafe(f'legacy table column mismatch: {table}')
    actual_indexes={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")}
    if not set(EXPECTED_INDEXES).issubset(actual_indexes):
        raise EYUnsafe('legacy indexes absent')
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise EYUnsafe('FK failed')
    if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
        raise EYUnsafe('SQLite quick_check failed')
    if version==2:
        validate_v2(db)
        if allow_copy_journal:
            expected_copy={'operation_id','chapter_id','source_id','source_manga_id',
                           'source_chapter_id','snapshot_name','source_device','source_inode',
                           'state','consent','reason','created_at','updated_at'}
            columns={row[1] for row in db.execute('PRAGMA table_info(offline_copy_journal)')}
            if columns!=expected_copy:raise EYUnsafe('copy journal columns drift')
            idx={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            if 'offline_copy_state_idx' not in idx:raise EYUnsafe('copy state index absent')


def capture_legacy(db: sqlite3.Connection):
    """Snapshots *rows, indexes, schema SQL* (order by rowid not needed)."""
    data={name:sorted(map(repr,db.execute('SELECT * FROM '+name).fetchall())) for name in TABLES}
    sql={name:db.execute("SELECT sql FROM sqlite_master WHERE name=?",(name,)).fetchone()[0] for name in (*TABLES,*EXPECTED_INDEXES)}
    return (data,sql)


def validate_shadow_pair(root: Path):
    root=Path(root)
    legacy=root/'synthetic_app'/'legacy_library_v1.sqlite'
    shadow=root/'synthetic_app'/'shadow_library_v2.sqlite'
    # The v1 file is synthetically created; never migrate it in place.
    with closing(sqlite3.connect(f'{legacy.as_uri()}?mode=ro',uri=True)) as db:
        validate_full_schema(db,version=1)
        before=capture_legacy(db)
    make_shadow(root)
    migrate_shadow(root)
    with closing(sqlite3.connect(f'{legacy.as_uri()}?mode=ro',uri=True)) as db:
        validate_full_schema(db,version=1)
        if capture_legacy(db)!=before: raise EYUnsafe('legacy data drift')
    with closing(sqlite3.connect(f'{shadow.as_uri()}?mode=ro',uri=True)) as db:
        validate_full_schema(db,version=2)
        if capture_legacy(db)!=before: raise EYUnsafe('shadow data drift')
    return shadow
