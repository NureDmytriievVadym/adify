# Story #22 — Track order stages, deadlines, and evidence

## Source and scope

Epic: Order workflow. Backlog priority Must, estimate 8 (ADY-022).

Primary requirements: **FR-037** (work stages and deadlines) and **FR-041** (submit text,
file attachments, or both as evidence, with a malware scan). Related:
**NFR-SEC-004** (file security) and **FR-051** (disputed orders keep their terms frozen).
The SRS leaves evidence attachment limits and retention TBD, so this story fixes interim
rules and lists them below.

> As an order participant, I want to submit evidence and track work stages and deadlines,
> so progress and completion can be documented.

## Stages (FR-037)

Either order participant can add a stage while the order is **in progress** or **in
review**. A stage has a title (1–120 characters) and an optional deadline. The deadline
must be today or later and cannot be later than the order's overall deadline. An order has
at most **10** stages.

Either participant can mark a stage complete or reopen it. Completion records the time and
the account that completed it. Stages are frozen while the order is disputed and in the
final states (done, canceled, rejected), matching FR-051's protection of agreed terms.

The first stages are still created with the order (ADY-019); the API adds more to an
existing order.

## Evidence (FR-041)

A participant can submit a note, one or more files, or both while the order is in progress
or in review:

- note up to **2,000 characters**;
- up to **5 files** per submission;
- each file up to **10 MB**;
- any file type; the detected type is stored from the content, not the extension;
- every file is scanned before anything is stored;
- a submission is immutable: there is no edit or delete endpoint;
- evidence is retained with the order (retention remains TBD in the SRS).

Both participants see every submission, its author, its time, the note, and its files in
the order timeline.

### Malware scanning

The scanner has two layers:

1. A built-in EICAR signature check. It works without external services, so the ticket's
   “upload the EICAR file” demo is deterministic.
2. ClamAV's INSTREAM protocol when `ADIFY_CLAMAV_HOST` is configured. A configured scanner
   that cannot be reached **rejects** the upload instead of accepting an unscanned file.

ClamAV is optional locally and runs in the Compose `malware` profile; the SRS stack names
ClamAV as the production scanner. The scan result is stored with each file.

## API

| Endpoint                                                        | Who         | Result                              |
| --------------------------------------------------------------- | ----------- | ----------------------------------- |
| `POST /api/v1/orders/{id}/stages` `{title, deadline}`           | Participant | `201`, the order with the new stage |
| `POST /api/v1/orders/{id}/stages/{sid}/complete`                | Participant | `200`, the stage time and author    |
| `POST /api/v1/orders/{id}/stages/{sid}/reopen`                  | Participant | `200`, completion cleared           |
| `POST /api/v1/orders/{id}/evidence` (multipart `note`, `files`) | Participant | `201`, the order with the new entry |
| `GET /api/v1/orders/{id}/evidence/{eid}/files/{fid}`            | Participant | The file, inline for images/PDF     |

Order responses now include:

- `stages` with `id`, `title`, `deadline`, `completed_at`, `completed_by`;
- `evidence` (`id`, `author`, `note`, `files`, `created_at`), oldest first;
- each evidence file has `id`, `filename`, `content_type`, `size`, `url`, `created_at`.

The evidence upload is multipart, so the backend adds `python-multipart` to its
dependencies. Files are stored through the shared storage module; the API only serves them
to the two order participants.

| Status | `type`                       | Cause                                          |
| ------ | ---------------------------- | ---------------------------------------------- |
| 401    | `not_authenticated`          | No valid access token                          |
| 403    | `not_order_participant`      | Anyone outside the order                       |
| 404    | `order_not_found`            | Unknown order                                  |
| 404    | `stage_not_found`            | Unknown stage                                  |
| 404    | `evidence_not_found`         | Unknown evidence or file                       |
| 409    | `order_not_workable`         | Stages/evidence changed in a frozen state      |
| 409    | `stage_limit`                | More than 10 stages                            |
| 409    | `stage_already_completed`    | Completing a completed stage                   |
| 409    | `stage_not_completed`        | Reopening a pending stage                      |
| 413    | `evidence_file_too_large`    | A file over 10 MB                              |
| 422    | `stage_deadline_past`        | A stage deadline in the past                   |
| 422    | `stage_deadline_after_order` | A stage deadline later than the order deadline |
| 422    | `evidence_empty`             | No note and no files                           |
| 422    | `evidence_note_too_long`     | Note over 2,000 characters                     |
| 422    | `too_many_evidence_files`    | More than 5 files in one submission            |
| 422    | `evidence_file_empty`        | An empty file                                  |
| 422    | `malware_detected`           | The malware scanner rejected a file            |
| 503    | `malware_scan_unavailable`   | A configured ClamAV daemon is unreachable      |

## Persistence

Migration `0016` (rebased after the order-workflow migrations) adds `completed_at` and
`completed_by_id` to `order_stages`, and creates `order_evidence` and
`order_evidence_files`. A file row keeps the filename, detected type, size, SHA-256
checksum, scan result, and the storage key (its id).

## Web

- The **Work stages** section lists every stage with its deadline, **Overdue** marker, and
  completion author/time. Participants of active orders can mark a stage complete, reopen
  it, and add a stage with a deadline.
- The **Evidence** section shows the timeline from both participants. A note field and file
  picker submit one evidence entry; files with images/PDFs are served inline, other types as
  attachments.
- Errors from the malware scan, limits, and frozen states are shown next to the forms.
- All actions are available to both participants; the API still enforces the order state
  and participant checks.

## Demo (acceptance)

1. Pay and **Start work** on an order (stories #20–#21), so it is **in progress**.
2. As either participant add a stage with a deadline in **Work stages**: it appears with
   the deadline; **Mark complete** records who completed it and when.
3. In **Evidence**, write a note, attach a screenshot, and submit: both participants see the
   entry and can download the file.
4. Attach the EICAR test file (for example `eicar.txt`): the upload is rejected with
   “rejected by the malware scan (Eicar-Test-Signature)”.
5. Optional full scan: run `ADIFY_CLAMAV_HOST=clamav docker compose --profile malware up`
   and repeat step 3; the same EICAR upload is rejected by ClamAV.

## Open TBDs

- Evidence limits (types, size, count) and retention are TBD in the SRS; the values above
  are the interim rules.
- The final malware scanner deployment is ClamAV; the local `malware` profile and the
  built-in EICAR check are development conveniences.
- The SRS allows evidence while an order is disputed (FR-051); this story intentionally
  leaves that to the dispute stories, so the form is limited to in progress and in review.
- Stage editing/deletion and stage-level evidence links are not in the ticket; stages
  currently support add, complete, and reopen only.
- Evidence notifications are not part of this ticket.

## Automated acceptance

- `backend/tests/test_stages_evidence.py`: both participants add stages, validation
  (past/after order/limit), complete/reopen with author and time, frozen and unknown states,
  outsider refusal, note/file evidence, both participants see it, participant-only
  downloads, EICAR rejection (with or without ClamAV), file count/size/note limits,
  unreachable-scanner rejection, and any-type storage.
- `frontend/tests/e2e/stages-evidence.spec.ts`: adding and completing/reopening a stage,
  submitting a note and screenshot, the malware error path, and axe Level A.
