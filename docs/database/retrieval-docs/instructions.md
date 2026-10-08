# instructions

## Purpose
The content repository for technical manuals. It stores the individual "Pages" of an assembly guide—including titles, subtitles, and technical content—which are cloned into active production steps during manufacturing.

---

## Retrieve This Table When The User Asks About

**Assembly guides and technical steps**
Standard operating guidelines, manuals, or procedures. Identifying the "How-To" (content) for specific manufacturing tasks. Retrieving the full manual for a specific Instruction Set.

**Technical methodology and schema**
Finding the logical sequence (step numbering) for a process. Identifying expected parameters or data-entry fields (args/checkboxes) that technicians must fill out during a build.

**Safety warnings and instruction types**
Auditing the content for critical safety warnings or instructional notes. Identifying the authors (creators) of technical methodology.

---

## Co-Retrieved Sibling Tables
- `production_instruction_sets` — the parent manual/folder.
- `production_steps` — the active, unique steps generated from these templates.
- `users` — the engineer who authored the content.
