import json
import httpx
import respx
import pytest

from invoiceiq.client import InvoiceIQClient, ApiError
from invoiceiq.models import TransformationMetadata, Party, Address, Job


BASE = "https://api.invoiceiq.fr"


def make_meta() -> TransformationMetadata:
    return TransformationMetadata(
        invoiceNumber="INV-2024-42",
        issueDate="2024-02-22",
        seller=Party(name="Seller", countryCode="FR", address=Address(line1="rue A", city="Paris", postCode="75001", countryCode="FR")),
        buyer=Party(name="Buyer", countryCode="FR", address=Address(line1="rue B", city="Lyon", postCode="69001", countryCode="FR")),
        totalTaxExclusiveAmount=100.0,
        taxTotalAmount=20.0,
        totalTaxInclusiveAmount=120.0,
    )


@respx.mock
def test_validate_document_headers(tmp_path):
    file_path = tmp_path / "doc.pdf"
    file_path.write_bytes(b"%PDF-1.4 test")

    route = respx.post(f"{BASE}/v1/validations").mock(return_value=httpx.Response(201, json={"id": "val-1"}))

    client = InvoiceIQClient(api_key="KEY123")
    resp = client.validate_document(str(file_path), idempotency_key="abc-123", reference_id="R1")

    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-API-KEY"] == "KEY123"
    assert sent.headers["Idempotency-Key"] == "abc-123"
    assert resp["id"] == "val-1"


@respx.mock
def test_transform_pdf_multipart(tmp_path):
    file_path = tmp_path / "doc.pdf"
    file_path.write_bytes(b"%PDF-1.4 test")

    route = respx.post(f"{BASE}/api/v1/transformations").mock(return_value=httpx.Response(202, json={"id": "job-1", "status": "PENDING"}))

    meta = make_meta()
    client = InvoiceIQClient(api_key="KEY123")
    resp = client.transform_pdf(str(file_path), meta)

    assert route.called
    req = route.calls.last.request
    # Vérifie qu'on envoie bien un multipart/form-data (boundary présent)
    assert "multipart/form-data" in req.headers["Content-Type"]
    # Le champ metadata doit être une chaîne JSON
    body = req.read().decode("utf-8", errors="ignore")
    assert 'name="metadata"' in body
    assert '"invoiceNumber":"INV-2024-42"' in body
    assert resp["id"] == "job-1"


@respx.mock
def test_generate_invoice_json():
    payload = {
        "invoiceNumber": "F-2024-42",
        "issueDate": "2024-02-22",
        "seller": {"name": "S", "countryCode": "FR"},
        "buyer": {"name": "B", "countryCode": "FR"},
        "totalTaxExclusiveAmount": 10,
        "taxTotalAmount": 0,
        "totalTaxInclusiveAmount": 10,
    }

    route = respx.post(f"{BASE}/api/v1/generations").mock(return_value=httpx.Response(202, json={"id": "gen-1"}))

    client = InvoiceIQClient(api_key="KEY123")
    resp = client.generate_invoice(payload)

    assert route.called
    req = route.calls.last.request
    assert req.headers["Content-Type"].startswith("application/json")
    assert json.loads(req.content) == payload
    assert resp["id"] == "gen-1"


@respx.mock
def test_wait_for_job_success():
    client = InvoiceIQClient(api_key="KEY123")

    calls = {"n": 0}

    def fake_get(job_id: str) -> Job:
        calls["n"] += 1
        if calls["n"] < 3:
            return Job(id=job_id, status="PENDING")
        return Job(id=job_id, status="COMPLETED", downloadUrl="https://file")

    job = client.wait_for_job(fake_get, "job-42", interval_seconds=0.01, max_wait_seconds=0.1)
    assert job.status == "COMPLETED"


@respx.mock
def test_wait_for_job_timeout():
    client = InvoiceIQClient(api_key="KEY123")

    def fake_get(job_id: str) -> Job:
        return Job(id=job_id, status="PENDING")

    with pytest.raises(TimeoutError):
        client.wait_for_job(fake_get, "job-42", interval_seconds=0.01, max_wait_seconds=0.02)
