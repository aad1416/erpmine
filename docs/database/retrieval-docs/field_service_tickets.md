# field_service_tickets

## Purpose
The command-and-control hub for technical support and repairs. It manages the communication between customers and the service department, anchoring technical failures (Root Cause Analysis) to unique physical machines (units) for quality and warranty management.

---

## Retrieve This Table When The User Asks About

**Service requests and support cases**
Incident reports, customer issues, or help desk tickets. Finding the status of a technical repair request. Searching for tickets using their human-readable ID (FST-9822).

**Root Cause Analysis (RCA) and failure trends**
Retrieving technical failure data (Problem, Cause, Prevention) for quality audits. Identifying product failure trends by category or model. Analyzing technical memory for failure prevention.

**Technical triage and department help**
Identifying tickets that require specialized engineering help, purchasing assistance for repair parts, or sales input for billing disputes.

**Service history for physical assets**
Finding all support cases linked to a specific serial number (unit) or model. Checking the urgency level (severity) of a customer's technical issue.

**Customer communication and portal visibility**
Identifying which technical notes and progress updates are visible to the client portal. Tracking contact information for site visits and coordination.

---

## Co-Retrieved Sibling Tables
- `units` — the specific physical machine being repaired.
- `field_service_tasks` — the individual work assignments inside the ticket.
- `sales_orders` — the original commercial contract for the machine.
- `purchase_orders` — vendor orders for specialized repair parts.
- `rma` — related return authorizations for warehouse repair.
- `users` — the technician or manager handling the ticket.
