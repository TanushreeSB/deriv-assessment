# Post-Mortem: Primary Database Exhaustion Leading to Pricing Service Outage

**Incident ID:** INC-20240315-001

## 1. Executive Summary

On March 15, 2024, at approximately 14:11 UTC, platform-wide trading functionality was halted due to the inability to serve price quotes from the Pricing service. This critical outage was caused by a database connection pool exhaustion in the primary database, triggered by a long-running batch job query. A daily batch job, `user_positions_recalc`, executed a query (`q_4489`) against the `user_positions` table. Due to a missing index on the `user_positions` table for the columns `user_id` and `position_date`, this query resulted in a full table scan, consuming excessive database resources and ultimately exhausting the primary database's connection pool. This rendered the Pricing service unresponsive, leading to API Gateway timeouts and circuit breaker activation, culminating in the trading halt. The issue was resolved by manually killing the long-running query.

**Impact Duration:**
*   **First Symptom to Resolution Trigger:** 14 minutes (14:08:44 UTC - 14:22:08 UTC)
*   **Business Impact (Trading Halted):** 15 minutes 35 seconds (14:11:10 UTC - 14:26:45 UTC)

## 2. Timeline of Events

All times are UTC.

*   **14:08:44:** API Gateway request latency p99 increased to 340ms, indicating the first symptom of degradation.
*   **14:09:01:** Pricing service detected a slow query (q_4821) taking 2100ms.
*   **14:09:15:** Pricing service detected another slow query (q_4822) taking 3400ms.
*   **14:10:33:** Primary database connection pool exhausted, with 47 requests waiting.
*   **14:10:45:** API Gateway experienced an upstream timeout trying to reach the Pricing service.
*   **14:11:02:** API Gateway circuit breaker opened for the Pricing service.
*   **14:11:10:** Trading halted platform-wide due to inability to serve price quotes. (Major Business Impact)
*   **14:11:45:** PagerDuty alert triggered, on-call engineer notified.
*   **14:16:30:** Engineer acknowledged the alert and began investigation.
*   **14:22:08:** Long-running query (q_4489) on the `user_positions` table in the primary database killed after 731 seconds. (Resolution Trigger)
*   **14:22:09:** Primary database connection pool began recovering, with 12 requests still waiting.
*   **14:23:15:** Pricing service query latency reported returning to normal.
*   **14:24:00:** API Gateway circuit breaker transitioned to HALF-OPEN state for Pricing service.
*   **14:25:30:** API Gateway circuit breaker closed, indicating Pricing service recovering.
*   **14:26:45:** Trading resumed on the platform. (Full Service Restoration)
*   **14:45:00:** Post-incident analysis identified query `q_4489` originated from the `user_positions_recalc` batch job, scheduled daily at 14:00 UTC.
*   **14:45:01:** Post-incident analysis determined the `user_positions` table lacked an index on `user_id` and `position_date`, causing `q_4489` to trigger a full table scan.

## 3. Impact

*   **Users Impacted:** All users attempting to trade on the platform during the outage experienced a complete halt in trading functionality.
*   **Business Impact:** Complete inability to process trades for approximately 15 minutes 35 seconds, leading to potential financial losses and reputational damage.
*   **Service Impact:** The Pricing service became unavailable, leading to upstream timeouts for the API Gateway and subsequent circuit breaker activation, which isolated the Pricing service to prevent cascading failures.
*   **System Impact:** Primary database connection pool exhaustion, severe degradation of database performance.

## 4. Root Cause Analysis

The primary root cause of this incident was the execution of an unoptimized batch job query (`q_4489`) against the `user_positions` table in the primary database.

**Primary Root Cause:**
*   **Missing Database Index:** The `user_positions` table lacked a critical index on the `user_id` and `position_date` columns. This deficiency meant that the batch job query `q_4489`, which filters or sorts on these columns, resulted in a full table scan rather than an efficient indexed lookup.

**Contributing Factors:**
*   **Batch Job Scheduling during Operational Hours:** The `user_positions_recalc` batch job was scheduled to run daily at 14:00 UTC, which falls within active trading hours. This increased the contention for database resources during a period of high transactional load.
*   **Insufficient Database Monitoring & Alerting for Query Duration:** While slow queries were detected by the Pricing service, proactive alerts for long-running queries consuming excessive resources at the database level were not sufficient to prevent connection pool exhaustion.
*   **Lack of Performance Review for Batch Jobs:** The `user_positions_recalc` batch job's queries were not adequately reviewed for their performance impact on the primary database, especially considering its scheduled execution during peak hours.

**Similar Failure Modes (INC-2024-007 and INC-20240405-DB-EXHAUSTION):**
This incident shares significant similarities with previous incidents (e.g., INC-2024-007 and INC-20240405-DB-EXHAUSTION). In all these cases, a batch job scheduled during operational hours executed a query that caused a full table scan due to a missing database index (e.g., on the `transactions table` in INC-2024-007 and `open_orders` table in INC-20240405-DB-EXHAUSTION). This consistently led to database connection pool exhaustion, upstream service timeouts, circuit breaker activation, and ultimately, a halt in critical platform functionality. While the specific services and tables differ, the underlying failure chain, originating from an unoptimized batch job query causing resource contention, remains a recurring pattern.

## 5. Lessons Learned

**What Went Well:**
*   **Automated System Protection:** The API Gateway circuit breaker successfully isolated the Pricing service, preventing cascading failures to other parts of the system when it became unresponsive.
*   **Alerting System:** PagerDuty successfully triggered and notified the on-call engineer within minutes of the major business impact, initiating the human response.
*   **Engineer Response:** The on-call engineer quickly identified the long-running query as the root cause and took decisive action to terminate it, leading to a swift recovery.
*   **Post-Incident Analysis:** The team was able to quickly pinpoint the specific batch job and the missing index as the underlying cause.

**What Could Be Improved:**
*   **Proactive Database Performance Monitoring:** Detection of long-running queries or impending connection pool exhaustion could have been more proactive, potentially allowing intervention before critical impact.
*   **Batch Job Resource Management:** The current process for scheduling and validating batch jobs' database impact is insufficient, especially for jobs running during peak hours.
*   **Database Schema Review Process:** The absence of a critical index suggests a gap in the review process for database schema changes or query performance for new features/jobs.
*   **Automated Query Killing:** There is no automated mechanism to kill queries exceeding a certain duration or resource threshold, relying solely on manual intervention.

## 6. Action Items

The following action items will be implemented to prevent recurrence and improve resilience:

1.  **Add Missing Index on `user_positions` table:**
    *   **Description:** Create an index on the `user_positions` table for columns `user_id` and `position_date` to optimize query `q_4489` and similar queries.
    *   **Owner:** Database Team
    *   **Due Date:** 2024-03-22
2.  **Review `user_positions_recalc` Batch Job Scheduling:**
    *   **Description:** Evaluate moving the `user_positions_recalc` batch job execution outside of peak operational hours (e.g., to off-peak times) or investigate further query optimization for `q_4489` to minimize resource contention during runtime.
    *   **Owner:** Engineering Lead (Pricing Service)
    *   **Due Date:** 2024-03-29
3.  **Implement Enhanced Database Query Monitoring and Alerting:**
    *   **Description:** Configure proactive alerts for long-running queries (e.g., queries exceeding 60 seconds) specifically for the primary database. Alerts should include details on the query, originating service/user, and affected tables.
    *   **Owner:** SRE Team
    *   **Due Date:** 2024-04-12
4.  **Establish Batch Job Performance Review Process:**
    *   **Description:** Implement a mandatory review process for all new or modified batch jobs, especially those interacting with core production databases. This review will include an analysis of query execution plans and potential resource impact on specific tables (e.g., `user_positions`, `open_orders`).
    *   **Owner:** Platform Architecture
    *   **Due Date:** 2024-04-26
5.  **Review Primary Database Connection Pool Configuration:**
    *   **Description:** Analyze the current primary database connection pool size and configuration to ensure it can gracefully handle spikes in demand or transient slow queries without exhausting the pool completely.
    *   **Owner:** SRE Team / Database Team
    *   **Due Date:** 2024-04-19
6.  **Investigate Automated Long-Running Query Termination:**
    *   **Description:** Explore and implement automated mechanisms (e.g., database-level configuration or custom tooling) to gracefully terminate queries that exceed predefined resource or time thresholds, focusing on high-impact tables like `user_positions`.
    *   **Owner:** SRE Team / Database Team
    *   **Due Date:** 2024-05-10