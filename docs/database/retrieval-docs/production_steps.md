# production_steps

## Purpose
The technical instruction layer of the assembly line. It defines the sequential actions, measurements, and safety checks a technician must perform to complete a work order, acting as a digital manual for the shop floor.

---

## Retrieve This Table When The User Asks About

**Assembly instructions and technical actions**
Workstation tasks, assembly steps, or manual entries. Finding the "The Manual" (content) for how to build a part of a machine.

**Data capture and measurements**
Retrieving technical measurements (e.g., voltage, resistance, pressure) captured during a specific build. Identifying if a safety check or calibration was performed (done status).

**Shop floor guidance and compliance**
Navigating the chronological sequence (WBS pathing) of a build. Enforcing a "Stop-and-Check" workflow where every step must be signed off.

---

## Co-Retrieved Sibling Tables
- `production_tasks` — the parent work order.
- `units` — the physical machine being built.
- `instructions` — the master template used to generate these steps.
- `users` — the manager or system that generated the record.
