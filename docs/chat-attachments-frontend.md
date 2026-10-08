# Chat attachments — frontend guide

The `reports` agent answers data questions with a short narrative **plus outputs**: charts, inline tables and Excel files. These outputs ride on the assistant message as `attachments`. This document is the contract the frontend needs to render them.

Backend status (branch `365-report-agent`): fully implemented and probed against the live store DB. The shape below is final.

## 1. What changed in the API

Two responses gained one field. Nothing else changed.

| Endpoint | Field |
|---|---|
| `POST /features/{feature_id}/chats/{chat_id}/messages` → `SendMessageResponse` | `attachments: Attachment[]` |
| `GET /features/{feature_id}/chats/{chat_id}` → `ChatWithMessages.messages[].attachments` | `attachments: Attachment[]` |

- Always an array. `[]` when there are none (older messages, user messages, other agents).
- Only **assistant** messages carry attachments.
- Array order = display order. The narrative refers to outputs **by `title`** ("see *Monthly sales 2024–2025*"), so render titles.
- At most **8** attachments per message.
- The `reports` agent is the Feature whose `entity_id` is `"reports"` (display name "Reports Agent"). Other agents return `attachments: []` today.

## 2. Attachment shape

Discriminated union on `kind`:

```ts
type Attachment = ChartAttachment | TableAttachment | FileAttachment;

interface Provenance {
  sql: string;                       // the query that produced this output (already store-scoped)
  transforms: { transform: string; params: Record<string, unknown> }[]; // [] if plain SQL
  row_count: number;                 // full result size before any inline cap
  generated_at: string;              // ISO datetime
}
```

Every kind has `kind`, `title` (≤120 chars) and `provenance`. Provenance is for a "how was this made?" disclosure — show it behind a toggle, not inline.

### 2.1 `chart`

```ts
interface ChartAttachment {
  kind: "chart";
  title: string;
  spec: ChartSpec;
  provenance: Provenance;
}

interface ChartSpec {
  type: "bar" | "line" | "pie";
  title: string;
  x: { label?: string | null; values: string[] };          // categories, 1–60
  series: ChartSeries[];                                   // 1–6
  y_label?: string | null;
  y2_label?: string | null;     // only present when a series uses axis "secondary"
  stacked: boolean;             // bar only
  horizontal: boolean;          // bar only
  note?: string | null;         // ≤300 chars — assumptions/caveats; render under the chart
}

interface ChartSeries {
  name: string;
  values: (number | null)[];    // same length as x.values; null = no data point
  format: "number" | "integer" | "currency" | "percent";
  unit?: string | null;         // e.g. "USD", "orders"
  axis: "primary" | "secondary";
}
```

Rendering rules (the backend validates these, so you can rely on them):

- `series[i].values.length === x.values.length` always.
- `pie`: exactly one series, no negatives, never stacked/horizontal, no secondary axis.
- `line`: never stacked/horizontal.
- `secondary` axis: at least one series stays on `primary`; draw a second y-axis on the right, labelled `y2_label`. Used when two measures differ in unit (e.g. order count vs revenue).
- `stacked` never mixes axes.
- `percent` values are **already 0–100** (e.g. `12.5` means 12.5 %). Do not multiply.
- `currency` → format with the store's currency symbol; `integer` → no decimals; `number` → sensible decimals.
- `horizontal: true` is used for long labels / top-N lists — swap axes.

Example (dual-axis):

```json
{
  "kind": "chart",
  "title": "Monthly sales, last 2 years",
  "spec": {
    "type": "bar",
    "title": "Monthly sales, last 2 years",
    "x": { "label": "Month", "values": ["2024-10", "2024-11", "2024-12"] },
    "series": [
      { "name": "Revenue", "values": [120500.5, 98000, 143200.25], "format": "currency", "unit": "USD", "axis": "primary" },
      { "name": "Orders",  "values": [312, 280, 355], "format": "integer", "unit": "orders", "axis": "secondary" }
    ],
    "y_label": "Revenue",
    "y2_label": "Orders",
    "stacked": false,
    "horizontal": false,
    "note": "Calendar months by order date; cancelled and revised orders excluded."
  },
  "provenance": { "sql": "SELECT ...", "transforms": [], "row_count": 24, "generated_at": "2026-09-16T08:12:00Z" }
}
```

### 2.2 `table`

```ts
interface TableAttachment {
  kind: "table";
  title: string;
  columns: { key: string; label: string; type: "string" | "number" | "currency" | "date" | "percent" }[];
  rows: unknown[][];            // ≤30 rows; each row is positionally aligned to columns
  row_count: number;            // full result size
  truncated: boolean;           // true when row_count > rows.length
  provenance: Provenance;
}
```

- `rows` are arrays, not objects — index by column position. Cells are JSON primitives; `date` cells are ISO strings; nulls are `null`.
- Use `label` for the header, `key` for identity/sorting.
- `percent` cells are already 0–100.
- When `truncated` is true, show "Showing 30 of {row_count}". The backend **always pairs** a truncated table with a `file` attachment holding the full data — link to it.

Example:

```json
{
  "kind": "table",
  "title": "Top 10 vendors by spend",
  "columns": [
    { "key": "rank", "label": "Rank", "type": "number" },
    { "key": "vendor", "label": "Vendor", "type": "string" },
    { "key": "spend", "label": "Spend", "type": "currency" },
    { "key": "share_pct", "label": "Share %", "type": "percent" }
  ],
  "rows": [
    [1, "Acme Supply", 84210.55, 23.4],
    [2, "Northwind", 51000, 14.2]
  ],
  "row_count": 11,
  "truncated": false,
  "provenance": { "sql": "SELECT ...", "transforms": [{ "transform": "top_n", "params": { "n": 10, "other": true } }], "row_count": 11, "generated_at": "2026-09-16T08:12:00Z" }
}
```

### 2.3 `file` (Excel export)

```ts
interface FileAttachment {
  kind: "file";
  title: string;
  file_id: string;              // use for download
  filename: string;             // e.g. "store-42-slow-moving-inventory-2026-09-16.xlsx"
  mime_type: string;            // "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  size: number;                 // bytes
  provenance: Provenance;
}
```

- Download: `GET /files/{file_id}/download` with the user's JWT. Returns the file with `Content-Disposition: attachment`. 403 if the file belongs to another user, 404 if missing.
- Render as a download card: title, filename, human-readable size, `row_count` from provenance ("4,812 rows").
- The workbook has two sheets: `Data` (the rows) and `Details` (title, SQL, transforms, row count, generated time).

## 3. Errors

There is no error attachment. If a query fails or is refused (timeout, too many rows, access), the assistant explains it in the narrative and `attachments` is simply shorter or `[]`. Nothing special to render.

## 4. Suggested rendering

```
┌ assistant message ───────────────────────────────┐
│ narrative text (markdown)                        │
│                                                  │
│ ┌ Monthly sales, last 2 years ──── [chart] ────┐ │
│ │  bar chart, dual axis                        │ │
│ │  note: Calendar months by order date; …      │ │
│ │  ▸ How this was made (SQL, transforms)       │ │
│ └──────────────────────────────────────────────┘ │
│ ┌ Top 10 vendors by spend ──────── [table] ────┐ │
│ │  Rank │ Vendor │ Spend │ Share %             │ │
│ │  Showing 30 of 4,812 — download full data ↓  │ │
│ └──────────────────────────────────────────────┘ │
│ ┌ 📄 store-42-top-vendors-2026-09-16.xlsx ─────┐ │
│ │  4,812 rows · 212 KB               [Download]│ │
│ └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

- Render attachments **after** the narrative, in array order.
- Unknown `kind` (future): ignore the item, don't break the message.
- Charts: any library works (Chart.js / Recharts / ECharts); the spec is deliberately small so mapping is direct: `x.values` → labels, each `series` → dataset, `axis` → y-axis id.

## 5. Checklist

- [ ] Type `Attachment` union + `ChartSpec` in the frontend models.
- [ ] `MessageResponse` / `SendMessageResponse` read `attachments` (default `[]`).
- [ ] Chart renderer: bar / line / pie, stacked, horizontal, secondary axis, `note`, value formats (percent already 0–100).
- [ ] Table renderer: positional rows, per-type cell formatting, truncated banner linking to the paired file.
- [ ] File card with authenticated download via `GET /files/{file_id}/download`.
- [ ] Provenance disclosure (SQL + transforms) behind a toggle.
- [ ] Chat history (`GET …/chats/{chat_id}`) renders attachments the same way as a fresh reply.
