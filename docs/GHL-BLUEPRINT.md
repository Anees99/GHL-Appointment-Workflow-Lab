# Native-account implementation blueprint (not yet executed)

Goal: demonstrate appointment reminders without sending duplicate or unwanted messages.

1. In a test sub-account, create a dedicated demo calendar, test contact and consent
   fields; document calendar timezone and account DND behavior.
2. Configure appointment triggers for booking, rescheduling, cancellation and outcomes.
   Verify their actual event payloads and update ordering in that account.
3. Use tags for human-visible state and a defined opportunity pipeline where useful.
   Map the account's real pipeline/stage IDs; do not invent IDs in integrations.
4. Before reminder enrollment, check channel-specific consent and DND. A contact
   record or a calendar booking alone must not enable unrelated marketing.
5. Schedule a reminder relative to appointment start. Apply quiet hours using the
   chosen account/contact timezone policy; that policy is not part of the local lab.
6. On reschedule, remove the obsolete reminder and enroll the new appointment time.
7. On cancellation/completion/no-show, remove the pending reminder. Keep rebooking
   campaigns separate and only enable them after consent/rules are approved.
8. On opt-out, stop the applicable channel and active follow-ups. Review native DND
   propagation; the local simulator intentionally uses stricter contact-wide blocking.
9. Replay synthetic events: duplicate, out-of-order, cancel-then-reschedule, opt-out,
   cross-location contact, and offset changes. Record screenshots and account results.
10. Use a test delivery address/number and verify actual delivery once authorized.

Handover: event map, workflow screenshots/export if supported, test matrix, failure
handling, field/tag dictionary, permissions and secrets setup. No native GHL build
or actual delivery is claimed by this repository.
