# Privacy by design

- **No facial recognition, no biometrics.** The system detects anonymous body boxes and gives
  them ephemeral track IDs that are discarded when the person leaves the frame.
- **Nothing identifiable is stored.** SQLite holds only numbers (counts, occupancy, wait time)
  and alert events. No frames, no crops, no IDs. Retention is configurable
  (`retention_hours` in `sources.yaml`, default 24 h).
- **On-premise.** Inference runs locally; no video leaves the machine.
- **Exports carry the same numbers.** A CSV or PDF report is an aggregate of those stored
  rows — counts, occupancy, wait times and alerts over a period — and can contain nothing
  the database does not already hold.
- **Blur toggle.** Every detected person can be blurred in the live view.

Before any real deployment: inform visitors with signage, run a Data Protection Impact
Assessment (DPIA), and get a legal review for the specific site. This POC does not claim
compliance with any particular regulation on its own.
