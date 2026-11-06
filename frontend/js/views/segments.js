import { api } from "../api.js";
import { drawRoutes } from "../art.js";
import { h, message } from "../dom.js";
import { SPORTS, clock, dayLabel, lengthLabel, pace } from "../format.js";
import { route } from "../navigation.js";

export async function segmentsPanel() {
  const segments = await api("/api/segments/");

  const remove = async (segment) => {
    if (!confirm(`Segment ${segment.name} verwijderen?`)) return;

    await api(`/api/segments/${segment.id}`, { method: "DELETE" });
    route();
  };

  return h("section", { class: "card" },
    h("h2", {}, "Segmenten"),
    segments.length === 0 && h("p", { class: "muted" },
      "Open een training met een route, toon de kaart en tik op het begin en einde van een stuk, zoals je vaste klim."),
    segments.map((segment) => {
      const mapSlot = h("div", {});
      const speed = (seconds) => pace({
        activity_type: segment.sport,
        average_speed: segment.length_meters / seconds,
      });

      return h("details", { class: "segment" },
        h("summary", {},
          h("strong", {}, segment.name),
          ` · ${SPORTS[segment.sport]} · ${lengthLabel(segment.length_meters)} · `,
          segment.best_seconds
            ? `beste ${clock(segment.best_seconds)} (${segment.count}×)`
            : "nog niet gereden"),
        segment.efforts.length > 0 && h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {},
            h("th", {}, "#"), h("th", {}, "Datum"), h("th", {}, "Tijd"), h("th", {}, "Tempo"))),
          h("tbody", {}, segment.efforts.map((effort, index) =>
            h("tr", {},
              h("td", {}, String(index + 1)),
              h("td", {}, dayLabel(effort.date)),
              h("td", {}, clock(effort.seconds)),
              h("td", {}, speed(effort.seconds)))
          ))
        )),
        h("p", { class: "muted" }, "Tijden kloppen op ongeveer 5 seconden, omdat de app elke 5 seconden een punt bewaart."),
        mapSlot,
        h("div", { class: "row" },
          h("button", {
            class: "small",
            type: "button",
            onclick: async () => {
              const element = h("div", { class: "route-map" });
              mapSlot.replaceChildren(element);

              try {
                await drawRoutes(element, [{ points: segment.points }], { markEnds: true });
              } catch (error) {
                mapSlot.replaceChildren(message(error.message, true));
              }
            },
          }, "Toon op kaart"),
          h("button", { class: "danger small", type: "button", onclick: () => remove(segment) }, "Verwijderen")
        )
      );
    })
  );
}
