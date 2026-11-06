import { api } from "../api.js";
import { coachDialog } from "../art.js";
import { fields, h, message, number, submitter, table } from "../dom.js";
import { SPORTS, dayLabel, kilometers } from "../format.js";
import { refreshGame } from "../gamification.js";
import { route } from "../navigation.js";
import { ring } from "../ring.js";

// From this share of its lifetime, gear shows it is nearly worn out.
const WEAR_WARNING = 0.85;

const POLAR_RESULTS = {
  gekoppeld: ["Je Polar-account is gekoppeld. Klik op Nu ophalen voor je trainingen.", false],
  geweigerd: ["Het koppelen is niet gelukt of werd geweigerd. Probeer het opnieuw.", true],
  mislukt: ["Polar weigerde de koppeling. Controleer je client-ID en secret, en probeer het opnieuw.", true],
};

async function syncView() {
  const status = await api(`/api/polar/status`);
  const result = POLAR_RESULTS[new URLSearchParams(location.hash.split("?")[1]).get("polar")];
  const output = h("div", { "aria-live": "polite" }, result && message(...result));
  const results = h("div", { "aria-live": "polite" });

  const fetchNow = async (event) => {
    const button = event.currentTarget;
    button.disabled = true;

    try {
      const counts = await api(`/api/polar/sync`, { method: "POST" });

      await route();

      const total = counts.imported + counts.updated + counts.skipped;

      document.getElementById("polar-output")?.replaceChildren(message(
        total
          ? `${counts.imported} nieuw, ${counts.updated} aangevuld, ${counts.skipped} waren er al.`
          : "De koppeling werkt, maar Polar heeft nog geen trainingen voor deze app. Polar geeft alleen trainingen die na het koppelen naar Polar Flow zijn geüpload. Je volgende training komt dus vanzelf door; oudere upload je hieronder als bestand."
      ));
    } catch (error) {
      output.replaceChildren(message(error.message, true));
      button.disabled = false;
    }
  };

  const unlink = async () => {
    if (!confirm("Polar ontkoppelen? Je trainingen blijven staan.")) return;

    await api(`/api/polar/link`, { method: "DELETE" });
    location.hash = "#profiel";
    route();
  };

  output.id = "polar-output";

  let polar;

  if (!status.configured) {
    polar = [
      h("p", {}, "De koppeling is nog niet ingesteld. Maak een gratis API-client aan op ",
        h("a", { href: "https://admin.polaraccesslink.com", target: "_blank", rel: "noreferrer" }, "admin.polaraccesslink.com"),
        " en zet de gegevens in backend/.env. De stappen staan in docs/deployment.md."),
    ];
  } else if (!status.linked) {
    polar = [
      h("p", {}, "Koppel je Polar-account. Daarna komen nieuwe trainingen vanzelf hierheen, inclusief je Running Index."),
      h("a", { class: "button primary", href: `/api/polar/connect` }, "Koppel met Polar"),
    ];
  } else {
    polar = [
      h("p", {}, status.last_sync_at
        ? `Laatst opgehaald: ${dayLabel(status.last_sync_at)} om ${status.last_sync_at.slice(11, 16)}.`
        : "Gekoppeld, maar nog niets opgehaald."),
      h("div", { class: "row" },
        h("button", { class: "primary", type: "button", onclick: fetchNow }, "Nu ophalen"),
        h("button", { class: "small", type: "button", onclick: unlink }, "Ontkoppelen")
      ),
    ];
  }

  return [
    h("section", { class: "card" },
      h("h2", {}, "Polar"),
      output,
      polar,
      h("p", { class: "muted", style: "margin:12px 0 0" },
        "Polar geeft alleen trainingen uit de laatste 30 dagen die na het koppelen zijn geüpload. Oudere trainingen upload je hieronder als bestand.")
    ),
    h("section", { class: "card" },
      h("h2", {}, "Bestanden"),
      h("p", {}, "Upload FIT-, GPX- of TCX-bestanden. Wat je al importeerde, wordt overgeslagen."),
      h("p", { class: "muted" }, "Polar Flow: open een training en exporteer als TCX. Garmin Connect: exporteer het origineel (FIT)."),
      h("form", {
        onsubmit: submitter(async (form) => {
          results.replaceChildren();

          for (const file of form.elements.files.files) {
            const body = new FormData();
            body.append("file", file);

            try {
              const result = await api(`/api/import/`, { method: "POST", body });
              const count = result.imported.length;

              results.append(message(
                `${file.name}: ${count} geïmporteerd${result.skipped ? `, ${result.skipped} overgeslagen` : ""}`
              ));
            } catch (error) {
              results.append(message(`${file.name}: ${error.message}`, true));
            }
          }

          form.reset();
          await refreshGame();
        }),
      },
        h("label", {}, "Bestanden", h("input", {
          name: "files", type: "file", accept: ".fit,.gpx,.tcx", multiple: true, required: true,
        })),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Importeren"))
      )
    ),
    results,
  ];
}

function gearEditor(item) {
  const sportOptions = ["RUNNING", "CYCLING", "SWIMMING", "OTHER"].map((sport) => {
    const option = h("option", { value: sport }, SPORTS[sport]);
    option.selected = item.sport === sport;
    return option;
  });

  const isDefault = h("input", { name: "is_default", type: "checkbox", value: "1" });
  isDefault.checked = item.is_default;

  return h("tr", { class: "gear-edit-row" },
    h("td", { colspan: 3 },
      h("form", {
        class: "gear-edit",
        onsubmit: submitter(async (form) => {
          const values = fields(form);

          await api(`/api/equipment/${item.id}`, {
            method: "PATCH",
            json: {
              name: values.name,
              category: values.category || null,
              brand: values.brand || null,
              model: values.model || null,
              sport: values.sport || null,
              purchase_date: values.purchase_date || null,
              replace_after_km: number(values.replace_after_km) || null,
              is_default: Boolean(values.is_default),
            },
          });

          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", value: item.name, required: true })),
          h("label", {}, "Categorie", h("input", { name: "category", value: item.category ?? "" })),
          h("label", {}, "Merk", h("input", { name: "brand", value: item.brand ?? "" })),
          h("label", {}, "Model", h("input", { name: "model", value: item.model ?? "" })),
          h("label", {}, "Voor sport",
            h("select", { name: "sport" }, h("option", { value: "" }, "Geen"), sportOptions)),
          h("label", {}, "In gebruik sinds", h("input", {
            name: "purchase_date", type: "date", value: item.purchase_date?.slice(0, 10) ?? "",
          })),
          h("label", {}, "Vervangen na (km)", h("input", {
            name: "replace_after_km", type: "number", min: 0, inputmode: "numeric",
            value: item.replace_after_km || "",
          })),
          h("label", { class: "check-field" }, isDefault, "Standaard voor deze sport")
        ),
        h("div", {}, h("button", { class: "primary small", type: "submit" }, "Opslaan"))
      )
    )
  );
}

async function management() {
  const [exercises, equipment] = await Promise.all([
    api("/api/exercises/"),
    api("/api/equipment/"),
  ]);

  const failure = h("div", { "aria-live": "polite" });

  const attempt = async (action) => {
    failure.replaceChildren();

    try {
      await action();
      route();
    } catch (error) {
      failure.replaceChildren(message(error.message, true));
      failure.scrollIntoView({ block: "center" });
    }
  };

  return [
    failure,
    h("section", { class: "card" },
      h("h2", {}, "Oefeningen"),
      h("form", {
        onsubmit: submitter(async (form) => {
          const values = fields(form);

          await api("/api/exercises/", {
            json: { name: values.name, category: values.category || null },
          });

          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", required: true })),
          h("label", {}, "Categorie", h("input", { name: "category", placeholder: "Chest, Back…" }))
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Oefening toevoegen"))
      ),
      exercises.length > 0 && h("div", { style: "margin-top:16px" }, table([
        { label: "Naam", value: (row) => row.name },
        { label: "Categorie", value: (row) => row.category || "–" },
        {
          label: "",
          value: (row) => h("button", {
            class: "danger small",
            type: "button",
            onclick: () => confirm(`${row.name} verwijderen?`)
              && attempt(() => api(`/api/exercises/${row.id}`, { method: "DELETE" })),
          }, "Verwijderen"),
        },
      ], exercises))
    ),
    h("section", { class: "card" },
      h("h2", {}, "Materiaal"),
      h("form", {
        onsubmit: submitter(async (form) => {
          const values = fields(form);

          await api("/api/equipment/", {
            json: {
              name: values.name,
              category: values.category || null,
              brand: values.brand || null,
              model: values.model || null,
              sport: values.sport || null,
              is_default: Boolean(values.is_default),
              replace_after_km: number(values.replace_after_km) || null,
              purchase_date: values.purchase_date || null,
            },
          });

          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", required: true })),
          h("label", {}, "Categorie", h("input", { name: "category", placeholder: "BIKE, WEARABLE…" })),
          h("label", {}, "Merk", h("input", { name: "brand" })),
          h("label", {}, "Model", h("input", { name: "model" })),
          h("label", {}, "Voor sport",
            h("select", { name: "sport" },
              h("option", { value: "" }, "Geen"),
              ["RUNNING", "CYCLING", "SWIMMING", "OTHER"].map((sport) => h("option", { value: sport }, SPORTS[sport])))),
          h("label", {}, "In gebruik sinds", h("input", { name: "purchase_date", type: "date" })),
          h("label", {}, "Vervangen na (km)", h("input", {
            name: "replace_after_km", type: "number", min: 0, inputmode: "numeric", placeholder: "Schoenen: rond 700",
          })),
          h("label", { class: "check-field" },
            h("input", { name: "is_default", type: "checkbox", value: "1" }),
            "Standaard voor deze sport")
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Materiaal toevoegen"))
      ),
      equipment.length > 0 && h("div", { style: "margin-top:16px" }, table([
        {
          label: "Materiaal",
          value: (row) => h("div", {},
            row.name,
            h("div", { class: "muted" },
              [
                row.category,
                row.status === "ACTIVE" ? "In gebruik" : "Afgevoerd",
                row.is_default && row.sport ? `standaard voor ${SPORTS[row.sport].toLowerCase()}` : null,
              ]
                .filter(Boolean)
                .join(" · ")),
            row.needs_replacing && h("div", { class: "gear-warning" }, "Tijd om te vervangen")
          ),
        },
        {
          label: "Gebruik",
          value: (row) => h("div", { class: "gear-use" },
            row.replace_after_km > 0 && ring(row.kilometers, row.replace_after_km, {
              label: `${row.kilometers} van ${row.replace_after_km} km`,
              center: `${Math.round((row.kilometers / row.replace_after_km) * 100)}%`,
              warning: row.kilometers / row.replace_after_km >= WEAR_WARNING,
            }),
            h("span", {}, row.kilometers ? kilometers(row.kilometers * 1000) : `${row.sessions}×`)
          ),
        },
        {
          label: "",
          value: (row) => h("div", { class: "row" },
            h("button", {
              class: "small",
              type: "button",
              onclick: (event) => {
                const row_ = event.currentTarget.closest("tr");
                const open = row_.nextElementSibling?.classList.contains("gear-edit-row");

                if (open) row_.nextElementSibling.remove();
                else row_.after(gearEditor(row));
              },
            }, "Aanpassen"),
            h("button", {
              class: "small",
              type: "button",
              onclick: () => attempt(() => api(`/api/equipment/${row.id}`, {
                method: "PATCH",
                json: { status: row.status === "ACTIVE" ? "RETIRED" : "ACTIVE" },
              })),
            }, row.status === "ACTIVE" ? "Afvoeren" : "Terugzetten"),
            h("button", {
              class: "danger small",
              type: "button",
              onclick: () => confirm(`${row.name} verwijderen?`)
                && attempt(() => api(`/api/equipment/${row.id}`, { method: "DELETE" })),
            }, "Verwijderen")
          ),
        },
      ], equipment))
    ),
  ];
}

export async function profileView() {
  const [sync, manage] = await Promise.all([syncView(), management()]);

  return [
    h("h1", {}, "Profiel"),
    sync,
    manage,
    h("p", { class: "muted" },
      "Pictogrammen: ",
      h("a", { href: "https://phosphoricons.com", target: "_blank", rel: "noreferrer" }, "Phosphor"),
      " (MIT). Beloningen: ",
      h("a", { href: "https://github.com/microsoft/fluentui-emoji", target: "_blank", rel: "noreferrer" }, "Fluent Emoji"),
      " van Microsoft (MIT) en ",
      h("a", { href: "https://googlefonts.github.io/noto-emoji-animation/", target: "_blank", rel: "noreferrer" }, "Noto Animated Emoji"),
      " van Google (",
      h("a", { href: "https://creativecommons.org/licenses/by/4.0/", target: "_blank", rel: "noreferrer" }, "CC BY 4.0"),
      "). Kaart: ",
      h("a", { href: "https://leafletjs.com", target: "_blank", rel: "noreferrer" }, "Leaflet"),
      " en © ",
      h("a", { href: "https://www.openstreetmap.org/copyright", target: "_blank", rel: "noreferrer" }, "OpenStreetMap"),
      "-bijdragers."),
  ];
}

export function setupView() {
  return [
    coachDialog("Nieuw gezicht. Hoe heet je? En ga niet zitten, we zijn er nog niet.").element,
    h("section", { class: "card" },
      h("form", {
        onsubmit: submitter(async (form) => {
          await api("/api/profile/", { json: fields(form) });
          location.hash = "#vandaag";
          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", required: true })),
          h("label", {}, "E-mail", h("input", { name: "email", type: "email", required: true }))
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Beginnen"))
      )
    ),
  ];
}
