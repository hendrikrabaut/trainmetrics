function errorText(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${item.loc.at(-1)}: ${item.msg}`)
      .join("; ");
  }

  return detail || "Er ging iets mis";
}

export async function api(path, options = {}) {
  const init = { ...options };

  if (options.json !== undefined) {
    init.method = options.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.json);
    delete init.json;
  }

  let response;

  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("De server is niet bereikbaar");
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) throw new Error(errorText(body?.detail));

  return body;
}
