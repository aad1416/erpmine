# warranties

## Purpose
The legal and technical record of coverage for physical assets. It defines the protection duration, terms, and status of guarantees for serialized machines, acting as the financial gatekeeper for billing vs. warranty service.

---

## Retrieve This Table When The User Asks About

**Warranty tracking and coverage verification**
Protection plans, service contracts, or guarantee details. Verifying if a specific serial number is currently under warranty (Active vs Expired).

**Coverage windows and deadlines**
Finding the exact start and end timestamps (Epoch) for machine protection. Identifying units whose warranty will expire in a specific timeframe (e.g., next 30 days).

**Financial gatekeeping for service**
Determining if labor and parts costs for a service ticket should be billed to the client or absorbed as a warranty expense. Checking for voided warranties due to tampering or contract breach.

**Legal terms and certificates**
Retrieving the specific contractual language (terms) governing a unit's coverage. Searching for a warranty record using its human-readable ID (WAR-10022).

---

## Co-Retrieved Sibling Tables
- `units` — the physical serial number being protected.
- `field_service_tickets` — service calls that rely on coverage status.
