Based on both postmortems, here are the shared systemic action items, categorized for clarity:

---

### Shared Systemic Action Items

These action items address common underlying issues identified in both **Postmortem A (Primary Database Exhaustion Leading to Pricing Service Outage)** and **Postmortem B (Incident INC-20240405-DB-EXHAUSTION)**.

1.  **Enhanced Database Performance Monitoring & Alerting**
    *   **Description:** Implement more robust and proactive monitoring and alerting specifically for database performance. This includes configuring aggressive thresholds for sustained long-running queries, detection of full table scans on critical tables, rapid increases in database connection pool utilization, and impending connection exhaustion. Alerts should trigger *before* critical impact and provide detailed contextual information (query, origin, affected tables).
    *   *Rationale:* Both incidents highlight insufficient proactive detection, with alerts often triggering only after significant degradation or impact. (Ref: A: `A3. Implement Enhanced Database Query Monitoring and Alerting`, B: `B4. Enhance Database Query Monitoring and Alerting`)

2.  **Formal Batch Job Management & Performance Review Process**
    *   **Description:** Establish a mandatory review process for all new or modified batch jobs, especially those interacting with core production databases. This process must include thorough analysis of query execution plans, potential resource impact (e.g., full table scans), and optimization. Additionally, conduct a comprehensive review of existing batch job scheduling to move resource-intensive jobs outside of peak operational hours or implement resource governors.
    *   *Rationale:* Both incidents were triggered by unoptimized batch jobs running during operational hours, causing full table scans and resource contention. (Ref: A: `A2. Review user_positions_recalc Batch Job Scheduling`, `A4. Establish Batch Job Performance Review Process`, B: `B2. Review open_orders_settlement Batch Job`, `B3. Batch Job Scheduling Review`)

3.  **Database Schema & Index Management Review Process**
    *   **Description:** Implement a formal and rigorous review process for database schema changes and the introduction of new or modified queries (e.g., as part of new features or batch jobs). This process should explicitly ensure that necessary indexes are identified and created to support efficient query execution, preventing full table scans on frequently accessed or large tables.
    *   *Rationale:* The fundamental root cause in both incidents was a missing database index leading to a full table scan. This points to a systemic gap in how schema changes and query optimizations are reviewed or enforced during development and deployment. (Ref: A: `Primary Root Cause: Missing Database Index`, `Lessons Learned: Database Schema Review Process`, B: `Root Cause: missing database index`)

4.  **Automated Query Management & Resource Governance**
    *   **Description:** Investigate and implement automated mechanisms to prevent individual long-running queries from monopolizing database resources. This could include database-level configurations for automatically terminating queries exceeding predefined time or resource thresholds, or enforcing application-level query timeouts for services interacting with the primary database.
    *   *Rationale:* In both cases, manual intervention was required to kill the long-running query. Automated protection would have reduced impact duration. (Ref: A: `A6. Investigate Automated Long-Running Query Termination`, B: `B5. Application-Level Query Timeouts for Order Service`)

5.  **Database Connection Pool Configuration Review**
    *   **Description:** Periodically review and optimize the primary database's connection pool size and configuration for all critical services. The goal is to ensure connection pools are adequately sized to handle anticipated load and transient spikes without becoming exhausted, while also considering the impact of holding idle connections.
    *   *Rationale:* Database connection pool exhaustion was a direct and critical consequence in both incidents, indicating potential misconfiguration or lack of resilience in handling spikes/slow queries. (Ref: A: `A5. Review Primary Database Connection Pool Configuration`, B: `System Impact: Primary database connection pool exhausted`)

6.  **Incident Response Playbook Enhancement**
    *   **Description:** Update existing incident playbooks for database-related outages (specifically connection pool exhaustion caused by long-running queries) to include clearer, more detailed steps for rapidly identifying and terminating problematic queries, and a checklist for reviewing recent batch job executions or deployments as a potential cause.
    *   *Rationale:* While specific to Postmortem B, enhancing playbooks for recurring failure modes is a critical systemic improvement for faster and more efficient incident resolution. (Ref: B: `B6. Incident Playbook Update`)