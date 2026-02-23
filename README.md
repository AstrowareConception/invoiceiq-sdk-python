# invoiceiq-sdk-python

SDK Python pratique pour l'API InvoiceIQ (Factur-X): validations, transformations PDF→Factur‑X et génération complète. Inclut des modèles Pydantic, un client HTTP et des helpers de polling.

## Installation

```bash
pip install -e .[test]
```

## Démarrage rapide

```python
from invoiceiq import InvoiceIQClient
from invoiceiq.models import TransformationMetadata, Party, Address

client = InvoiceIQClient(api_key="YOUR_API_KEY")

# 1) Valider un document
res = client.validate_document("/chemin/facture.pdf", idempotency_key="GUID-123")
print(res)

# 2) Transformer un PDF vers Factur-X (BASIC)
meta = TransformationMetadata(
    invoiceNumber="INV-2024-42",
    issueDate="2024-02-22",
    seller=Party(name="Seller", countryCode="FR", address=Address(line1="10 rue A", city="Paris", postCode="75001", countryCode="FR")),
    buyer=Party(name="Buyer", countryCode="FR", address=Address(line1="5 rue B", city="Lyon", postCode="69001", countryCode="FR")),
    totalTaxExclusiveAmount=100.0,
    taxTotalAmount=20.0,
    totalTaxInclusiveAmount=120.0,
)
job = client.transform_pdf("/chemin/source.pdf", meta)
print(job)

# 2.b) Suivre le job jusqu'à complétion
from invoiceiq.models import Job
final_job = client.wait_for_job(client.get_transformation, job_id=job.get("id"))
print(final_job)

# 3) Générer une facture complète (PDF + XML)
payload = meta.model_dump()
res = client.generate_invoice(payload)
print(res)
```

## Référence rapide

- Base URL par défaut: `https://api.invoiceiq.fr`
- Authentification supportée: `X-API-KEY` et/ou `Authorization: Bearer <token>`
- Endpoints couverts:
  - `POST /v1/validations`, `GET /v1/validations/{id}/report`, `GET /v1/validations`
  - `POST /api/v1/transformations`, `GET /api/v1/transformations/{jobId}`
  - `POST /api/v1/generations`, `GET /api/v1/generations/{jobId}`

## Tests

Les tests utilisent `pytest` et `respx` (mocks httpx):

```bash
pytest -q
```

## Notes

- Le champ `metadata` pour `/api/v1/transformations` est automatiquement sérialisé en chaîne JSON.
- Utilisez `Idempotency-Key` pour vos requêtes multipart afin d’éviter les traitements dupliqués.
- `wait_for_job` gère un backoff exponentiel configurable et déclenche un `TimeoutError` en cas de dépassement de délai.
