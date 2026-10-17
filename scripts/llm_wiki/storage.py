"""Single-writer, compare-and-swap transactions with explicit recovery."""
from __future__ import annotations

import os
import re
import socket
import uuid
from contextlib import contextmanager
from pathlib import Path

from .model import WikiError, digest, json_text, load_json, now, require_safe, safe_path


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def version(text: str | None) -> str | None:
    return digest(text) if text is not None else None


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.state = safe_path(self.root, "schema/.state")
        self.lock_path = self.state / "writer.lock"

    @contextmanager
    def lock(self):
        self.state.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        try:
            with self.lock_path.open("x", encoding="utf-8") as handle:
                handle.write(json_text({"pid": os.getpid(), "host": socket.gethostname(), "token": token, "created_at": now()}))
        except FileExistsError as exc:
            raise WikiError("writer lock exists; inspect owner before recover --break-lock") from exc
        try:
            yield
        finally:
            if self.lock_path.exists() and load_json(self.lock_path.read_text(encoding="utf-8")).get("token") == token:
                self.lock_path.unlink()

    def journals(self):
        return sorted((self.state / "transactions").glob("*.json"))

    def pending(self):
        return [p for p in self.journals() if load_json(p.read_text(encoding="utf-8")).get("status") == "pending"]

    def revision(self):
        return [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in self.journals()]

    def replay(self, operation_id, intent):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", operation_id):
            raise WikiError("invalid operation id")
        path = self.state / "transactions" / (operation_id + ".json")
        if not path.exists():
            return None
        prior = load_json(path.read_text(encoding="utf-8"))
        if prior.get("intent") != intent:
            raise WikiError("operation id reused with different input")
        if prior.get("status") != "committed":
            raise WikiError("operation needs recovery before retry")
        return {**prior.get("receipt", {}), "operation_id": operation_id, "replayed": True}

    def commit(self, changes: dict[str, str | None], expected: dict[str, str | None],
               operation_id: str | None = None, fail_after: int | None = None,
               intent: str | None = None, receipt: dict | None = None) -> dict:
        operation_id = operation_id or uuid.uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", operation_id):
            raise WikiError("invalid operation id")
        for name, content in changes.items():
            target = safe_path(self.root, name)
            if target == self.root or target.is_relative_to(self.state):
                raise WikiError("transaction cannot overwrite internal state")
            if content is not None:
                require_safe(content)
        with self.lock():
            journal_path = self.state / "transactions" / (operation_id + ".json")
            if journal_path.exists():
                prior = load_json(journal_path.read_text(encoding="utf-8"))
                if prior["status"] == "committed":
                    if intent is not None:
                        return self.replay(operation_id, intent)
                    if prior.get("after") != changes:
                        raise WikiError("operation id reused with different content")
                    return {"operation_id": operation_id, "replayed": True}
                raise WikiError("operation needs recovery before retry")
            if self.pending():
                raise WikiError("unfinished transaction; run recover before writing")
            before = {}
            for name, expected_hash in expected.items():
                current = read_text(safe_path(self.root, name))
                if version(current) != expected_hash:
                    raise WikiError("concurrent edit detected; reread and retry")
            for name in changes:
                if name not in expected:
                    raise WikiError("transaction lacks expected file fingerprint")
                before[name] = read_text(safe_path(self.root, name))
                if before[name] is not None:
                    require_safe(before[name])
            journal = {"schema_version": 2, "operation_id": operation_id, "status": "pending",
                       "created_at": now(), "before": before, "after": changes, "intent": intent, "receipt": receipt or {}}
            atomic_write(journal_path, json_text(journal))
            for i, (name, content) in enumerate(changes.items(), 1):
                target = safe_path(self.root, name)
                if content is None:
                    if target.exists():
                        target.unlink()
                else:
                    atomic_write(target, content)
                if fail_after == i:  # Fault injection is available only through the Python API.
                    raise WikiError("injected interruption; transaction remains recoverable")
            journal["status"] = "committed"
            atomic_write(journal_path, json_text(journal))
        return {**(receipt or {}), "operation_id": operation_id, "replayed": False}

    def break_dead_lock(self):
        if not self.lock_path.exists():
            return
        owner = load_json(self.lock_path.read_text(encoding="utf-8"))
        if owner.get("host") != socket.gethostname() or not isinstance(owner.get("pid"), int):
            raise WikiError("cannot prove lock owner is dead on this host")
        pid = owner["pid"]
        if pid <= 0:
            raise WikiError("invalid lock owner")
        if os.name == "nt":
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            handle = kernel.OpenProcess(0x1000, False, pid)
            if handle:
                kernel.CloseHandle(ctypes.c_void_p(handle))
                raise WikiError("lock owner is still alive")
            if ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER: PID no longer exists.
                raise WikiError("cannot determine lock owner liveness")
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                raise WikiError("cannot determine lock owner liveness") from exc
            else:
                raise WikiError("lock owner is still alive")
        self.lock_path.unlink()

    def recover(self, operation_id: str | None = None, rollback: bool = False, break_lock: bool = False):
        if break_lock:
            self.break_dead_lock()
        recovered = []
        with self.lock():
            for path in self.journals():
                journal = load_json(path.read_text(encoding="utf-8"))
                if operation_id and journal["operation_id"] != operation_id:
                    continue
                if journal["status"] != "pending" and not (rollback and operation_id and journal["status"] == "committed"):
                    continue
                desired = journal["before"] if rollback else journal["after"]
                # Check every file before touching any: never clobber post-transaction edits.
                for name in desired:
                    target = safe_path(self.root, name)
                    if target == self.root or target.is_relative_to(self.state):
                        raise WikiError("recovery cannot overwrite internal state")
                    current = read_text(target)
                    if current not in (journal["before"][name], journal["after"][name]):
                        raise WikiError("recovery conflicts with later edits; manual reconciliation required")
                    if desired[name] is not None:
                        require_safe(desired[name])
                for name, content in desired.items():
                    target = safe_path(self.root, name)
                    if content is None:
                        if target.exists():
                            target.unlink()
                    else:
                        atomic_write(target, content)
                journal["status"] = "rolled_back" if rollback else "committed"
                atomic_write(path, json_text(journal))
                recovered.append(journal["operation_id"])
        return {"recovered": recovered, "rollback": rollback}
