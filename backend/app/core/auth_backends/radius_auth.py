"""RADIUS PAP authentication backend using pyrad."""

import logging

logger = logging.getLogger(__name__)


def authenticate_radius(
    host: str,
    port: int,
    secret: str,
    timeout: int,
    username: str,
    password: str,
) -> bool:
    """
    Send a RADIUS Access-Request (PAP) and return True on Access-Accept.
    Returns False on Access-Reject, timeout, or any error.
    """
    try:
        from pyrad.client import Client
        from pyrad.dictionary import Dictionary

        # Minimal RADIUS dictionary (RFC 2865 core attributes)
        _DICT_TEXT = """\
ATTRIBUTE User-Name       1  string
ATTRIBUTE User-Password   2  string
ATTRIBUTE NAS-Identifier  32 string
"""
        import io

        dict_obj = Dictionary(io.StringIO(_DICT_TEXT))
        client = Client(server=host, authport=port, secret=secret.encode(), dict=dict_obj)
        client.timeout = timeout

        req = client.CreateAuthPacket(code=1)  # Access-Request
        req["User-Name"] = username
        req["User-Password"] = req.PwCrypt(password)
        req["NAS-Identifier"] = "WorkFlow"

        reply = client.SendPacket(req)
        # Access-Accept = code 2
        return reply.code == 2

    except Exception as exc:
        logger.error("RADIUS authentication error for '%s': %s", username, exc)
        return False
