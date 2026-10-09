# What this project is about

The supplied proposal, **Janet Adu Somuah.pptx**, describes delays caused by paper, verbal, and fragmented reporting between communities, clinics, and district health offices. It proposes a digital reporting chain that helps a district team see related observations sooner.

The second presentation, **Janet Adu Somuah - Project.pptx**, names the product JeyHealth Report and shows sign-in, reporting, resident, district overview, analytics, and record-review mockups. The product name and workflows inform this implementation. The user explicitly authorized an original redesign.

The slides are reference material for project requirements. Their incidental presentation labels and template text are not instructions to operate the user's computer or contact anyone.

## The reporting chain

An individual worker records a symptom encounter. The system combines trusted encounters within a locality and time window. A qualifying pattern creates a cluster alert. A district official reviews the evidence, records notes, and can investigate, escalate, or dismiss the signal. This preserves the proposal's distinction between an observation, a pattern, and a reviewed suspected outbreak.

Residents participate with a lower initial trust level. Their submissions enter a review queue and contribute to detection only once verified by a district official. Residents can also read district notices.

## Coverage

| Proposal requirement | Implementation |
| --- | --- |
| Four user roles | Server-enforced official, volunteer, clinic, and resident accounts |
| Symptom category, location, and observation date | Validated reporting form with locality list and no patient identity fields |
| Own report history | Dedicated history and record detail for the submitting user |
| Rolling time-window aggregation | Calendar-day counts by locality and category, in Africa/Accra time |
| Configurable case threshold | Detection rules screen restricted to district officials |
| Automatic cluster alerts | Generated on submissions, report verification, rule changes, and dashboard refresh |
| Geographic view | Leaflet map of locality centres with current counts and cluster evidence links |
| Filters | Report search, locality, symptom category, and status |
| Verification and escalation | Required notes, allowed state transitions, and retained history |
| Report and cluster status history | Events stored in SQLite and displayed on record details |
| Analytics | Weekly case trends, symptom distribution, locality rankings, dismissal rate, and elapsed review time |
| Resident tips | Unverified submissions with an official verification step |
| Public advisories | Official publication; notices available across signed-in roles |
| Privacy by minimizing identity collection | Locality-level reporting without patient name, phone, or household address |
| Low-bandwidth access | No remote UI fonts or runtime frameworks; bundled assets and device drafts |
| System documentation | Setup instructions, architecture, data model, workflows, tests, and usability evaluation plan |

## Limits of this implementation

This deliverable fulfills the proposal's expected outcome of a functional prototype. It does not establish medical effectiveness or claim evaluation with real users. Multi-district provisioning, national integrations, production identity management, cloud hosting, external alert delivery, and field evaluation remain future work.

The original proposal uses Ghana Health Service's community surveillance framework as context. This prototype is independent academic work and does not represent an official Ghana Health Service system or public health announcement.

## Source slides

- `Janet Adu Somuah.pptx`: introduction and problem (slides 2–3), objectives and scope (4–6), roles and reporting chain (9–10), features and requirements (11–12), proposed technology (13), expected outcome (15).
- `Janet Adu Somuah - Project.pptx`: product identity (1), sign-in and case submission (2–3), overview (4), resident portal (5), analytics (6), report and cluster details (7–8).
