# RedArt EDI — Progress Report

**Branch:** `Ayaz/local-main`  
**Date:** 2026-08-31  
**Overall:** ~70–75% backend (demo-ready; not production Medicaid)

---

## Done

### Domain & workflow
- TradingPartner, ProviderBillingProfile, Patient, NemtTrip, LongDistanceRule
- Claim, ClaimServiceLine, ClaimDocument, SubmissionBatch, BatchClaim
- Long-distance flags (25+ / 52–125), document gate, block incomplete claims
- Claim flow: Trip → Claim → READY_FOR_837P / BLOCK → Batch

### EDI pipeline
- EDIControlNumber, EDIFile, transfer logs
- 837P **generate** API (Colorado overlays; minimal X12 — demo OK)
- Upload: SFTP + MinIO, Celery retries
- Claim statuses: `EDI_SENT` (after upload), `EDI_ACCEPTED` (after 999 apply)
- EDIAcknowledgement (999 store + apply — not full parser)
- AttachmentSubmission (channel tracking; not live HCPF send)
- Demo seed, Docker/MinIO, Swagger APIs

---

## Remaining

| Priority | Item |
|----------|------|
| High | Full ASC X12 TR3 `005010X222A1` mapping (production-valid 837P) |
| High | Real HCPF TP enrollment + MFT connectivity (ops; config after approval) |
| Medium | Inbound TA1 / `.rjct` / `.description` parsing |
| Medium | Rural county list (125-mile rule) |
| Medium | Real provider tax_id / TPID (replace demo placeholders) |
| Lower | Service auth (RedArt → EDI API) |
| Lower | Ops FE / adjudication → PAID automation |
| Lower | Live HCPF attachment channel integration |

---

## Not for coding yet
MFT install guide = enrollment/ops only. No schema rewrite needed.

## Next recommended
1. Client: HCPF enrollment + MFT test  
2. Eng: deepen 837P vs TR3, or inbound error parsers  
