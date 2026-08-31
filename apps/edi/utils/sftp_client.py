"""Paramiko SFTP upload helper — always closes the connection."""

from __future__ import annotations

import io
import logging
from pathlib import PurePosixPath

import paramiko

from apps.edi.choices import SFTPAuthType

logger = logging.getLogger(__name__)


def upload_bytes_via_sftp(*, credentials, remote_dir, filename, data: bytes) -> str:
    """
    Upload bytes to remote_dir/filename.
    Returns the remote path used.
    """
    if not credentials:
        raise ValueError("SFTP credentials are required.")
    if not remote_dir:
        raise ValueError("SFTP remote directory is required.")
    if not filename:
        raise ValueError("Filename is required.")

    remote_path = str(PurePosixPath(remote_dir.rstrip("/")) / filename)
    transport = None
    sftp = None
    try:
        transport = paramiko.Transport((credentials.host, int(credentials.port or 22)))
        transport.banner_timeout = credentials.timeout_seconds or 30
        transport.auth_timeout = credentials.timeout_seconds or 30

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

        sftp = paramiko.SFTPClient.from_transport(transport)
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


def _load_private_key(pem, passphrase):
    if not pem:
        raise ValueError("private_key_pem is required.")
    raw = pem.encode("utf-8") if isinstance(pem, str) else pem
    password = passphrase.encode("utf-8") if passphrase else None
    for loader in (
        paramiko.RSAKey.from_private_key,
        paramiko.ECDSAKey.from_private_key,
        paramiko.Ed25519Key.from_private_key,
    ):
        try:
            return loader(io.BytesIO(raw), password=password)
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
