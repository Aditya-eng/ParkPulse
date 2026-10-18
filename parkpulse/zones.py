"""Parking zones used by the prototype.

Coordinates are approximate and capacities are illustrative. They are demo values
for a pitch prototype, not survey data from Jammu Municipal Corporation. Replace
them with JMC / JSCL records before any pilot.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    kind: str  # "lot" (off-street) or "street" (on-street bays)
    lat: float
    lon: float
    capacity: int
    hourly_fee: int  # INR, illustrative
    market_area: bool = False
    near_transit: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


ZONES: tuple[Zone, ...] = (
    Zone(
        id="raghunath-bazaar",
        name="Raghunath Bazaar MC Parking",
        kind="lot",
        lat=32.7291,
        lon=74.8638,
        capacity=180,
        hourly_fee=20,
        market_area=True,
        aliases=("raghunath", "raghunath bazar", "रघुनाथ", "रघुनाथ बाजार", "رگھوناتھ"),
    ),
    Zone(
        id="residency-road",
        name="Residency Road (City Chowk) bays",
        kind="street",
        lat=32.7268,
        lon=74.8594,
        capacity=90,
        hourly_fee=15,
        market_area=True,
        aliases=("residency", "residency road", "city chowk", "रेजीडेंसी", "सिटी चौक", "ریزیڈنسی"),
    ),
    Zone(
        id="gandhi-nagar",
        name="Gandhi Nagar Gole Market lot",
        kind="lot",
        lat=32.7067,
        lon=74.8612,
        capacity=140,
        hourly_fee=20,
        market_area=True,
        aliases=("gandhi nagar", "gole market", "गांधी नगर", "गोल मार्केट", "گاندھی نگر"),
    ),
    Zone(
        id="bahu-plaza",
        name="Bahu Plaza parking",
        kind="lot",
        lat=32.7108,
        lon=74.8745,
        capacity=220,
        hourly_fee=20,
        market_area=True,
        aliases=("bahu plaza", "bahu", "बाहु प्लाज़ा", "बाहु प्लाजा", "باہو پلازہ"),
    ),
    Zone(
        id="railway-station",
        name="Jammu Tawi Railway Station parking",
        kind="lot",
        lat=32.7080,
        lon=74.8790,
        capacity=260,
        hourly_fee=30,
        near_transit=True,
        aliases=("railway", "station", "jammu tawi", "रेलवे", "स्टेशन", "ریلوے"),
    ),
    Zone(
        id="bus-stand",
        name="General Bus Stand multi-tier",
        kind="lot",
        lat=32.7330,
        lon=74.8652,
        capacity=300,
        hourly_fee=20,
        near_transit=True,
        aliases=("bus stand", "bus adda", "बस स्टैंड", "बस अड्डा", "بس اسٹینڈ"),
    ),
)

ZONES_BY_ID: dict[str, Zone] = {z.id: z for z in ZONES}


# No-parking corridors watched for illegal parking (approximate polylines, demo only).
NO_PARKING_SEGMENTS: tuple[dict, ...] = (
    {"id": "np-city-chowk", "name": "City Chowk junction", "lat": 32.7276, "lon": 74.8606},
    {"id": "np-raghunath-gate", "name": "Raghunath Bazaar entry", "lat": 32.7297, "lon": 74.8650},
    {"id": "np-gole-market", "name": "Gole Market crossing", "lat": 32.7072, "lon": 74.8625},
    {"id": "np-station-road", "name": "Station approach road", "lat": 32.7090, "lon": 74.8775},
)
