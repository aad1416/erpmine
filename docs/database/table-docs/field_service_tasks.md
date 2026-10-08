# `field_service_tasks`

## Searchable Aliases
repair jobs, maintenance tasks, on-site work, technician assignments, work orders

## Description
The `field_service_tasks` table is the execution layer of the Field Service domain. While a Ticket represents the "Problem," a Task represents a specific "Action" or "Assignment" required to reach a resolution. 

This table enables managers to dismantle complex repairs into individual instructions (e.g., "Replace PCB", "Recalibrate Sensors"), assign them to specific technicians, and track the exact timing and status of those work items.

## ⚙️ The Task Execution Workflow
1.  **Instruction Generation**: Inside a Field Service Ticket, one or more tasks are created to define the scope of work.
2.  **Assignment**: A specific user is assigned via `assigned_to_id`.
3.  **Scheduling**: The `due_date` is established for SLA tracking.
4.  **Logistics Anchor**: The task maintains denormalized links to the `unit_serial_number` and `sales_order_number` to ensure the technician has the correct context without needing complex multi-table joins in the field.
5.  **Completion**: Once the technician finishes the work, the `end` timestamp is recorded, and the `status` is updated.

## ⚠️ SQL-Critical Behaviors
- **Relationship Hub**: This table is highly connected, linking to the **Ticket** (Technical context), the **Sales Order** (Commercial context), and the **Unit** (Physical context) simultaneously.
- **Time Capture**: The `start` and `end` columns (Epoch) are the primary sources for calculating the "Labor Duration" of a repair. 
- **Denormalization for Performance**: By storing the `unit_serial_number` and `ticket_number` directly as text, the system ensures that list-views in mobile field-apps remain high-performance and accessible offline.

## Columns (23 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the workload. |
| start | int8 | yes | — | The actual timestamp when work began (Epoch). |
| end | int8 | yes | — | The actual timestamp when work was completed (Epoch). |
| type | enum | no | — | The nature of the task (e.g., `REPAIR`, `INSPECTION`, `ADMIN`). |
| requested_by_id | uuid | yes | — | Link to the client contact who requested the specific action. |
| requested_by_name | text | yes | — | Denormalized name of the requesting contact. |
| assigned_to_id | uuid | yes | — | **The Technician**: Link to `users.id` responsible for execution. |
| assigned_to_name | text | yes | — | Name of the technician for display on field vouchers. |
| sales_order_id | uuid | yes | — | Link to the commercial contract in `sales_orders.id`. |
| sales_order_number | text | yes | — | Denormalized SO human-readable ID. |
| unit_id | uuid | yes | — | Link to the physical asset being serviced. |
| unit_serial_number | text | yes | — | **The Target Unit**: Denormalized serial number of the machine. |
| ticket_id | uuid | yes | — | **Parent Ticket**: Link to the master service request in `field_service_tickets.id`. |
| ticket_number | text | yes | — | Denormalized **FST** (Field Service Ticket) human-readable ID. |
| description | text | yes | — | Detailed work instructions for the technician. |
| number | text | yes | — | **Task ID**: Human-readable serial for this specific assignment. |
| title | text | yes | — | Short name for the task (e.g., "Annual Maintenance"). |
| status | enum | no | — | **Task State**: (e.g., `PENDING`, `IN_PROGRESS`, `COMPLETED`). |
| creator_id | uuid | no | — | The manager who created/assigned the task. |
| due_date | int8 | yes | — | The deadline for task completion (Epoch). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| requested_by_id | contacts | id | set null |
| assigned_to_id | users | id | set null |
| sales_order_id | sales_orders | id | set null |
| unit_id | units | id | set null |
| ticket_id | field_service_tickets | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Audit Technician Performance: Average duration of COMPLETED repair tasks
SELECT assigned_to_name, AVG("end" - "start") as avg_duration_seconds
FROM field_service_tasks 
WHERE status = 'COMPLETED' AND type = 'REPAIR'
GROUP BY assigned_to_name;

-- Find all Overdue tasks (Due Date passed but not Completed)
SELECT number, title, assigned_to_name 
FROM field_service_tasks 
WHERE status != 'COMPLETED' AND due_date < EXTRACT(EPOCH FROM NOW());
```

## Indexes
- *Includes standard relational indexes on `ticket_id`, `assigned_to_id`, and `unit_id` for fleet-level task management.*
