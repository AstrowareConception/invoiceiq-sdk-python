from __future__ import annotations
from typing import Any, Dict, Iterable, Optional
import json
import time

import httpx
from pydantic import BaseModel

from .models import (
    TransformationMetadata,
    GenerationPayload,
    Job,
    ValidationReport,
)


DEFAULT_BASE_URL = "https://api.invoiceiq.fr"


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, response: Optional[httpx.Response] = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.response = response


class InvoiceIQClient:
    """Client minimaliste et pratique pour l'API InvoiceIQ."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not api_key and not bearer_token:
            # On autorise explicitement des appels publics (ex: /v1/free-validations), sinon headers seront vides
            pass
        self._api_key = api_key
        self._bearer = bearer_token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    # ---- Utils ----
    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["X-API-KEY"] = self._api_key
        if self._bearer:
            headers["Authorization"] = f"Bearer {self._bearer}"
        if extra:
            headers.update(extra)
        return headers

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            # essaie d'extraire un message
            try:
                data = resp.json()
                msg = data.get("message") or data.get("error") or resp.text
            except Exception:
                msg = resp.text
            raise ApiError(resp.status_code, msg, resp)
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return resp.json()
        return resp.content

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ---- Validations ----
    def validate_document(
        self,
        file_path: str,
        *,
        idempotency_key: Optional[str] = None,
        callback_url: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}/v1/validations"
        headers = self._headers({"Idempotency-Key": idempotency_key} if idempotency_key else None)
        files: Dict[str, Any] = {"file": open(file_path, "rb")}
        data: Dict[str, Any] = {}
        if callback_url:
            data["callbackUrl"] = callback_url
        if reference_id:
            data["referenceId"] = reference_id
        with files["file"] as fp:
            resp = self._client.post(url, headers=headers, files={"file": fp}, data=data)
        return self._handle(resp)

    def get_validation_report(self, validation_id: str) -> ValidationReport:
        url = f"{self._base_url}/v1/validations/{validation_id}/report"
        resp = self._client.get(url, headers=self._headers())
        data = self._handle(resp)
        if isinstance(data, (bytes, bytearray)):
            # si renvoie binaire par erreur
            raise ApiError(500, "Réponse binaire inattendue pour un rapport JSON")
        return ValidationReport.model_validate(data)  # type: ignore[arg-type]

    def list_validations(self, **query: Any) -> Any:
        url = f"{self._base_url}/v1/validations"
        resp = self._client.get(url, headers=self._headers(), params=query)
        return self._handle(resp)

    # ---- Transformations ----
    def transform_pdf(
        self,
        file_path: str,
        metadata: TransformationMetadata | Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        url = f"{self._base_url}/api/v1/transformations"
        headers = self._headers({"Idempotency-Key": idempotency_key} if idempotency_key else None)
        # le champ metadata doit être une chaîne JSON
        if isinstance(metadata, BaseModel):
            metadata_str = metadata.model_dump_json()
        else:
            metadata_str = json.dumps(metadata)
        with open(file_path, "rb") as fp:
            files = {"file": fp}
            data = {"metadata": metadata_str}
            resp = self._client.post(url, headers=headers, files=files, data=data)
        return self._handle(resp)

    def get_transformation(self, job_id: str) -> Job:
        url = f"{self._base_url}/api/v1/transformations/{job_id}"
        resp = self._client.get(url, headers=self._headers())
        data = self._handle(resp)
        if isinstance(data, (bytes, bytearray)):
            raise ApiError(500, "Réponse binaire inattendue pour un job JSON")
        return Job.model_validate(data)  # type: ignore[arg-type]

    # ---- Generations ----
    def generate_invoice(self, payload: GenerationPayload | Dict[str, Any]) -> Any:
        url = f"{self._base_url}/api/v1/generations"
        headers = self._headers({"Content-Type": "application/json"})
        if isinstance(payload, BaseModel):
            json_data = payload.model_dump()
        else:
            json_data = payload
        resp = self._client.post(url, headers=headers, json=json_data)
        return self._handle(resp)

    def get_generation(self, job_id: str) -> Job:
        url = f"{self._base_url}/api/v1/generations/{job_id}"
        resp = self._client.get(url, headers=self._headers())
        data = self._handle(resp)
        if isinstance(data, (bytes, bytearray)):
            raise ApiError(500, "Réponse binaire inattendue pour un job JSON")
        return Job.model_validate(data)  # type: ignore[arg-type]

    # ---- Helper: attendre la complétion d'un job ----
    def wait_for_job(
        self,
        fetch_fn: callable[[str], Job],
        job_id: str,
        *,
        interval_seconds: float = 1.0,
        max_wait_seconds: float = 60.0,
        backoff_factor: float = 1.5,
        completed_status: str = "COMPLETED",
        failed_statuses: Iterable[str] = ("FAILED", "CANCELED"),
    ) -> Job:
        """Attend la fin d'un job en le requêtant périodiquement.

        Exemple d'utilisation:
            job = client.wait_for_job(client.get_transformation, job_id)
        """
        deadline = time.time() + max_wait_seconds
        delay = interval_seconds
        while True:
            job = fetch_fn(job_id)
            if job.status.upper() == completed_status:
                return job
            if job.status.upper() in {s.upper() for s in failed_statuses}:
                raise ApiError(500, f"Job {job_id} en échec: {job.status}")
            if time.time() + delay > deadline:
                raise TimeoutError(f"Timeout après {max_wait_seconds}s en attendant le job {job_id}")
            time.sleep(delay)
            delay *= backoff_factor


__all__ = [
    "InvoiceIQClient",
    "ApiError",
]
