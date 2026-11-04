export type Mode = "LIVE" | "REPLAY" | "SNAPSHOT" | "OFFLINE";
export type Review = "unreviewed" | "acknowledged" | "false_alarm";
export interface SourceCapabilities {
  continuous_video: boolean;
  snapshot_only: boolean;
  supports_tracking: boolean;
  supports_temporal_events: boolean;
  capture_timestamp_available: boolean;
  source_authorized: boolean;
}
export interface Camera {
  capabilities?: SourceCapabilities;
  id: string;
  name: string;
  mode: Mode;
  region: string;
  provider: string;
  source_type: string;
  source_page: string;
  terms_url: string;
  permission_notes: string;
  permission_checked: string;
  analysis_authorized: boolean;
  redisplay_authorized: boolean;
  enabled: boolean;
  configuration_issues?: string[];
  license_status: string;
  latitude?: number | null;
  longitude?: number | null;
  orientation?: string;
  public_image_url?: string;
}
export interface Zone {
  id: string;
  name: string;
  kind: "monitoring_lane" | "ignore";
  points: [number, number][];
}
export interface FlowLine {
  id: string;
  name: string;
  points: [[number, number], [number, number]];
}
export interface Rules {
  flow_track_maturity_seconds?: number;
  flow_dwell_seconds?: number;
  flow_queue_people?: number;
  flow_queue_seconds?: number;
  flow_motion_threshold?: number;
  flow_slow_fraction?: number;
  flow_capacity?: number;
  flow_crossing_margin?: number;
  flow_crossing_cooldown?: number;
  stationary_seconds: number;
  min_track_age: number;
  motion_threshold: number;
  occupancy_threshold: number;
  occupancy_increase: number;
  baseline_window: number;
  congestion_seconds: number;
  cooldown_seconds: number;
  min_confidence: number;
  target_fps: number;
}
export type StaffOnlyRegion = "none" | "left" | "right" | "top" | "bottom";
export interface ZoneConfig {
  staff_only_region?: StaffOnlyRegion;
  lines?: FlowLine[];
  zones: Zone[];
  rules: Rules;
}
export interface Observation {
  id: string;
  camera_id: string;
  type: "potential_stopped_vehicle" | "congestion_buildup" | "extended_dwell" | "possible_queue_buildup";
  state: "active" | "resolved";
  review_status: Review;
  severity: string;
  started_at: string;
  ended_at: string | null;
  window_started_at?: string;
  zone_id: string;
  zone_name: string;
  track_id: string | null;
  explanation: string;
  source_mode: Mode;
  features: Record<string, unknown>;
  quality_flags: string[];
  evidence_url: string | null;
  rule_parameters: Rules;
  model_version: string;
}
export interface RuleDebug {
  zone_id: string;
  name: string;
  count: number;
  occupancy: number;
  motion: number;
  warming_up: boolean;
  general_stop_suppression: boolean;
  queue_state: string;
  baseline: { occupancy: number; motion: number };
}
export interface SceneHotspot {
  id: string;
  bounds: [number, number, number, number];
  location: string;
  pattern: "longer_stays" | "movement" | "frequent_presence";
  evidence: "strong" | "developing";
  frames_with_people: number;
  visible_now: number;
  presence_share: number;
  observed_seconds?: number;
  presence_percent?: number;
  occupancy_episodes?: number;
}
export interface SceneDiscovery {
  state: "learning" | "ready";
  sampled_frames: number;
  window_seconds: number;
  hotspots: SceneHotspot[];
  disclaimer: string;
}

export interface AutomaticInsights {
  sample_count: number;
  average_visible: number | null;
  peak_visible: number | null;
  visible_trend: "warming_up" | "rising" | "falling" | "steady";
  busiest_image_sector: string | null;
  sector_share: number | null;
  image_midline_crossings: { left_to_right: number; right_to_left: number };
  longest_visible_seconds?: number | null;
  average_track_age_seconds?: number | null;
  active_lingerers?: number;
  service_level?: "learning" | "quiet" | "steady" | "busy" | "rush";
  staff_only_region?: StaffOnlyRegion;
  guest_area_visible?: number | null;
  guest_area_recent?: number[];
  scene_discovery?: SceneDiscovery;
  session_summary?: {
    processed_samples: number;
    average_visible: number | null;
    peak_visible: number | null;
    supported_peak_visible?: number | null;
    peak_possible_outlier?: boolean;
    peak_support_window?: number;
    supported_guest_area_peak?: number | null;
    guest_area_average?: number | null;
    guest_area_peak?: number | null;
    busy_sample_percent: number | null;
    elapsed_seconds: number;
    minute_averages: { minute: number; average: number }[];
  };
  limitations: string;
}
export interface Status {
  view_shift_detected?: boolean;
  control_revision?: number;
  preview_only?: boolean;
  device_released?: boolean;
  continuous_frames_verified?: boolean;
  consecutive_frames_received?: number;
  monitoring_zones_configured?: boolean;
  capabilities?: SourceCapabilities;
  resolution?: number[] | null;
  tracks?: { id: string; label: string; confidence: number; box: number[]; image_plane_motion_per_second: number }[];
  // Held outlines are unverified visual hints, never included in current counts.
  overlay_tracks?: { id: string; confidence: number; box: number[]; held: boolean; held_age_seconds?: number }[];
  weak_person_confirmations?: number;
  detector_input_size?: number | null;
  detail_scan_mode?: "learning" | "scanning" | "performance_limited" | "unavailable" | "inactive";
  detail_scan_additional_candidates?: number;
  detail_scan_duplicate_proposals?: number;
  detail_scan_closeup_candidates?: number;
  camera_id: string;
  mode: Mode;
  state: string;
  model: string;
  device: string;
  device_note?: string | null;
  input_type?: string;
  source_kind?: string;
  source_timestamp?: string | null;
  source_age_seconds?: number | null;
  timestamp_kind?: string;
  next_refresh_estimate?: string | null;
  visible_vehicles?: number | null;
  visible_people?: number | null;
  staff_only_region?: StaffOnlyRegion;
  people_count_history?: { at: string; people: number }[];
  automatic_insights?: AutomaticInsights | null;
  flow?: {
    entries: number;
    exits: number;
    zone_counts: Record<string, number>;
    lines: FlowLine[];
  } | null;
  detection_target?: "vehicle" | "person";
  temporal_rules_enabled?: boolean;
  attribution?: string | null;
  detections?: { box: number[]; label: string; confidence: number }[];
  ai_state: string;
  frame_timestamp: string | null;
  frame_id?: string | null;
  source_image_sha256?: string | null;
  frame_age_seconds: number | null;
  processing_delay_ms: number | null;
  processed_frame_age_seconds: number | null;
  ingest_fps: number;
  preview_fps?: number;
  processed_fps: number;
  inference_ms?: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  dropped_frames: number;
  reconnect_count: number;
  queue_depth: number;
  active_tracks: number;
  session_events: number;
  uptime_seconds: number;
  last_error: string | null;
  quality_flags: string[];
  rule_debug: RuleDebug[];
  evidence_enabled: boolean;
  evidence_error: string | null;
  logs: { at: string; message: string }[];
}
export interface Metric {
  timestamp: string;
  occupancy: number;
  count: number;
  processed_fps: number;
  inference_ms: number;
}
export interface EventPage {
  items: Observation[];
  total: number;
  limit: number;
  offset: number;
}
