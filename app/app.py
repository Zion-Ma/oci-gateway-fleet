import os
import socket
import urllib.request
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

VERSION = os.environ.get("APP_VERSION", "v1")
BUCKET = os.environ.get("NOTES_BUCKET", "")
EGRESS_URL = os.environ.get("EGRESS_URL", "https://example.com")

app = FastAPI()


class Note(BaseModel):
    text: str


def fetch_public_site() -> None:
    """Reach a public website. Raises on failure (tests swap this out)."""
    urllib.request.urlopen(EGRESS_URL, timeout=5).read(1)


def save_note(text: str) -> str:
    """Write a note to Object Storage via instance principal. Tests swap this out."""
    import oci  # imported lazily so local runs and tests don't need cloud access

    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    client = oci.object_storage.ObjectStorageClient({}, signer=signer)
    namespace = client.get_namespace().data
    name = f"note-{uuid.uuid4().hex[:8]}.txt"
    client.put_object(namespace, BUCKET, name, text.encode())
    return name


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/whoami")
def whoami():
    return {"hostname": socket.gethostname()}


@app.get("/egress")
def egress():
    try:
        fetch_public_site()
        return {"egress": "ok"}
    except Exception as e:
        return {"egress": "fail", "error": str(e)}


@app.post("/notes")
def notes(note: Note):
    try:
        return {"saved": save_note(note.text)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
