"""ByteTrack multi-object tracker (Roboflow `trackers`): stable, anonymous IDs per person."""
import supervision as sv
from trackers import ByteTrackTracker


class PersonTracker:
    def __init__(self, fps: float):
        self._bt = ByteTrackTracker(
            lost_track_buffer=45,  # ~1.5 s of occlusion before an ID is dropped
            frame_rate=fps,
            track_activation_threshold=0.5,
            minimum_consecutive_frames=2,  # ignore single-frame false positives
            high_conf_det_threshold=0.5,
        )

    def update(self, detections: sv.Detections, ts: float) -> sv.Detections:
        # `ts` lets the Kalman filter account for frames skipped when inference lags.
        tracked = self._bt.update(detections, timestamp=ts)
        return tracked[tracked.tracker_id != -1]
