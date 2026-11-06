import { h } from "../dom.js";

const WEEKDAY_NAMES = ["ma", "di", "wo", "do", "vr", "za", "zo"];

export function weekdayPicker(selected) {
  return h("fieldset", { class: "day-picker" },
    h("legend", {}, "Op welke dagen train je? Het aantal dagen bepaalt het aantal trainingen per week."),
    WEEKDAY_NAMES.map((name, index) => {
      const input = h("input", { type: "checkbox", name: "day", value: index, "aria-label": name });
      input.checked = selected.includes(index);

      return h("label", {}, input, h("span", { "aria-hidden": "true" }, name));
    })
  );
}

export function pickedDays(form) {
  return [...form.querySelectorAll("input[name=day]:checked")].map((input) => Number(input.value));
}
