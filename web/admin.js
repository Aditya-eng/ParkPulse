// City dashboard for JMC / JSCL: KPIs, forecast, hourly heatmap, alerts and hotspots.
(() => {
  const css = getComputedStyle(document.documentElement);
  const C = (n) => css.getPropertyValue(n).trim();
  let zones = [];
  let chart;

  async function kpis() {
    const k = await PP.get("/api/kpis");
    document.getElementById("k-free").textContent = k.free.toLocaleString("en-IN");
    document.getElementById("k-occ").textContent = `${Math.round(k.occupancy * 100)}%`;
    document.getElementById("k-alerts").textContent = k.open_alerts;
    document.getElementById("k-full").textContent = k.zones_full;
    document.getElementById("k-time").textContent = PP.time(k.updated_at);
  }

  async function forecast(zoneId) {
    const [f, z] = await Promise.all([PP.get(`/api/forecast/${zoneId}`), PP.get(`/api/zones/${zoneId}`)]);
    const labels = ["Now", ...f.points.map((p) => PP.time(p.at))];
    const data = [Math.round(z.occupancy * 100), ...f.points.map((p) => Math.round(p.occupancy * 100))];
    document.getElementById("model-q").textContent =
      f.model_mae != null ? `Back-test error ${(f.model_mae * 100).toFixed(1)} pts vs ${(f.baseline_mae * 100).toFixed(1)} pts for "same hour last week"` : "";
    const cfg = {
      type: "line",
      data: { labels, datasets: [
        { label: "Occupancy %", data, borderColor: C("--tawi"), backgroundColor: C("--tawi-wash"), fill: true, tension: 0.35, pointRadius: 4, borderWidth: 3 },
        { label: "Full (95%)", data: labels.map(() => 95), borderColor: C("--sindoor"), borderDash: [6, 6], pointRadius: 0, borderWidth: 2 },
      ] },
      options: {
        maintainAspectRatio: false, animation: false,
        scales: { y: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` }, grid: { color: "#eef1ee" } }, x: { grid: { display: false } } },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 14 } } },
      },
    };
    if (chart) { chart.data = cfg.data; chart.update(); }
    else chart = new Chart(document.getElementById("fc-chart"), cfg);
  }

  function heat(a) {
    const el = document.getElementById("heat");
    const hours = [...Array(24).keys()];
    let html = `<span></span>${hours.map((h) => `<span class="h">${h % 3 === 0 ? h : ""}</span>`).join("")}`;
    zones.forEach((z) => {
      const row = a.hourly_profile[z.id] || [];
      html += `<span class="zn" title="${z.name}">${z.name}</span>`;
      html += row.map((v, h) => {
        const tone = v > 0.85 ? C("--sindoor") : v > 0.65 ? C("--mustard") : C("--tawi");
        const alpha = Math.max(0.12, Math.min(1, v));
        return `<span class="c" title="${h}:00 · ${Math.round(v * 100)}%" style="background:${tone};opacity:${alpha.toFixed(2)}"></span>`;
      }).join("");
    });
    el.innerHTML = html;
  }

  function hotspots(a) {
    const max = Math.max(...a.hotspots.map((h) => h.violations_14d), 1);
    document.getElementById("hotspots").innerHTML = a.hotspots.map((h) => `
      <div class="bar-row"><span>${h.name}</span><b>${h.violations_14d}</b>
        <div class="bar"><i style="width:${(h.violations_14d / max) * 100}%"></i></div></div>`).join("");
    document.getElementById("leak").textContent = `₹${a.estimated_weekly_revenue_leakage_inr.toLocaleString("en-IN")}`;
    document.getElementById("leak-note").textContent = `Assumes ${a.leakage_assumption}. Replace with JMC billing data in a pilot.`;
  }

  async function alerts() {
    const list = await PP.get("/api/alerts");
    document.getElementById("alerts").innerHTML = list.slice(0, 8).map((a) => `
      <tr><td>${PP.time(a.detected_at)}</td><td>${a.segment_name}</td><td>${a.vehicle_class}</td>
      <td>${a.dwell_minutes} min</td><td><span class="tag ${a.status}">${a.status === "open" ? "New" : "Police notified"}</span></td></tr>`).join("")
      || `<tr><td colspan="5">No open alerts. Junctions are clear.</td></tr>`;
  }

  async function init() {
    zones = await PP.get("/api/zones");
    const sel = document.getElementById("zone-select");
    sel.innerHTML = zones.map((z) => `<option value="${z.id}">${z.name}</option>`).join("");
    sel.addEventListener("change", () => forecast(sel.value));
    const a = await PP.get("/api/analytics");
    heat(a); hotspots(a);
    await Promise.all([kpis(), forecast(zones[0].id), alerts()]);
    setInterval(() => { kpis(); alerts(); }, 15000);
  }
  init();
})();
