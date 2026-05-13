# Post-Mortem: Incident INC-20240405-DB-EXHAUSTION

**Incident ID:** INC-20240405-DB-EXHAUSTION
**Date:** 2024-04-05
**Time of First Symptom:** 09:44:22 UTC
**Time of Impact:** 09:45:40 UTC
**Time of Resolution:** 09:59:00 UTC
**Duration of Impact:** 13 minutes, 20 seconds
**Services Affected:** Order Service, API Gateway, Primary Database, Order Submission Functionality
**Lead Engineer:** SRE Team

## 1. Summary

On Friday, April 5th, 2024, at 09:45 UTC, the platform experienced a critical outage resulting in the complete halt of order submission functionality for 13 minutes and 20 seconds. The incident was triggered by a long-running database query (`q_9031`) originating from the daily `open_orders_settlement` batch job. This query, performing a full table scan on the `open_orders` table due to a missing index on `account_id` and `order_date`, exhausted the primary database's connection pool. Consequently, the Order Service became unresponsive, leading to API Gateway timeouts and circuit breaker activation, ultimately blocking all new order submissions. The issue was resolved by manually killing the errant database query.

## 2. Impact

*   **Critical:** Complete halt of order submission functionality. Users were unable to place new orders.
*   **Customer Impact:** All users attempting to submit orders during the 13 minute and 20 second window (09:45:40 UTC to 09:59:00 UTC) received errors.
*   **System Impact:**
    *   Primary database connection pool exhausted.
    *   Order Service became unresponsive due to database contention.
    *   API Gateway experienced upstream timeouts and activated its circuit breaker for the Order Service.
    *   Degraded performance across dependent services interacting with the primary database.

## 3. Timeline

*   **2024-04-05 09:11:00 UTC:** API Gateway reports normal p99 request latency of 95ms (baseline).
*   **2024-04-05 09:30:00 UTC (Approx.):** Daily `open_orders_settlement` batch job is scheduled and begins execution.
*   **2024-04-05 09:44:22 UTC:** Order Service detects a slow database query (q_9031) with a duration of 1.8 seconds. (First Symptom)
*   **2024-04-05 09:44:55 UTC:** Primary database connection pool becomes exhausted (100/100 connections in use) with 39 requests waiting.
*   **2024-04-05 09:45:10 UTC:** API Gateway reports upstream timeouts when calling the Order Service.
*   **2024-04-05 09:45:28 UTC:** API Gateway's circuit breaker opens for the Order Service due to persistent timeouts.
*   **2024-04-05 09:45:40 UTC:** Platform-wide critical alert: Order submission functionality is halted. (Impact Moment)
*   **2024-04-05 09:57:14 UTC:** Long-running database query `q_9031` on `open_orders` table is manually killed after running for 748 seconds. (Resolution Trigger)
*   **2024-04-05 09:57:15 UTC:** Primary database connection pool begins recovering.
*   **2024-04-05 09:59:00 UTC:** Order submission functionality is successfully resumed. (Resolution)
*   **2024-04-05 10:15:00 UTC:** Post-incident analysis reveals query `q_9031` originated from the daily `open_orders_settlement` batch job, scheduled at 09:30 UTC.
*   **2024-04-05 10:15:01 UTC:** Further investigation confirms the `open_orders` table lacks a necessary index on `account_id` and `order_date`, causing the query to perform a full table scan.

## 4. Root Cause

The root cause of Incident INC-20240405-DB-EXHAUSTION was a **missing database index on the `open_orders` table**, exacerbating the performance of the `open_orders_settlement` batch job.

Specifically:
1.  The daily `open_orders_settlement` batch job, scheduled to run during operational hours (09:30 UTC), executed a query (`q_9031`) against the `open_orders` table.
2.  This query required filtering and sorting on `account_id` and `order_date`. However, the `open_orders` table lacked a composite index on these columns.
3.  Consequently, `q_9031` was forced to perform a full table scan, consuming excessive database resources and running for an exceptionally long duration (748 seconds).
4.  The sustained high resource utilization by `q_9031` led to the primary database's connection pool becoming exhausted, preventing the Order Service and other applications from acquiring new database connections.
5.  This database contention resulted in upstream timeouts reported by the API Gateway when calling the Order Service, ultimately leading to the API Gateway opening its circuit breaker and halting all new order submissions.

This incident shares the same failure mode as `INC-2024-007` and `INC-20240315-001`, both triggered by a batch job performing a full table scan due to a missing index, exhausting database resources and causing critical service degradation.

## 5. Resolution

The incident was resolved by manually identifying and terminating the long-running database query `q_9031` at 09:57:14 UTC. This action immediately freed up database connections, allowing the primary database connection pool to recover and the Order Service to resume normal operations, restoring order submission functionality.

## 6. Detection

The incident was detected through:
1.  **Application Monitoring (Order Service):** The Order Service detected an initial slow database query (`q_9031`) at 09:44:22 UTC.
2.  **Database Monitoring:** Exhaustion of the primary database connection pool (100/100 connections in use) was observed at 09:44:55 UTC.
3.  **API Gateway Monitoring:** Upstream timeouts for the Order Service were reported starting at 09:45:10 UTC, followed by the circuit breaker opening at 09:45:28 UTC.
4.  **Platform Alerting:** A critical alert for "Order submission functionality is halted" was triggered at 09:45:40 UTC.

While initial symptoms were detected relatively early, the progression to critical impact was rapid due to the cascade effect of database resource exhaustion.

## 7. Future Actions

To prevent recurrence and improve system resilience, the following actions will be undertaken:

1.  **Add Missing Database Index:**
    *   **Action:** Create a composite index on `(account_id, order_date)` for the `open_orders` table in the primary database.
    *   **Owner:** Database Team / Order Service Team
    *   **Due Date:** 2024-04-12
2.  **Review `open_orders_settlement` Batch Job:**
    *   **Action:** Analyze the `open_orders_settlement` batch job for other potentially unindexed queries and overall efficiency. Consider optimizing the query `q_9031` further or breaking it into smaller operations.
    *   **Owner:** Order Service Team
    *   **Due Date:** 2024-04-19
3.  **Batch Job Scheduling Review:**
    *   **Action:** Evaluate the scheduling of the `open_orders_settlement` batch job and other non-critical batch jobs running during peak operational hours. Reschedule where possible to off-peak hours or implement resource governors to limit their impact on the primary database.
    *   **Owner:** SRE Team / Operations Team
    *   **Due Date:** 2024-04-26
4.  **Enhance Database Query Monitoring and Alerting:**
    *   **Action:** Implement more aggressive alerting thresholds for sustained long-running queries or rapid increase in database connection pool utilization across all critical database instances. Configure alerts to notify on query execution plans showing full table scans for frequently accessed tables.
    *   **Owner:** SRE Team / Database Team
    *   **Due Date:** 2024-05-03
5.  **Application-Level Query Timeouts for Order Service:**
    *   **Action:** Review and implement/enforce appropriate query timeouts within the `Order Service` application configuration when interacting with the primary database. This would prevent individual slow queries from holding connections indefinitely and allow the application to fail faster and gracefully.
    *   **Owner:** Order Service Team
    *   **Due Date:** 2024-05-10
6.  **Incident Playbook Update:**
    *   **Action:** Update the `Primary Database Exhaustion` playbook to include specific steps for identifying and terminating problematic queries, and a checklist for reviewing recent batch job executions.
    *   **Owner:** SRE Team
    *   **Due Date:** 2024-04-19