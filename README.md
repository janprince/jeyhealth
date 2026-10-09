# JeyHealth Report

A working local prototype of Janet Adu Somuah's **Community Disease Outbreak Early-Warning System**, based on the two supplied PowerPoint presentations. The interface is an original redesign, as requested, rather than a reproduction of the slide mockups.

The project gives community health volunteers and clinic workers a structured way to report symptom encounters. It groups trusted reports by locality, symptom category, and date. When the configured case threshold is met, it flags a cluster for a district official to investigate. Residents can submit tips, which count only after verification, and read published community advisories.

## Run

Requires Python 3.10 or later. No dependency installation, Firebase account, API key, or build step is required.

```sh
cd /Users/kami/Projects/SCHOOL
python3 server.py
```

Open [http://localhost:8000](http://localhost:8000). Alternatively, `npm start` runs the same command. To use another port: `python3 server.py --port 8080`.

The first run creates `data/jeyhealth.sqlite3` with fictional demonstration records, eight approximate locality centres in Ga West, and four accounts. Data and decisions persist across restarts. Subsequent runs leave existing data intact.

| Account | Email | Responsibilities |
| --- | --- | --- |
| District official | `official@jeyhealth.local` | View district reports, review tips and clusters, change rules, publish notices, export data |
| Health volunteer | `chv@jeyhealth.local` | Submit observations and view own reporting history |
| Clinic staff | `clinic@jeyhealth.local` | Submit facility observations and view own reporting history |
| Resident | `resident@jeyhealth.local` | Submit unverified tips, follow own tips, read notices |

All demo passwords are `JeyHealth2026!`. The sign-in role selector fills these credentials. It does not grant permissions: the backend uses the role associated with the authenticated account.

## Included features

- Responsive desktop and mobile layouts with keyboard navigation, labelled forms, visible focus, native dialogs, and reduced motion support.
- Password authentication, server sessions, role checks on the API, and CSRF protection.
- Case reporting with locality, symptoms, observation date, count, and notes. No patient identity fields.
- Drafts stored on the current device, validation, submission feedback, and duplicate-request protection.
- A rolling-window detection rule, initially **at least 5 trusted cases of the same symptom category in one locality over 3 calendar days**.
- District overview with a real Leaflet map, review queue, and recent reports.
- Report search and filters for locality, symptoms, and review status.
- Cluster investigation, escalation as a **suspected** outbreak, dismissal, and resolution, each with required notes and history.
- Verification of resident tips, with immediate recalculation of detection.
- Analytics based on actual database records, including weekly case trends, symptom distribution, and review outcomes.
- District advisory publication, visible to signed-in users.
- CSV export without encounter notes or reporter names.
- Configurable rules and retained decision history.

## A short demonstration

1. Sign in as the district official. Review the three seeded clusters on the overview.
2. Open a cluster, inspect contributing reports, enter notes, and start an investigation or escalate it.
3. Open All reports, filter to unverified tips, and verify the resident's tip.
4. Publish a sample advisory, sign out, and open the resident account to see it.
5. Sign in as a health volunteer. Submit a sample encounter and check My reports.
6. Return to the official account to see the new report and updated analytics.

## Implementation choice

The proposal suggests Firebase with either React or lightweight HTML/CSS/JavaScript. This implementation uses the lightweight frontend option and replaces Firebase with a Python/SQLite backend so the entire prototype works immediately without cloud credentials. Authorization, verification, clustering, persistence, and history run on the server rather than trusting browser state.

This is a local academic demonstration. It uses a development HTTP server and public demo accounts. Cloud deployment, account provisioning, clinical validation, notifications to health authorities, and live patient data are not implemented. Basemap tiles need internet access; the bundled map library, markers, forms, and local reporting work without downloading frontend dependencies. Drafts save locally while offline, but submitting requires access to the server.

The default threshold is an illustrative rule from the proposal, not a clinical guideline. Escalating records a decision within the application; it does not send email, SMS, or external alerts. Analytics describe entered observations rather than population incidence. No diagnosis, treatment recommendations, hospital integrations, or insurance integrations are included.

## Tests and documentation

```sh
python3 -m unittest discover -s tests -v
```

The tests use a temporary database and HTTP server. They verify boundaries of the rolling window, separation by locality and symptom category, verification trust, closed-cluster suppression, new evidence, authentication, role restrictions, CSRF, input validation, duplicate submissions, review history, transitions, notices, rule changes, and export access.

Browser workflow tests are in `tests/browser.cjs`; they need Playwright and Chrome. Run against a separate seeded instance so the presentation database stays unchanged. See the script header for commands.

- [Project explanation and requirement coverage](docs/PROJECT.md)
- [Architecture, data model, and API](docs/ARCHITECTURE.md)
- [Interface design decisions and evaluation plan](docs/DESIGN.md)
- [Verification results](docs/VERIFICATION.md)

Leaflet 1.9.4 is bundled in `public/vendor`, together with its license. The basemap comes from OpenStreetMap with attribution displayed on the map.
