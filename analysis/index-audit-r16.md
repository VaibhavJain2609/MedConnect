# R16 — DB Index Audit (hot query paths)

Scope: `backend/app/models/*.py` (main DB + medicine DB), all `.where(` /
`.join(` / `order_by(` call sites across `app/routers/`, `app/services/`,
`app/workers/`, compared against indexes already declared in models and
created by migrations `001`–`037`.

Result: **9 new indexes** in migration `038_hot_path_indexes`
(down_revision `037_medication_reminders`), with matching `Index(...)`
entries added to the model `__table_args__` so metadata/autogen stays in
sync (project convention — every existing model index has a migration
counterpart).

## Indexes added

| Index | Table (cols) | Predicate | Query path it serves |
|---|---|---|---|
| `idx_appointments_clinic_scheduled_at` | `appointments(clinic_id, scheduled_at)` | `deleted_at IS NULL` | Clinic daily schedule: `clinic_id = ? AND scheduled_at BETWEEN day_start AND day_end ORDER BY scheduled_at` — `routers/appointments.py` list endpoint (clinic ctx branch ~L755/773/818). Previously `idx_appointments_clinic` fetched *all* of a clinic's appointments then filtered+sorted. |
| `idx_appointments_created_at` | `appointments(created_at)` | `deleted_at IS NULL` | Admin dashboard "recent activity": `ORDER BY created_at DESC LIMIT n` over the whole table — `routers/admin/stats.py` ~L468. |
| `idx_records_document_url` | `medical_records(document_url)` | `document_url IS NOT NULL AND deleted_at IS NULL` | Download authorization: `document_url = object_key AND deleted_at IS NULL` on **every** file fetch — `routers/uploads.py::_user_can_access_object` (~L357). Was a sequential scan. |
| `idx_rx_valid_until` | `prescriptions(valid_until)` | `valid_until IS NOT NULL AND deleted_at IS NULL` | `check_prescription_expiry` ARQ task range scan `valid_until BETWEEN window_start AND window_end ORDER BY valid_until` — `workers/tasks/prescription_expiry.py` ~L73. Also helps the `valid_until >= today` filter in `workers/tasks/medication_reminders.py` ~L117. |
| `idx_rx_created_at` | `prescriptions(created_at)` | `deleted_at IS NULL` | Admin stats prescription trend: repeated `created_at >= ? AND created_at < ?` counts + `GROUP BY date(created_at)` — `routers/admin/stats.py` L182/189/323/329. (`idx_rx_patient(patient_id, created_at)` can't serve unscoped ranges.) |
| `idx_users_created_at` | `users(created_at)` | `deleted_at IS NULL` | Admin user list `ORDER BY created_at DESC` pagination — `routers/admin/users.py` L83/122; admin stats patient trend ranges — `routers/admin/stats.py` L149/243/417; admin exports ordering. |
| `idx_doctors_created_at` | `doctors(created_at)` | `deleted_at IS NULL` | Admin doctor list `ORDER BY created_at DESC` — `routers/admin/doctors.py` L87; doctor trend range counts — `routers/admin/stats.py` L198/362/368. |
| `idx_encounters_created_at` | `encounters(created_at)` | `deleted_at IS NULL` | Admin visits list `ORDER BY created_at DESC` pagination over all encounters — `routers/admin/visits.py` L110. (`idx_encounters_clinic_created_at` is clinic-led and can't serve the unscoped ordering.) |
| `idx_pcl_clinic_consent` | `patient_clinic_links(clinic_id, consent_status)` | `deleted_at IS NULL` | Doctor↔patient access-control join `PCL.clinic_id = ClinicMembership.clinic_id AND consent_status IN (...) AND deleted_at IS NULL` — `services/access_service.py::accessible_patient_ids_select` (reused by search, doctor patient list, record-access checks, uploads auth) and `routers/doctors.py` clinic_subq ~L148. |

## Already covered (verified — no action)

- `appointments`: `doctor_id+scheduled_at`, `patient_id+scheduled_at` (conflict checks + lists), `clinic_id`, `status`, `branch_id`, partial-unique `source_encounter_id`, GiST exclusion constraint for double-booking.
- `queue_entries`: unique `(clinic_id, queue_date, queue_number)`, `clinic_id+created_at`, `clinic_id+status`, `doctor_id`, `patient_id`, `appointment_id` — covers every queue WHERE (clinic + day-range + status) and the wait-estimate/count queries.
- `medical_records`: `patient_id+created_at`, `doctor_id`, `record_type`, `created_at`, `clinic_id`, `amended_from_id`, `family_member_id`.
- `notifications`: `user_id+read`, `user_id+type`, `user_id+created_at` (+ column indexes). NotificationPreferences.user_id unique.
- `patient_vitals`: `(patient_id, vital_type, recorded_at)` — covers patient+type history and patient-only lists.
- `prescriptions`: `record_id` unique, `patient_id+created_at`, `doctor_id`, `clinic_id`, `branch_id`, `appointment_id`.
- `patient_clinic_links`: unique `(patient_id, clinic_id)`, `patient_id`, `clinic_id`. `patient_link_codes`: unique `patient_id`, `code`.
- `clinic_memberships`: unique `(user_id, clinic_id)` + both single-col indexes — covers `get_active_clinic` on every clinic-scoped request.
- `encounters`: `doctor_id`, `patient_id`, `appointment_id`, `clinic_id+created_at`.
- `audit_logs`/`audit_log_archive`: `table_name+record_id`, `changed_by`, `changed_at` — covers admin audit list + retention worker.
- `billing`/`billing_items`, `lab_orders`, `lab_results`, `webhook_endpoints`/`webhook_deliveries`, `clinic_invites`/`clinic_join_requests`, `doctor_availability`/`doctor_leaves`, `clinic_holidays`, `appointment_waitlist`, `prescription_refill_requests`, `prescription_templates`, `prescription_safety_checks`, `medication_reminders`, `push_subscriptions`, `platform_settings`, `family_members`, `reminder_logs`, `record_access_consents`, `idempotency_keys` (composite PK), medicine-DB models — all already indexed on their queried columns.

## Deliberately skipped

- **`patient_clinic_links(patient_id, consent_status)`** — suggested in the audit brief, but `idx_pcl_patient` already leads with `patient_id`; per-patient link cardinality is tiny (a handful of clinics). The *clinic-led* consent filter is the one that matters → added as `idx_pcl_clinic_consent`.
- **`users.is_active`**, **`doctors.verified`**, **`clinics.is_active`** (standalone) — low-selectivity booleans; always combined with an indexed column (`role`, membership join) or used on admin lists already served by the new `created_at` indexes.
- **`lab_results.appointment_date`** ordering — always scoped by `patient_id` (indexed); per-patient sort set is small.
- **`lab_orders.created_at`** ordering — always scoped by `doctor_id`/`patient_id` (indexed).
- **`reminder_logs.status`** — no scan by status exists; lookups are `appointment_id` (indexed + unique constraint).
- **`idempotency_keys.created_at`** — reads/deletes go through the composite PK; TTL is lazy-evaluated on read, no range scan.
- **`queue_entries.queue_date`** — queries filter `created_at` ranges (covered by `idx_queue_entries_clinic_created_at`); `queue_date` is only used by the unique constraint itself.
- **`Notification.meta` JSONB keys** (`queue_entry_id`, `kind`) — dedup checks are `user_id`-led (indexed); a GIN/jsonb-path index is not justified at current cardinality.
- **`medical_records(patient_id, record_type)`** — `record_type` filter is applied per-patient (indexed); per-patient record counts don't warrant a composite.
- **ILIKE search columns** (`users.full_name`, `clinics.name`, `appointments.chief_complaint`, `doctors.specialization`, brand/salt names in search.py) — btree indexes can't serve `%term%` patterns; would need pg_trgm — out of scope for this audit.
- **Medicine DB** (`brands`, `salts`, etc.) — FK/lookup columns already carry `index=True`; search is ILIKE (see above).
