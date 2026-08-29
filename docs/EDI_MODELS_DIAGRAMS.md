# RedArt EDI — Client Diagrams

These diagrams match the planned Colorado Medicaid 837P models.
Open this file on GitHub or any Mermaid viewer (no FigJam login needed).

## 1) Data model (entities)

```mermaid
erDiagram
    TradingPartner ||--o{ SubmissionBatch : owns
    ProviderBillingProfile ||--o{ NEMTTrip : provides
    ProviderBillingProfile ||--o{ Claim : bills
    Patient ||--o{ NEMTTrip : rides
    Patient ||--o{ Claim : subscriber
    NEMTTrip ||--o| Claim : becomes
    Claim ||--|{ ClaimServiceLine : has
    SubmissionBatch ||--|{ Claim : contains
    SubmissionBatch ||--|| EDIFile : generates
    SubmissionBatch ||--|| EDIControlNumber : tracks
    SubmissionBatch ||--o{ EDIAcknowledgement : receives

    TradingPartner {
        int id
        string name
        string tpid
        string receiver_id
        string environment
    }
    ProviderBillingProfile {
        int id
        string legal_name
        string billing_name
        string npi
        string medicaid_provider_id
    }
    Patient {
        int id
        string name
        string medicaid_member_id
    }
    NEMTTrip {
        int id
        date service_date
        decimal mileage
        decimal charge
    }
    Claim {
        int id
        string claim_number
        decimal total_charge
        string status
    }
    ClaimServiceLine {
        int id
        string procedure_code
        int units
        decimal mileage
        decimal charge
    }
    SubmissionBatch {
        int id
        string batch_number
        int claim_count
        decimal total_amount
        string status
    }
    EDIFile {
        int id
        string transaction
        string filename
        string status
    }
    EDIControlNumber {
        int id
        string ISA13
        string GS06
        string ST02
    }
    EDIAcknowledgement {
        int id
        string type
        string status
        string reason
    }
```

## 2) Claim flow (Ali example)

```mermaid
flowchart LR
    RedArt["RedArt App"] --> Trips["NEMT Trips"]
    Trips --> Claims["Claims READY"]
    Claims --> Batch["SubmissionBatch"]
    Batch --> Gen["Generate 837P"]
    Gen --> File["EDIFile + Control Numbers"]
    File --> SFTP["Colorado SFTP"]
    SFTP --> Ack999["999 Acknowledgement"]
    Ack999 -->|"ACCEPTED"| Accepted["EDI_ACCEPTED"]
    Ack999 -->|"REJECTED"| Rejected["EDI_REJECTED"]

    TP["TradingPartner TEST or PROD"] -.-> Batch
    Provider["ProviderBillingProfile"] -.-> Claims
    Patient["Patient Medicaid ID"] -.-> Claims
```

## 3) Sample story for the client

| Step | Example |
|------|---------|
| Patient | Ali Khan — Medicaid ID `987654321` |
| Provider | Al Shifa Transportation — NPI `1234567890` |
| Trips | 3 rides (Aug 25–27), $50 each |
| Batch | `RB-2026-10048` — 3 claims — $150 |
| File | `123456789-837P-...-1of1.txt` |
| Next | Upload → Colorado 999 ACCEPTED / REJECTED |

## Important separation

- **TradingPartner** = EDI submitter (RedArt / clearinghouse role)
- **ProviderBillingProfile** = transportation company billing identity
- These must stay different in the 837P file
