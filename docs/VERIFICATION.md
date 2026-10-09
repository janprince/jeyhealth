# Verification record

Verified on 1 October 2026 using fictional data. No real-user usability study or clinical evaluation has been performed.

## Backend

`python3 -m unittest discover -s tests -v`: **16 tests passed**. The suite exercises the actual HTTP handlers and detection code against an isolated SQLite database.

It covers threshold equality, inclusive calendar-day boundaries, locality/category separation, resident trust, dismissed reports, ageing evidence, closed episodes and new evidence, authentication, account-level visibility, role authorization, idempotency, validation, CSRF, cross-origin mutations, report verification, audit events, cluster transitions, notices, logout, rule recalculation, and CSV export permissions.

## Browser

`tests/browser.cjs`: **passed** with Playwright and installed Google Chrome, against a separate seeded application instance.

Verified workflows:

- District official: map markers and locality popup, cluster investigation, escalation, resolution, tip verification, search, category filters, empty results, advisory publication, rules, and analytics.
- Volunteer: form submission, draft restoration after reload, own history, no review permissions, and a second independent encounter after returning from history.
- Clinic worker: facility encounter submission.
- Resident: phone layout, tip submission, unverified status, mobile navigation, and viewing an official advisory.
- Mobile official: no horizontal page overflow at 390 pixels, cluster evidence dialog, and Escape to close.
- User-provided HTML in notices displays as text rather than executing. No browser JavaScript exceptions occurred.

Rendered desktop overview, analytics, resident phone form, and official phone review screenshots were visually inspected. The browser test initially identified an overflow from an unpositioned table container; the container now bounds hidden accessibility labels and scrolling to the table. Final checks passed after the fix.

## Limits

Testing does not prove production readiness, medical validity, population representativeness, accessibility conformance, or usability for actual field workers. The project includes a proposed real-user evaluation in `DESIGN.md`. All tested decisions and notices were made in a separate fictional-data instance, leaving the demonstration database intact.

## Map correction, 2 October 2026

The in-app browser displayed OpenStreetMap's blocked-access tiles. The response previously set `Referrer-Policy: same-origin`, suppressing the cross-origin referrer required by the tile service. It now uses `strict-origin-when-cross-origin`, the canonical `https://tile.openstreetmap.org/{z}/{x}/{y}.png` endpoint, and a matching image CSP allowlist. Frontend asset versions were updated to replace cached code.

Verified in the user's existing in-app browser: tile images loaded at their native 256-pixel width, street geography rendered, and all eight locality pins remained visible. `map-fixed.jpg` records the corrected view. A regression test checks the response headers. Failed backgrounds now clear completely and offer labelled locality pins and a Retry map button.
