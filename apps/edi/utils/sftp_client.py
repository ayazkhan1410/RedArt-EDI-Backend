"""Paramiko SFTP helpers — always close the connection."""

from __future__ import annotations

import io
import logging
import stat
from contextlib import contextmanager
from pathlib import PurePosixPath

import paramiko

from apps.edi.choices import SFTPAuthType

logger = logging.getLogger(__name__)


@contextmanager
def open_sftp(credentials):
    """Yield an SFTPClient; always closes transport/client."""
    if not credentials:
        raise ValueError("SFTP credentials are required.")

    transport = None
    sftp = None
    try:
        transport = paramiko.Transport((credentials.host, int(credentials.port or 22)))
        transport.banner_timeout = credentials.timeout_seconds or 30
        transport.auth_timeout = credentials.timeout_seconds or 30
        _connect_transport(transport, credentials)
        sftp = paramiko.SFTPClient.from_transport(transport)
        yield sftp
    finally:
        if sftp is not None:
            try:
                sftp.close()
            except Exception:
                logger.exception("Failed closing SFTP client")
        if transport is not None:
            try:
                transport.close()
            except Exception:
                logger.exception("Failed closing SFTP transport")


def _connect_transport(transport, credentials):
    auth = (credentials.auth_type or SFTPAuthType.PASSWORD).upper()
    if auth == SFTPAuthType.PASSWORD:
        if not credentials.password:
            raise ValueError("SFTP password is required for PASSWORD auth.")
        transport.connect(
            username=credentials.username,
            password=credentials.password,
        )
    elif auth == SFTPAuthType.PRIVATE_KEY:
        key = _load_private_key(
            credentials.private_key_pem,
            credentials.private_key_passphrase,
        )
        transport.connect(username=credentials.username, pkey=key)
    elif auth == SFTPAuthType.PASSWORD_AND_KEY:
        key = _load_private_key(
            credentials.private_key_pem,
            credentials.private_key_passphrase,
        )
        transport.connect(
            username=credentials.username,
            password=credentials.password,
            pkey=key,
        )
    else:
        raise ValueError(f"Unsupported SFTP auth_type: {auth}")


def upload_bytes_via_sftp(*, credentials, remote_dir, filename, data: bytes) -> str:
    """
    Upload bytes to remote_dir/filename.
    Returns the remote path used.
    """
    if not remote_dir:
        raise ValueError("SFTP remote directory is required.")
    if not filename:
        raise ValueError("Filename is required.")

    remote_path = str(PurePosixPath(remote_dir.rstrip("/")) / filename)
    with open_sftp(credentials) as sftp:
        _ensure_remote_dir(sftp, remote_dir)
        with io.BytesIO(data) as buf:
            sftp.putfo(buf, remote_path)

    logger.info(
        "SFTP upload ok host=%s path=%s bytes=%s",
        credentials.host,
        remote_path,
        len(data),
    )
    return remote_path


def list_remote_files(*, credentials, remote_dir) -> list[dict]:
    """
    List regular files in remote_dir.
    Returns [{"filename", "remote_path", "size", "mtime"}, ...].
    """
    if not remote_dir:
        raise ValueError("SFTP remote directory is required.")

    remote_dir = remote_dir.rstrip("/") or "/"
    results = []
    with open_sftp(credentials) as sftp:
        try:
            entries = sftp.listdir_attr(remote_dir)
        except FileNotFoundError as exc:
            raise ValueError(f"Remote directory not found: {remote_dir}") from exc

        for attr in entries:
            # Skip directories / specials (paramiko S_ISDIR when available).
            mode = getattr(attr, "st_mode", None)
            if mode is not None and stat.S_ISDIR(mode):
                continue
            name = attr.filename
            if not name or name in (".", ".."):
                continue
            path = str(PurePosixPath(remote_dir) / name)
            results.append(
                {
                    "filename": name,
                    "remote_path": path,
                    "size": int(getattr(attr, "st_size", 0) or 0),
                    "mtime": getattr(attr, "st_mtime", None),
                }
            )
    return results


def download_bytes_via_sftp(*, credentials, remote_path) -> bytes:
    """Download a remote file into memory."""
    if not remote_path:
        raise ValueError("remote_path is required.")

    with open_sftp(credentials) as sftp:
        with io.BytesIO() as buf:
            sftp.getfo(remote_path, buf)
            data = buf.getvalue()

    logger.info(
        "SFTP download ok host=%s path=%s bytes=%s",
        credentials.host,
        remote_path,
        len(data),
    )
    return data


def _load_private_key(pem, passphrase):
    if not pem:
        raise ValueError("private_key_pem is required.")
    # Paramiko 3.x expects a text file-like for PEM strings (BytesIO breaks).
    if isinstance(pem, str):
        stream = io.StringIO(pem)
    elif isinstance(pem, (bytes, bytearray)):
        stream = io.StringIO(pem.decode("utf-8"))
    else:
        stream = pem
    password = passphrase.encode("utf-8") if passphrase else None
    for loader in (
        paramiko.RSAKey.from_private_key,
        paramiko.ECDSAKey.from_private_key,
        paramiko.Ed25519Key.from_private_key,
    ):
        try:
            stream.seek(0)
            return loader(stream, password=password)
        except Exception:
            continue
    raise ValueError("Unable to load private key PEM.")


def _ensure_remote_dir(sftp, remote_dir):
    path = PurePosixPath(remote_dir)
    parts = []
    for part in path.parts:
        if part == "/":
            parts.append("")
            continue
        parts.append(part)
        current = "/".join(parts) if parts[0] == "" else "/".join(parts)
        if current in ("", "/"):
            continue
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)
