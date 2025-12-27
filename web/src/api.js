export async function getYears() {
  const res = await fetch("/api/years");
  if (!res.ok) throw new Error("Failed to load years");
  const json = await res.json();
  return json.years;
}

export async function buildDelta(fromYear, toYear) {
  const res = await fetch("/api/delta", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_year: fromYear, to_year: toYear }),
  });
  if (!res.ok) throw new Error("Failed to build delta");
  return await res.json();
  
}

export async function getBounds(year) {
  const r = await fetch(`/api/bounds/${year}`);
  if (!r.ok) throw new Error(`getBounds failed: ${r.status}`);
  return r.json();
}
