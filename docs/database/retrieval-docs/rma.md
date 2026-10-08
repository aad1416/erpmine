# rma

## Purpose
The cornerstone of reverse logistics and warranty management. It is a formal authorization (Return Merchandise Authorization) that approves a customer's request to return physical assets, typically for repair or credit within a service context.

---

## Retrieve This Table When The User Asks About

**Customer returns and authorizations**
Return merchandise authorizations (RMAs), product returns, or credit notes. Identifying open vs completed return requests. Who authorized or approved a return and the authorization date.

**Service and warranty claims**
Returns triggered by technical issues or faulty items. Identifying returns covered under manufacturer or service warranty. RMAs linked to specific field service tickets.

**Reverse logistics and exchange**
Tracking defective units moving back to the warehouse. Identifying advance exchanges where replacement parts are shipped out immediately (are_parts_being_shipped flag). Recording when a returned asset physically arrives at the warehouse (receive_date).

**Return reasons and deadlines**
Detailed explanations or failure analysis for a return request. When a return authorization expires (expire_date window for returning goods). Special instructions for the client regarding packaging or shipping.

**Asset ownership and financial context**
Determining if an asset belongs to the customer (Return for Repair) or the store (Return for Credit). RMAs linked back to an original commercial sales order.

---

## Co-Retrieved Sibling Tables
- `rma_line_items` — the specific SKUs and units inside the authorization.
- `field_service_tickets` — the technical issue that triggered the return.
- `sales_orders` — the original purchase contract.
- `users` — the staff member authorizing or creating the return.
- `stores` — the branch managing the return.
