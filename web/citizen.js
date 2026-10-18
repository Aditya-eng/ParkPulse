// Citizen view: live map, availability rail and WhatsApp bot preview.
(() => {
  const map = PP.baseMap("map");
  const markers = {};
  const list = document.getElementById("zones");
  const updated = document.getElementById("updated");
  let active = null;
  let fitted = false;
  const labelSide = { "bus-stand": "top", "raghunath-bazaar": "right", "residency-road": "left" };

  function bayStrip(z) {
    const ticks = Math.max(8, Math.round(z.capacity / 10));
    const taken = Math.round(ticks * z.occupancy);
    return `<div class="bays" aria-hidden="true">${Array.from({ length: ticks }, (_, i) =>
      `<span class="bay${i < taken ? " taken" : ""}"></span>`).join("")}</div>`;
  }

  function render(zones) {
    list.innerHTML = zones
      .sort((a, b) => b.free - a.free)
      .map((z) => `
        <li class="zone${z.id === active ? " active" : ""}" data-id="${z.id}" data-status="${z.status}" tabindex="0">
          <div class="zone-top">
            <span class="zone-name">${z.name}</span>
            <span class="zone-free">${z.free}<small>of ${z.capacity} free</small></span>
          </div>
          <div class="zone-meta">₹${z.hourly_fee}/hr · ${z.kind === "lot" ? "Off-street lot" : "On-street bays"}
            ${z.trend_3h ? ` · <span class="trend">${PP.trendLabel[z.trend_3h]} in next 3 h</span>` : ""}</div>
          ${bayStrip(z)}
        </li>`)
      .join("");

    zones.forEach((z) => {
      const icon = L.divIcon({ className: "", html: `<div class="pin ${z.status}">${z.free}</div>`, iconSize: [46, 46], iconAnchor: [23, 23] });
      const popup = `<strong>${z.name}</strong><br>${z.free} of ${z.capacity} free · ₹${z.hourly_fee}/hr<br><a href="${z.directions}" target="_blank" rel="noopener">Get directions</a>`;
      if (markers[z.id]) markers[z.id].setIcon(icon).setPopupContent(popup);
      else markers[z.id] = L.marker([z.lat, z.lon], { icon, title: z.name }).bindPopup(popup)
        .bindTooltip(z.name.split(" (")[0].replace(/ (MC Parking|parking|lot|bays|multi-tier)$/i, ""),
          { permanent: window.innerWidth >= 640, direction: labelSide[z.id] || "bottom",
            offset: { top: [0, -24], right: [24, 0], left: [-24, 0] }[labelSide[z.id]] || [0, 24], className: "pin-label" })
        .addTo(map);
    });
    if (!fitted && zones.length) {
      map.fitBounds(L.latLngBounds(zones.map((z) => [z.lat, z.lon])), { padding: [70, 70] });
      fitted = true;
    }
    if (zones[0]) updated.textContent = `Updated ${PP.time(zones[0].updated_at)} · counts refresh every 15 seconds`;
  }

  async function refresh() {
    try { render(await PP.get("/api/zones")); }
    catch (e) { updated.textContent = "Live counts are unavailable. Retrying in 15 seconds."; }
  }

  async function drawAlerts() {
    const alerts = await PP.get("/api/alerts");
    alerts.filter((a) => a.status === "open").forEach((a) => {
      L.marker([a.lat, a.lon], { icon: L.divIcon({ className: "", html: '<div class="np-pin"></div>', iconSize: [16, 16] }) })
        .bindPopup(`No-parking violation at ${a.segment_name}<br>${a.vehicle_class}, parked ${a.dwell_minutes} min`)
        .addTo(map);
    });
  }

  list.addEventListener("click", (e) => {
    const li = e.target.closest(".zone");
    if (!li) return;
    active = li.dataset.id;
    const m = markers[active];
    map.flyTo(m.getLatLng(), 16, { duration: 0.6 });
    m.openPopup();
    list.querySelectorAll(".zone").forEach((n) => n.classList.toggle("active", n.dataset.id === active));
  });
  list.addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.click(); });

  // ---- chat
  const log = document.getElementById("chat-log");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");

  function bubble(text, who, lang) {
    const div = document.createElement("div");
    div.className = `msg ${who}`;
    if (lang) div.lang = lang;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  const sessionId = `web-${Math.random().toString(36).slice(2, 10)}`;

  async function send(payload, shown) {
    payload = { ...payload, session_id: sessionId };
    bubble(shown, "me", /[؀-ۿ]/.test(shown) ? "ur" : undefined);
    try {
      const r = await PP.post("/api/chat", payload);
      bubble(r.reply, "bot", r.lang === "ur" ? "ur" : r.lang);
    } catch (e) {
      bubble("The bot is unreachable right now. Check that the server is running.", "bot");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    send({ text }, text);
  });
  document.getElementById("chips").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.loc) {
      const [lat, lon] = b.dataset.loc.split(",").map(Number);
      send({ lat, lon }, "📍 Location shared");
    } else send({ text: b.dataset.q }, b.dataset.q);
  });

  send({ text: "hi" }, "hi");
  refresh();
  drawAlerts();
  setInterval(refresh, 15000);
})();
