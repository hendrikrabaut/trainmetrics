export const decimal = (value, digits = 1) =>
  value.toLocaleString("nl-BE", { maximumFractionDigits: digits });

export const kilometers = (meters) => `${decimal(meters / 1000)} km`;

export const percentage = (part, whole) => `${Math.min(100, (part / whole) * 100)}%`;

export function duration(seconds) {
  if (!seconds) return "–";

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);

  return hours ? `${hours} u ${String(minutes).padStart(2, "0")}` : `${minutes} min`;
}

export const dayLabel = (value, options = { day: "numeric", month: "short", year: "numeric" }) =>
  new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("nl-BE", options);

export const shortDay = (value) => dayLabel(value, { day: "numeric", month: "short" });

export function localNow() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

export function pace(activity) {
  const speed = activity.average_speed;

  if (!speed) return null;

  const clock = (seconds) => {
    const whole = Math.round(seconds);
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  };

  if (activity.activity_type === "RUNNING") return `${clock(1000 / speed)} /km`;
  if (activity.activity_type === "SWIMMING") return `${clock(100 / speed)} /100 m`;

  return `${decimal(speed * 3.6)} km/u`;
}

export function clock(seconds) {
  const whole = Math.round(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = String(whole % 60).padStart(2, "0");

  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${rest}`
    : `${minutes}:${rest}`;
}

export const SPORTS = {
  RUNNING: "Lopen",
  CYCLING: "Fietsen",
  SWIMMING: "Zwemmen",
  OTHER: "Overig",
  STRENGTH: "Kracht",
};

export function isoDay(date) {
  const local = new Date(date);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  return local.toISOString().slice(0, 10);
}

export function formLabel(form) {
  if (form > 5) return "fris";
  if (form < -10) return "moe";
  return "in balans";
}

export function lengthLabel(meters) {
  if (meters < 1000) return `${decimal(meters, 0)} m`;
  if (Math.abs(meters - 21098) < 1) return "Halve marathon";

  return `${decimal(meters / 1000, 0)} km`;
}

export const ZONE_NAMES = ["Zeer licht", "Licht", "Matig", "Zwaar", "Maximaal"];

export const PHASE_LABELS = {
  BASE: "Basis",
  BUILD: "Opbouw",
  PEAK: "Piek",
  TAPER: "Afbouw",
  RACE: "Wedstrijd",
};

export const RACE_GOALS = {
  "5K": "5 km",
  "5MI": "5 mijl",
  "10K": "10 km",
  "10MI": "10 mijl",
  HALF: "Halve marathon",
  MARATHON: "Marathon",
  TRI_QUARTER: "1/4 triatlon",
  TRI_HALF: "1/2 triatlon",
  TRIATHLON: "Triatlon",
};

export const PLAN_GOALS = {
  ...RACE_GOALS,
  STRENGTH: "Kracht",
  FITNESS: "Algemene conditie",
};
