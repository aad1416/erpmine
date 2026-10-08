# contacts

## Purpose
The universal registry for individuals. It represents the human beings—such as sales reps, technicians, and billing clerks—who work for client or vendor organizations, managing their communication details across multiple business domains.

---

## Retrieve This Table When The User Asks About

**People and individuals**
Representatives, stakeholders, or phone numbers. Retrieving contact information (email/phone) for the staff members at a specific Client or Vendor organization.

**CRM communication nexus**
Finding a person by their name or email address across the entire system. Identifying the human being who serves as the primary contact for a business partner.

**Polymorphic relationship mapping**
Identifying which organization (owner_id) and type (client/vendor) a specific individual belongs to.

---

## Co-Retrieved Sibling Tables
- `clients` — the customer organization the person works for.
- `vendors` — the supplier organization the person works for.
- `stores` — the branch managing the contact relationship.
- `users` — the staff member who registered the individual.
