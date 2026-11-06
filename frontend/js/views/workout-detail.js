import { api } from "../api.js";
import { seriesChart } from "../charts.js";
import { fields, h, message, submitter, table } from "../dom.js";
import { ZONE_NAMES, clock, decimal, duration, lengthLabel, pace } from "../format.js";
import { route } from "../navigation.js";

const MOST_POINTS = 400;

function thinned(rows) {
  const stride = Math.ceil(rows.length / MOST_POINTS);

  return stride > 1 ? rows.filter((_, index) => index % stride === 0) : rows;
}

function detailCharts(detail, sport) {
  const series = detail.series;
  const interval = detail.interval_seconds;
  const length = (series.heart_rate ?? series.speed ?? series.distance ?? []).length;

  if (length < 2) return [];

  // Over distance where there is one, so that two runs line up by place.
  const hasDistance = (series.distance ?? []).at(-1) > 100;

  const rows = thinned(Array.from({ length }, (_, index) => ({
    x: hasDistance ? series.distance[index] / 1000 : (index * interval) / 60,
    heart_rate: series.heart_rate?.[index] ?? null,
    speed: series.speed?.[index] ?? null,
    altitude: series.altitude?.[index] ?? null,
  })));

  const xFormat = (value) => (hasDistance ? `${decimal(value)} km` : `${decimal(value, 0)} min`);
  const speedFormat = (value) => (value ? pace({ activity_type: sport, average_speed: value }) : "–");

  const chart = (title, field, format, label) => {
    if (!rows.some((row) => row[field] !== null)) return null;

    return seriesChart(title, rows, {
      x: (row) => row.x,
      xFormat,
      format,
      series: [{ label, color: "#6E0D25", value: (row) => row[field] }],
      columns: [
        { label: hasDistance ? "Afstand" : "Tijd", value: (row) => xFormat(row.x) },
        { label, value: (row) => (row[field] === null ? "–" : format(row[field])) },
      ],
    });
  };

  return [
    chart("Hartslag", "heart_rate", (value) => `${decimal(value, 0)} bpm`, "Hartslag"),
    chart(sport === "CYCLING" ? "Snelheid" : "Tempo", "speed", speedFormat, "Snelheid"),
    chart("Hoogte", "altitude", (value) => `${decimal(value, 0)} m`, "Hoogte"),
  ].filter(Boolean);
}

function splitsTable(detail, sport) {
  return table([
    { label: "#", value: (split) => String(split.number) },
    { label: "Afstand", value: (split) => lengthLabel(split.meters) },
    { label: "Tijd", value: (split) => clock(split.seconds) },
    {
      label: sport === "CYCLING" ? "Snelheid" : "Tempo",
      value: (split) => pace({ activity_type: sport, average_speed: split.meters / split.seconds }),
    },
    { label: "Hartslag", value: (split) => (split.heart_rate ? `${split.heart_rate} bpm` : "–") },
    { label: "Klim", value: (split) => (split.ascent === null ? "–" : `${decimal(split.ascent, 0)} m`) },
  ], detail.splits);
}

export function zoneBars(zones, total = zones.reduce((sum, zone) => sum + zone.seconds, 0)) {
  return h("div", { class: "zone-bars" }, zones.map((zone, index) =>
    h("div", { class: "zone-row" },
      h("span", {}, h("b", {}, `Z${index + 1}`), ` ${ZONE_NAMES[index]}`,
        zone.lower ? h("small", {}, ` ${decimal(zone.lower, 0)}–${decimal(zone.upper, 0)} bpm`) : null),
      h("span", { class: "zone-track" },
        h("i", { class: `zone-${index + 1}`, style: `width:${total ? (zone.seconds / total) * 100 : 0}%` })),
      h("span", { class: "zone-time" }, zone.seconds ? duration(zone.seconds) : "–")
    )
  ));
}

function gearPicker(workout, gear) {
  const sport = workout.endurance_activity?.activity_type;
  const options = gear.filter((item) => item.sport === sport && item.status === "ACTIVE");

  if (!options.length) return null;

  const linked = options.find((item) => item.linked_workout_ids.includes(workout.id));
  const usual = options.find((item) => item.is_default);

  const select = h("select", {
    "aria-label": "Materiaal",
    onchange: async (event) => {
      const chosen = Number(event.target.value);

      try {
        if (linked) {
          await api(`/api/workouts/${workout.id}/equipment/${linked.id}`, { method: "DELETE" });
        }

        if (chosen) {
          await api(`/api/workouts/${workout.id}/equipment/${chosen}`, { method: "PUT" });
        }

        route();
      } catch (error) {
        select.after(message(error.message, true));
      }
    },
  },
    h("option", { value: "" }, usual ? `Standaard: ${usual.name}` : "Geen"),
    options.map((item) => {
      const option = h("option", { value: item.id }, item.name);
      option.selected = item.id === linked?.id;
      return option;
    })
  );

  return h("label", { class: "gear-picker" }, "Materiaal", select);
}

export async function workoutDetail(workout) {
  const sport = workout.endurance_activity?.activity_type ?? "STRENGTH";

  const [detail, gear] = await Promise.all([
    api(`/api/workouts/${workout.id}/detail`),
    workout.endurance_activity ? api("/api/equipment/") : [],
  ]);

  const parts = [gearPicker(workout, gear), ...detailCharts(detail, sport)];

  if (detail.zones.some((zone) => zone.seconds)) {
    parts.push(h("div", {}, h("h3", {}, "Hartslagzones"), zoneBars(detail.zones)));
  }

  if (detail.splits.length > 1) {
    parts.push(h("div", {}, h("h3", {}, "Splits"), splitsTable(detail, sport)));
  }

  if (detail.best_efforts.length) {
    parts.push(h("p", { class: "muted" },
      "Snelste stukken: ",
      detail.best_efforts.map((effort) => `${lengthLabel(effort.meters)} in ${clock(effort.seconds)}`).join(" · ")));
  }

  if (detail.segments.length) {
    parts.push(h("p", { class: "muted" },
      "Segmenten: ",
      detail.segments.map((segment) => `${segment.name} in ${clock(segment.seconds)}`).join(" · ")));
  }

  return parts.filter(Boolean);
}

// Lets someone tap two places on a route to make a segment of what lies between.
export function segmentTool(map, workout, L) {
  const status = h("p", { class: "muted", style: "margin:0" }, "Tik op de kaart op het begin van het stuk.");
  const form = h("div", {});
  const points = [];
  const markers = [];

  const reset = () => {
    points.length = 0;
    markers.splice(0).forEach((marker) => marker.remove());
    form.replaceChildren();
    status.textContent = "Tik op de kaart op het begin van het stuk.";
  };

  map.on("click", (event) => {
    if (points.length === 2) reset();

    points.push([event.latlng.lat, event.latlng.lng]);
    markers.push(L.circleMarker(event.latlng, {
      radius: 7, color: "#FFFFFF", weight: 2, fillColor: "#2F7FB5", fillOpacity: 1,
    }).addTo(map));

    if (points.length === 1) {
      status.textContent = "Tik nu op het einde.";
      return;
    }

    status.textContent = "De punten springen naar de dichtstbijzijnde plek op je route.";

    form.replaceChildren(h("form", {
      onsubmit: submitter(async (element) => {
        const created = await api("/api/segments/", {
          json: {
            name: fields(element).name,
            workout_id: workout.id,
            start: points[0],
            end: points[1],
          },
        });

        form.replaceChildren(message(
          `${created.name}: ${lengthLabel(created.length_meters)}, gevonden in ${created.count} ${created.count === 1 ? "training" : "trainingen"}.`
        ));
      }),
    },
      h("label", {}, "Naam van het segment", h("input", { name: "name", required: true, maxlength: 100 })),
      h("div", {}, h("button", { class: "primary small", type: "submit" }, "Segment opslaan"))
    ));
  });

  return h("div", { class: "segment-tool" }, status, form);
}
