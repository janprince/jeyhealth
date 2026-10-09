# Architecture and data model

The browser serves the interface from `public/`. A Python HTTP server hosts static assets and exposes JSON endpoints. SQLite stores users, sessions, observations, alerts, advisories, and events. A transaction updates an observation and runs cluster detection together. Foreign keys and a unique active-cluster index protect relationships and prevent duplicate active alerts.

## Entities

| Entity | Key information and relationships |
| --- | --- |
| users | Name, email, password hash, role |
| sessions | Hashed random token, user, expiry, CSRF token |
| login_attempts | Account/client key and recent failed attempt count |
| localities | District, name, approximate centre coordinates |
| reports | Locality, symptom category, count, observation date, notes, author, status, unique submission key |
| clusters | Locality, category, status, initial threshold/window, current count, reviewer and timestamps |
| cluster_reports | Many-to-many links retaining the reports that contributed to an alert |
| events | Entity type and ID, action, actor, notes, timestamp |
| advisories | Title, message, optional locality, publishing official, date |
| settings | Current minimum case count and rolling window length |

Users can submit many reports. Localities can hold many reports and clusters. A cluster can retain many reports, and a report can contribute to a subsequent reviewed episode. Events describe changes without replacing previous notes.

## Detection algorithm

1. Calculate the window start as today minus `window_days - 1`, using the Africa/Accra calendar. Both endpoints are inclusive.
2. Include observation dates from that start through today. Ignore dismissed reports. Include volunteer/clinic reports and officially verified resident tips.
3. Group by locality and exact symptom category. Sum the number of people affected in each encounter.
4. If an active cluster exists, update its current count and retain newly contributing evidence.
5. If no active cluster exists and the count is at least the threshold, create an alert. After a closed episode, require a report created or reviewed after that closure before alerting again.
6. Preserve the original trigger rule, linked evidence, history, and human decision when the rolling count falls. A signal does not silently disappear merely because its date window moves.

The window and threshold displayed as the current rule may differ from the rule that initially triggered an alert. The cluster detail shows both retained evidence and current counts. Existing evidence may include later-dismissed reports, which retain their displayed status.

Example: for 1 October with a 3-day window, include 29 September through 1 October. Five trusted acute watery diarrhoea cases in Ablekuma flag that locality/category. Cases in Oduman or another category do not contribute to the same group. An unverified citizen tip contributes zero until official verification.

## State transitions

Report: a worker submission starts as `submitted`; a resident tip starts as `unverified`. An official can transition either to `verified` or `dismissed`, with required notes. Reviewed reports cannot be rewritten through this API.

Cluster: `pending` can become `investigating`, `escalated`, or `dismissed`. `investigating` can become `escalated` or `dismissed`. `escalated` can become `resolved`. A closed record remains closed. A qualifying subsequent observation may create a new episode.

## API

| Method and path | Permission | Purpose |
| --- | --- | --- |
| POST `/api/login` | Credentials | Create a session |
| GET `/api/state` | Any signed-in user | Role-filtered records and configuration |
| POST `/api/logout` | Signed in + CSRF | Revoke the current session |
| POST `/api/reports` | Volunteer, clinic, resident + CSRF | Validated, idempotent observation submission |
| POST `/api/reports/review` | Official + CSRF | Verify or dismiss a report |
| POST `/api/clusters/review` | Official + CSRF | Record an allowed cluster decision |
| POST `/api/settings` | Official + CSRF | Update detection rules with a reason |
| POST `/api/advisories` | Official + CSRF | Publish a notice |
| GET `/api/export` | Official | CSV of report metadata without free-text notes or author names |

Session cookies use HttpOnly and SameSite=Strict. Passwords use salted PBKDF2-SHA256. Sessions expire after eight hours and are stored using hashed tokens. State responses never expose password hashes or session tokens. POST routes check origin and an authenticated CSRF token. Incorrect login attempts receive a short rate limit. CSV output escapes spreadsheet formula prefixes. User content is escaped before rendering in HTML.

The app does not provide registration, password recovery, staff provisioning, encryption at rest, or a production HTTPS deployment. A production handover requires those functions, a managed application server, identity lifecycle controls, operational monitoring, backups, and validation by the adopting health authority.

## Persistence and operation

`JEYHEALTH_DB` can specify an alternate SQLite file. The default is `data/jeyhealth.sqlite3`. Initialization seeds only an empty user table, so normal restarts preserve data. Database connections enable foreign keys and initialization enables WAL.

For a live database backup, use SQLite's backup API rather than copying only the `.sqlite3` file while WAL is active. The schema is intentionally small for academic evaluation and future migration. The localhost bind is deliberate for the demonstration.
