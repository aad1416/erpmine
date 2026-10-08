# production_instruction_set_specs

## Purpose
The automated rule engine for methodologies. It intelligently assigns technical manuals and assembly procedures to products based on their physical specifications, ensuring technicians always have the correct guidance for every item variant.

---

## Retrieve This Table When The User Asks About

**Instruction assignment logic and manual parameters**
Technical guide specs or template details. Identifying which physical attributes (e.g., "Voltage = 480V" or "Height = 72 inches") trigger a specific technical manual.

**Methodology automation**
Auditing the rules that "Inject" instructions into a build's active steps. Pattern matching between product attributes and engineering procedures.

---

## Co-Retrieved Sibling Tables
- `production_instruction_sets` — the technical manual being assigned.
- `categories` — the item category where the rule applies.
- `specifications` — the technical characteristic used as the trigger.
