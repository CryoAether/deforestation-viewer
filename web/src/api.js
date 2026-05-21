export async function getYears() {
  const res = await fetch("/api/years");
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to load years (${res.status}): ${text}`);
  }
  const json = await res.json();
  return json.years;
}

export async function buildDelta(fromYear, toYear) {
  const res = await fetch("/api/delta", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_year: fromYear, to_year: toYear }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to build delta (${res.status}): ${text}`);
  }

  return await res.json();
}

export async function getBounds(year) {
  const res = await fetch(`/api/bounds/${year}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`getBounds failed (${res.status}): ${text}`);
  }
  return await res.json();
}
