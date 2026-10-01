"""Content backups require the latest independent guard; no implicit rollback."""
from contextlib import closing
from pathlib import Path
from hashlib import sha256
import json
import re
import os
import shutil
import sqlite3
import tempfile
import zipfile

from .store import Store


class BackupError(ValueError):
    pass


def backup_store(store, destination):
    store.sync_privacy()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise BackupError('backup_destination_exists')
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        snapshot = Path(temp) / 'state.sqlite3'
        with closing(sqlite3.connect(snapshot)) as target:
            store.db.backup(target)
        manifest = {'format': 1, 'lineage': store.lineage, 'privacy_seq': store.privacy_seq(),
                    'requires_latest_guard': True, 'state_sha256':sha256(snapshot.read_bytes()).hexdigest()}
        staged = Path(temp) / 'backup.zip'
        with zipfile.ZipFile(staged, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, 'state.sqlite3')
            archive.writestr('manifest.json', json.dumps(manifest))
        os.replace(staged, destination)
    return destination


def restore_backup(archive_path, data_dir, guard_path=None):
    """Caller must hold InstanceLock. On a fresh machine, explicitly supply latest guard."""
    destination = Path(data_dir)
    guard = Path(guard_path) if guard_path else destination / 'guard.sqlite3'
    try:
        if not guard.is_file():
            raise BackupError('latest_guard_required')
        if guard_path and (destination / 'guard.sqlite3').exists() and guard.resolve() != (destination / 'guard.sqlite3').resolve():
            raise BackupError('refuse_to_replace_existing_guard')
        with zipfile.ZipFile(archive_path) as archive:
            if len(archive.infolist()) != 2 or set(archive.namelist()) != {'state.sqlite3', 'manifest.json'}:
                raise BackupError('invalid_backup_members')
            if archive.getinfo('manifest.json').file_size > 4096 or archive.getinfo('state.sqlite3').file_size > 100 * 1024 * 1024:
                raise BackupError('backup_too_large')
            manifest = json.loads(archive.read('manifest.json'))
            if (not isinstance(manifest, dict) or type(manifest.get('format')) is not int or
                manifest['format'] != 1 or type(manifest.get('privacy_seq')) is not int or
                not 0 <= manifest['privacy_seq'] < 2**63 or manifest.get('requires_latest_guard') is not True or
                not isinstance(manifest.get('lineage'), str) or not re.fullmatch('[a-f0-9]{32}',manifest['lineage']) or
                not isinstance(manifest.get('state_sha256'), str) or not re.fullmatch('[a-f0-9]{64}',manifest['state_sha256'])):
                raise BackupError('invalid_manifest')
            content = archive.read('state.sqlite3')
            if sha256(content).hexdigest() != manifest['state_sha256']:
                raise BackupError('backup_checksum_mismatch')
            with closing(sqlite3.connect(guard.as_uri() + '?mode=ro', uri=True)) as current:
                lineage = current.execute("SELECT value FROM meta WHERE key='lineage'").fetchone()[0]
                seq = current.execute('SELECT COALESCE(MAX(seq),0) FROM erasures').fetchone()[0]
                if manifest.get('format') != 1 or lineage != manifest.get('lineage') or seq < manifest['privacy_seq']:
                    raise BackupError('guard_mismatch_or_outdated')
            destination.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=destination) as tmp:
                tmp = Path(tmp)
                (tmp / 'state.sqlite3').write_bytes(content)
                # SQLite backup API supports a consistent snapshot even when the guard is open.
                with closing(sqlite3.connect(guard)) as source, closing(sqlite3.connect(tmp / 'guard.sqlite3')) as target:
                    source.backup(target)
                with closing(sqlite3.connect(tmp / 'state.sqlite3')) as check:
                    if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise BackupError('content_integrity_failed')
                validate_content(tmp / 'state.sqlite3', manifest)
                restored = Store(tmp)
                restored.close() # replays erasures before any content becomes visible
                if not (destination / 'guard.sqlite3').exists():
                    os.replace(tmp / 'guard.sqlite3', destination / 'guard.sqlite3')
                os.replace(tmp / 'state.sqlite3', destination / 'state.sqlite3')
    except BackupError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, sqlite3.Error, zipfile.BadZipFile):
        raise BackupError('invalid_backup_or_guard; existing content was not replaced') from None


def validate_content(path, manifest):
    """Validate before Store can CREATE missing tables; empty SQLite files are not backups."""
    required = {
        'meta': {'key','value'},
        'memories': {'id','session','key','keyhash','value','kind','certainty','status','source_ref','created_ns','updated_ns'},
        'turns': {'id','session','source_ref','role','content','created_ns'},
        'summaries': {'session','content','sources'},
    }
    if path.stat().st_size < 100:
        raise BackupError('invalid_content_schema')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as check:
        tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(required) <= tables or check.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
            raise BackupError('invalid_content_schema')
        for table, columns in required.items():
            # table comes from the constant allowlist above, never archive-provided SQL.
            actual = {row[1] for row in check.execute(f'PRAGMA table_info({table})')}
            if actual != columns:
                raise BackupError('invalid_content_schema')
        metadata = dict(check.execute('SELECT key,value FROM meta'))
        if (metadata.get('schema_version') != '1' or metadata.get('lineage') != manifest['lineage'] or
            metadata.get('applied_seq') != str(manifest['privacy_seq'])):
            raise BackupError('content_manifest_mismatch')
