# Café owner upgrade — guest-facing areas and notification reliability

## What the new measurement actually means

The YOLO person detector recognizes **people**, never their role. A camera cannot establish whether a person is a customer, barista, visitor or courier from a single frame. FlowPulse **does not classify staff or customers** by uniforms, faces, dress, color or identities.

Instead, the Camera setup page offers a one-time **staff-only side** hint for a *fixed, authorized camera*: none, left half, right half, top half, or bottom half. This is an optional **geometric exclusion** applied to each person's bottom-center detection anchor (image-plane footpoint). All detected people remain included in the original **full camera** count. A separate **guest-facing area** estimate counts detections **outside** the selected staff-only half. It can still include staff in that area and can exclude actual customers on the staff side.

After this one-time selection, the separate guest-facing count, recent activity alert baseline, and aggregate guest-area shift averages update automatically. The count is **not** unique customer visits, purchasing customers, queue size, waiter productivity, headcount or wait time. If the camera angle cannot clearly separate staff-only from guest-facing space, keep **Show everyone**, the default.

## How an owner uses it

1. Start FlowPulse, authorize and preview a stationary permitted café camera. The camera never starts without an operator action.
2. Open **Camera setup → Does your camera also see behind the counter?**. Select the approximate half **used primarily by staff** (or leave **Show everyone**).
3. Inspect the darkened preview overlay. The mask must match a genuinely staff-only half; otherwise don't enable it.
4. Select **Save camera area** once. This preserves existing polygons, lines and thresholds. Current shift comparisons restart to prevent data from different areas being mixed.
5. On Live café, **People in guest-facing area** now appears alongside the **full camera count**. On Shift summary, the optional guest-area average and peak appear in a separate section. Automatic Service Alerts use the selected guest-facing area history if configured.

The mask is saved locally for that camera source via the existing zones API/configuration store. Changing camera angles or moving furniture requires checking the mask again. Images, individual roles and track identities are not saved by this setting. Existing archives are preserved.

## Desktop notifications

Notifications are now run at the **App root** rather than only inside the Service Alerts page. After a browser permission opt-in, one notification per active signal may appear while the browser tab remains open, even if the user is viewing Live café or Shift summary. A local-camera connection failure can raise attention; intentionally stopping or pausing remains informational. No background OS service, external push notifications, or cloud service is added.

## Important product constraints

- Field-of-view area exclusion is less sophisticated than dedicated staff counters. In mixed views staff and customers are **not separable**. If an employee enters the guest-facing region, they are counted there; if a customer stands in the staff-only region, they are excluded there.
- Camera frames from a video playing on another monitor prove software plumbing, **not** reliable live café counts.
- The new live counts are measured people *in a selected portion of the picture*, not estimated room occupancy, entries, completed orders or individual visitor tracking.
- Browser notifications may be suppressed by browser/OS Do Not Disturb settings. Run the app over the localhost URL as before and explicitly authorize notifications.
- Privacy/legal notice and permission are necessary. This is an evaluation prototype.

## Acceptance checks

Run `make lint`, `make test`, `make build`, and `make verify-people` on the user's Mac. Test a fixed authorized physical scene with known full-frame counts and different placements in each half. Record false negatives/positives manually. Validate that changes to staff-only region reset shift summaries, and that older observations remain accessible in the historical archive. Verify notification opt-in, no duplicates, and page-switch behavior in an actual browser.

## Relevant prior research

- [Milestone/BriefCam People Counting Best Practices](https://doc.milestonesys.com/briefcam/briefcam-white-papers/2024r2/en/people-counting-best-practices) — viewpoint, occlusion, and area filters affect count reliability.
- [FootfallCam Staff Exclusion Methods](https://www.footfallcam.com/people-counting/knowledge-base/appendix-a-staff-exclusion-tag/) — dedicated paths/areas or separate aids are used for staff exclusion; actual visitors can be excluded unintentionally.
