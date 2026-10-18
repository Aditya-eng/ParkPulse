// Shared helpers for the citizen and admin views.
const PP = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${path} returned ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${path} returned ${r.status}`);
    return r.json();
  },
  time(iso) {
    return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  },
  trendLabel: { filling: "Filling up", emptying: "Freeing up", steady: "Steady" },

  // Schematic Tawi river so the map still reads when map tiles are offline.
  tawi: [[32.684, 74.915], [32.694, 74.900], [32.703, 74.889], [32.711, 74.877], [32.718, 74.866],
         [32.723, 74.856], [32.728, 74.846], [32.733, 74.834], [32.739, 74.822]],

  baseMap(el, center = [32.7195, 74.8665], zoom = 14) {
    const map = L.map(el, { zoomControl: true, attributionControl: true }).setView(center, zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    L.polyline(PP.tawi, { color: "#5aa6c8", weight: 14, opacity: 0.55, lineCap: "round" }).addTo(map);
    L.marker([32.7165, 74.8705], {
      interactive: false,
      icon: L.divIcon({ className: "river-label", html: "Tawi river", iconSize: [90, 16] }),
    }).addTo(map);
    // Area names help orientation when tiles cannot load (offline demos).
    [["Old City", 32.7312, 74.8585], ["Gandhi Nagar", 32.7025, 74.8570], ["Trikuta Nagar", 32.6985, 74.8835]]
      .forEach(([name, lat, lon]) => L.marker([lat, lon], { interactive: false,
        icon: L.divIcon({ className: "area-label", html: name, iconSize: [110, 18] }) }).addTo(map));
    return map;
  },
};
