"""Portable evidence binding; structural validation, never an authorization oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from datetime import datetime, timezone


def need(value, message):
    if not value:
        raise ValueError(message)


def fields(value, keys):
    need(isinstance(value, dict) and set(value) == set(keys.split()), "invalid fields: " + keys)


def word(value):
    need(isinstance(value, str) and bool(value.strip()) and len(value) <= 4096, "expected nonempty text")
    return value


def strings(value):
    need(isinstance(value, list) and value, "expected nonempty list")
    for item in value:
        word(item)
    need(len(value) == len(set(value)), "duplicate values")
    return set(value)


def no_links(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            stat = item.lstat()
            need(not item.is_symlink() and not (getattr(stat, "st_file_attributes", 0) & 1024), "linked paths forbidden")
    return path


def load(path):
    path = no_links(Path(path).absolute())
    need(path.stat().st_size <= 2_000_000, "record too large")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def artifact(value, root):
    fields(value, "path sha256")
    name, digest = word(value["path"]), word(value["sha256"])
    rel = PurePosixPath(name)
    need(not rel.is_absolute() and ".." not in rel.parts and ":" not in name and "\\" not in name, "artifact escapes root")
    path = no_links(root / name)
    need(path.is_file(), "artifact missing")
    need(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "full SHA256 required")
    hashed = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hashed.update(chunk)
    need(hashed.hexdigest() == digest, "artifact changed")


def subject(value):
    fields(value, "product target revision configuration")
    for item in value.values():
        word(item)


def timestamp(value):
    result = datetime.fromisoformat(word(value).replace("Z", "+00:00"))
    need(result.tzinfo is not None, "timestamp requires timezone")
    return result


def receipt(value, root, current, success=True, fresh=True):
    fields(value, "subject actor at expires command exit_code assertions output oracle artifacts")
    subject(value["subject"])
    if current is not None:
        need(value["subject"] == current, "receipt subject mismatch")
    word(value["actor"])
    need(isinstance(value["command"], list) and value["command"], "command required")
    for argument in value["command"]:
        word(argument)
    start, end = timestamp(value["at"]), timestamp(value["expires"])
    now = datetime.now(timezone.utc)
    need(start <= now and end > start and (not fresh or now < end), "receipt stale or future")
    code = value["exit_code"]
    need(type(code) is int and ((code == 0) if success else (code != 0)), "unexpected check exit code")
    count = value["assertions"]
    need(type(count) is int and count > 0, "no meaningful assertions recorded")
    artifact(value["output"], root)
    artifact(value["oracle"], root)
    need(isinstance(value["artifacts"], list) and value["artifacts"], "tested artifacts required")
    for item in value["artifacts"]:
        artifact(item, root)


def artifacts(value, root):
    need(isinstance(value, list) and value, "changed artifacts required")
    for item in value:
        artifact(item, root)


def is_current(value, current):
    return value["subject"] == current and datetime.now(timezone.utc) < timestamp(value["expires"])


def covers_changes(value, changes):
    actual = {(item["path"], item["sha256"]) for item in value["artifacts"]}
    need(all((item["path"], item["sha256"]) in actual for item in changes), "verification omits changed artifacts")


def run(validate):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record")
    parser.add_argument("--subject", required=True, help="current subject JSON independently supplied by conductor")
    parser.add_argument("--append", help="append one event under an exclusive local writer lock")
    args = parser.parse_args()
    lock = None
    try:
        path = no_links(Path(args.record).absolute())
        if args.append:
            lock = Path(str(path) + ".lock")
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        current = load(args.subject)
        subject(current)
        record = load(path)
        if args.append:
            need(isinstance(record.get("events"), list), "events must be a list")
            record["events"].append(load(args.append))
        result = validate(record, path.parent, current)
        if args.append:
            payload = json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8")
            need(len(payload) <= 2_000_000, "record too large")
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        print(json.dumps(dict(result, authority="none", evidence_scope="local structural binding")))
        return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as error:
        print(json.dumps({"status": "INVALID_OR_BLOCKED", "error": str(error), "authority": "none"}))
        return 2
    finally:
        # Only remove the lock when this invocation acquired it.
        if lock is not None and 'fd' in locals():
            lock.unlink(missing_ok=True)
