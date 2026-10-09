# Interface design and evaluation

## Direction

The interface presents JeyHealth as a calm community reporting workspace. Deep forest green anchors navigation, pale green backgrounds establish trust, and amber distinguishes review work. Colour reinforces written status labels, so it is never the only signal.

Palette: forest `#123f36`, action green `#226d57`, mint `#c4e7cf`, paper `#f5f7f4`, ink `#20362e`, review amber `#b97621`.

Typography uses the locally available Avenir Next family, with system fallbacks. It avoids remote font downloads. The main content is left aligned. Headings, spacing, borders, and restrained icons separate navigation from decisions and evidence.

## Role-specific tasks

- Officials arrive at the district overview with an alert summary, locality map, priority queue, and recent reports. Cluster decisions live in a focused dialog beside the evidence and retained history.
- Volunteers and clinic workers arrive directly at the new report form. Location and symptom selection precede counts and dates. The submit action is explicit, and success shows a reference number and links to history.
- Residents arrive at a community portal with a short explanation of tips and their verification. The interface avoids implying that a resident can confirm an outbreak.

The sign-in role cards populate demo credentials. Authentication still depends on the account rather than a browser-selected role.

## Interaction decisions

- Simple labels, sensible defaults, validation, and specific feedback support users with limited digital experience.
- A number of people field supports the household encounters shown in the project mockups. Each submission remains one encounter rather than a disease diagnosis.
- Notes discourage names, phone numbers, and exact household addresses.
- Native dialogs contain review tasks and support Escape, focus containment, and keyboard navigation.
- Search and filters update the report table without fetching every keystroke.
- Drafts are saved on the same device, separately for each account. They contain observations, so shared-device users should sign out and avoid sensitive information.
- The UI polls informational screens every 45 seconds when visible and not interacting with an input. It avoids replacing open review dialogs or reporting drafts.
- A reviewed cluster retains original evidence, even as the current time-window count changes. These values have separate labels.
- Mobile screens use a collapsible navigation drawer, stacked forms, and content that adapts to the viewport. Wide tables scroll inside their container.
- The map labels approximate locality centres and reveals counts on selection. It has an offline-tile fallback while preserving marker interactions and the adjacent textual review queue.
- Map requests use OpenStreetMap's canonical tile endpoint and send only the application origin as the cross-origin referrer. When a tile fails, the entire failed background layer is removed, locality labels remain visible, and a Retry map button lets the user try again. This keeps provider warning images out of the dashboard.

## Evaluation plan

No real-user evaluation has been performed. The following study is prepared for the proposal's usability objective.

Recruit consenting representatives from the four intended roles. Use fictional observations and explain that the prototype is independent academic work. Give each participant the same tasks relevant to their role:

| Role | Tasks |
| --- | --- |
| Volunteer / clinic | Enter an encounter, recover a draft, locate its status, understand a rejected date |
| Official | Find a flagged locality, inspect evidence, verify a citizen tip, record an investigation, publish a notice |
| Resident | Submit a tip, explain what unverified means, find a district notice |

Record task completion, time, assistance, validation mistakes, and whether participants correctly distinguish a tip, a cluster, and an escalation. Collect a short satisfaction survey and open comments. Compare delays and completeness against the participants' current reporting workflow without claiming medical effectiveness from a small usability sample.

Use consented findings to prioritize revisions to terminology, form length, mobile navigation, and evidence visibility. Record actual participant numbers, dates, observed outcomes, and limitations in the academic report rather than presenting this evaluation plan as completed research.
