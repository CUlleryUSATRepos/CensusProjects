from pathlib import Path
import csv
import json
import zipfile
import urllib.request
import shutil

import shapefile


ACS_YEAR = 2024
PA_STATE_FIPS = "42"
BUCKS_COUNTY_FIPS = "017"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"

DOCS_DIR = PROJECT_ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "census_boundaries"

DOCS_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

MUNICIPAL_CSV = OUTPUT_DIR / "pa_municipal_income_rankings.csv"

BOUNDARY_ZIP_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_42_cousub_500k.zip"
BOUNDARY_ZIP = DATA_RAW_DIR / "cb_2024_42_cousub_500k.zip"
BOUNDARY_DIR = DATA_RAW_DIR / "cb_2024_42_cousub_500k"

DATABASE_JSON = ASSETS_DIR / "wealthiest_towns.json"
PA_GEOJSON = ASSETS_DIR / "wealthiest_towns_pa.geojson"
BUCKS_GEOJSON = ASSETS_DIR / "wealthiest_towns_bucks.geojson"


def parse_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except ValueError:
        return None


def parse_int(value):
    try:
        if value in ("", None):
            return None
        return int(float(value))
    except ValueError:
        return None


def money(value):
    if value is None:
        return "Not available"
    return f"${value:,.0f}"


def pct(value):
    if value is None:
        return "Not available"
    return f"{value:.1f}%"


def load_municipal_records():
    records = []

    with MUNICIPAL_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            record = {
                "statewide_rank": parse_int(row.get("state_rank")),
                "municipality": row.get("municipality"),
                "county": row.get("county"),
                "households_200k_plus_pct": parse_float(row.get("pct_200k_plus")),
                "households_200k_plus_moe": parse_float(row.get("pct_200k_plus_moe")),
                "median_household_income": parse_float(row.get("median_income")),
                "median_household_income_moe": parse_float(row.get("median_income_moe")),
                "median_household_income_low": parse_float(row.get("median_income_low")),
                "median_household_income_high": parse_float(row.get("median_income_high")),
                "state_fips": str(row.get("state_fips", "")).zfill(2),
                "county_fips": str(row.get("county_fips", "")).zfill(3),
                "county_subdivision_fips": str(row.get("county_subdivision_fips", "")).zfill(5),
            }

            record["geoid"] = (
                record["state_fips"]
                + record["county_fips"]
                + record["county_subdivision_fips"]
            )

            record["households_200k_plus_display"] = pct(record["households_200k_plus_pct"])
            record["median_household_income_display"] = money(record["median_household_income"])
            record["median_household_income_range_display"] = (
                f"{money(record['median_household_income_low'])} to "
                f"{money(record['median_household_income_high'])}"
            )

            records.append(record)

    records = sorted(records, key=lambda x: x["statewide_rank"] or 999999)
    return records


def write_database_json(records):
    DATABASE_JSON.write_text(json.dumps(records, indent=2), encoding="utf-8")


def download_boundaries():
    if BOUNDARY_DIR.exists() and any(BOUNDARY_DIR.glob("*.shp")):
        print("Boundary shapefile already exists.")
        return

    if not BOUNDARY_ZIP.exists():
        print(f"Downloading Census boundary file: {BOUNDARY_ZIP_URL}")
        urllib.request.urlretrieve(BOUNDARY_ZIP_URL, BOUNDARY_ZIP)

    if BOUNDARY_DIR.exists():
        shutil.rmtree(BOUNDARY_DIR)

    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BOUNDARY_ZIP, "r") as z:
        z.extractall(BOUNDARY_DIR)

    print(f"Extracted boundary file to: {BOUNDARY_DIR}")


def find_shapefile():
    shp_files = list(BOUNDARY_DIR.glob("*.shp"))

    if not shp_files:
        raise FileNotFoundError(f"No .shp file found in {BOUNDARY_DIR}")

    return shp_files[0]


def make_geojson(records):
    records_by_geoid = {record["geoid"]: record for record in records}

    shp_path = find_shapefile()
    reader = shapefile.Reader(str(shp_path), encoding="latin1")
    fields = [field[0] for field in reader.fields[1:]]

    pa_features = []
    bucks_features = []

    for shape_record in reader.iterShapeRecords():
        attrs = dict(zip(fields, shape_record.record))

        geoid = (
            str(attrs.get("STATEFP", "")).zfill(2)
            + str(attrs.get("COUNTYFP", "")).zfill(3)
            + str(attrs.get("COUSUBFP", "")).zfill(5)
        )

        data = records_by_geoid.get(geoid)

        if data is None:
            continue

        properties = {
            "statewide_rank": data["statewide_rank"],
            "municipality": data["municipality"],
            "county": data["county"],
            "households_200k_plus_pct": data["households_200k_plus_pct"],
            "households_200k_plus_display": data["households_200k_plus_display"],
            "median_household_income": data["median_household_income"],
            "median_household_income_display": data["median_household_income_display"],
            "median_household_income_range_display": data["median_household_income_range_display"],
            "geoid": geoid,
            "state_fips": data["state_fips"],
            "county_fips": data["county_fips"],
            "county_subdivision_fips": data["county_subdivision_fips"],
            "census_name": attrs.get("NAMELSAD") or attrs.get("NAME"),
        }

        feature = {
            "type": "Feature",
            "properties": properties,
            "geometry": shape_record.shape.__geo_interface__,
        }

        pa_features.append(feature)

        if data["county_fips"] == BUCKS_COUNTY_FIPS:
            bucks_features.append(feature)

    PA_GEOJSON.write_text(
        json.dumps({"type": "FeatureCollection", "features": pa_features}),
        encoding="utf-8",
    )

    BUCKS_GEOJSON.write_text(
        json.dumps({"type": "FeatureCollection", "features": bucks_features}),
        encoding="utf-8",
    )

    print(f"PA GeoJSON features written: {len(pa_features):,}")
    print(f"Bucks GeoJSON features written: {len(bucks_features):,}")


def make_database_html():
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Wealthiest towns in Pennsylvania</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #222; background: #fff; }
    .container { max-width: 1100px; margin: 0 auto; }
    h1 { font-size: 24px; margin: 0 0 8px; }
    .dek { color: #555; margin: 0 0 18px; line-height: 1.4; }
    .controls { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
    input { flex: 1; min-width: 260px; padding: 10px; font-size: 15px; border: 1px solid #bbb; border-radius: 6px; }
    .count { color: #555; font-size: 14px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid #ddd; padding: 10px 8px; text-align: left; vertical-align: top; }
    th { background: #f2f2f2; font-weight: 700; position: sticky; top: 0; z-index: 1; }
    tbody tr:nth-child(even) td { background: #f7f7f7; }
    tbody tr:hover td { background: #eeeeee; }
    .pagination { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
    button { border: 1px solid #333; border-radius: 6px; background: #fff; padding: 8px 12px; cursor: pointer; font-size: 14px; }
    button:disabled { opacity: 0.4; cursor: not-allowed; }
    .source { margin-top: 18px; color: #666; font-size: 13px; line-height: 1.4; }
    @media (max-width: 760px) {
      body { padding: 12px; }
      table { font-size: 13px; }
      th, td { padding: 8px 6px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Wealthiest towns in Pennsylvania</h1>
    <p class="dek">Search Pennsylvania municipalities ranked by the share of households earning $200,000 or more, based on 2020–2024 American Community Survey five-year estimates.</p>

    <div class="controls">
      <input id="searchInput" type="search" placeholder="Search by municipality or county...">
      <div class="count" id="resultCount"></div>
    </div>

    <table>
      <thead>
        <tr>
          <th>Statewide rank</th>
          <th>Municipality</th>
          <th>County</th>
          <th>Households earning $200,000 or more</th>
          <th>Median household income</th>
          <th>Estimated median income range</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>

    <div class="pagination">
      <button id="prevBtn">Previous</button>
      <div id="pageStatus"></div>
      <button id="nextBtn">Next</button>
    </div>

    <p class="source">Source: U.S. Census Bureau, 2020–2024 American Community Survey five-year Data Profile estimates. Municipal rankings are based on the estimated percentage of households earning $200,000 or more.</p>
  </div>

  <script>
    const rowsPerPage = 10;
    let allRows = [];
    let filteredRows = [];
    let currentPage = 1;

    const tableBody = document.getElementById("tableBody");
    const searchInput = document.getElementById("searchInput");
    const resultCount = document.getElementById("resultCount");
    const pageStatus = document.getElementById("pageStatus");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");

    function renderTable() {
      const totalPages = Math.max(1, Math.ceil(filteredRows.length / rowsPerPage));

      if (currentPage > totalPages) {
        currentPage = totalPages;
      }

      const start = (currentPage - 1) * rowsPerPage;
      const pageRows = filteredRows.slice(start, start + rowsPerPage);

      tableBody.innerHTML = "";

      for (const row of pageRows) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.statewide_rank}</td>
          <td>${row.municipality}</td>
          <td>${row.county}</td>
          <td>${row.households_200k_plus_display}</td>
          <td>${row.median_household_income_display}</td>
          <td>${row.median_household_income_range_display}</td>
        `;
        tableBody.appendChild(tr);
      }

      resultCount.textContent = `${filteredRows.length.toLocaleString()} municipalities`;
      pageStatus.textContent = `Page ${currentPage} of ${totalPages}`;
      prevBtn.disabled = currentPage <= 1;
      nextBtn.disabled = currentPage >= totalPages;
    }

    function applySearch() {
      const query = searchInput.value.trim().toLowerCase();

      if (!query) {
        filteredRows = [...allRows];
      } else {
        filteredRows = allRows.filter(row => {
          return (
            row.municipality.toLowerCase().includes(query) ||
            row.county.toLowerCase().includes(query)
          );
        });
      }

      currentPage = 1;
      renderTable();
    }

    prevBtn.addEventListener("click", () => {
      currentPage -= 1;
      renderTable();
    });

    nextBtn.addEventListener("click", () => {
      currentPage += 1;
      renderTable();
    });

    searchInput.addEventListener("input", applySearch);

    fetch("assets/wealthiest_towns.json")
      .then(response => response.json())
      .then(data => {
        allRows = data;
        filteredRows = [...allRows];
        renderTable();
      });
  </script>
</body>
</html>
"""
    (DOCS_DIR / "wealthiest-towns-database.html").write_text(html, encoding="utf-8")


def make_map_html(title, subtitle, geojson_file, output_file):
    is_state_map = geojson_file == "wealthiest_towns_pa.geojson"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">

  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #222; background: #fff; }}

    .page-shell {{
      max-width: 1400px;
      margin: 0 auto;
      border-left: 1px solid #d8d8d8;
      border-right: 1px solid #d8d8d8;
      background: #fff;
      box-sizing: border-box;
    }}

    .header {{
      padding: 14px 16px 10px;
      border-bottom: 1px solid #ddd;
    }}

    h1 {{
      font-size: 22px;
      margin: 0 0 6px;
      line-height: 1.15;
    }}

    .dek {{
      margin: 0;
      color: #555;
      font-size: 14px;
      line-height: 1.4;
    }}

    #map {{
      width: 100%;
      height: 620px;
    }}

    body.statewide-map #map {{
      height: 430px;
    }}

    .spectrum-legend {{
      padding: 12px 16px 14px;
      border-top: 1px solid #ddd;
      background: #fff;
    }}

    .spectrum-title {{
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #333;
    }}

    .spectrum-bar {{
      height: 16px;
      border-radius: 999px;
      border: 1px solid #888;
      background: linear-gradient(
        to right,
        #fee838 0%,
        #c8ba6a 20%,
        #958f78 40%,
        #666870 60%,
        #31446b 80%,
        #00224e 100%
      );
    }}

    .spectrum-labels {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-top: 8px;
      font-size: 12px;
      color: #444;
      line-height: 1.25;
    }}

    .spectrum-labels span {{
      flex: 1;
    }}

    .spectrum-labels span:nth-child(1) {{ text-align: left; }}
    .spectrum-labels span:nth-child(2),
    .spectrum-labels span:nth-child(3),
    .spectrum-labels span:nth-child(4),
    .spectrum-labels span:nth-child(5) {{ text-align: center; }}
    .spectrum-labels span:nth-child(6) {{ text-align: right; }}

    .source {{
      padding: 10px 16px 14px;
      font-size: 12px;
      color: #666;
      border-top: 1px solid #ddd;
    }}

    .town-tooltip {{
      font-size: 13px;
      line-height: 1.35;
    }}

    .hover-card {{
      position: fixed;
      z-index: 1000;
      display: none;
      max-width: 260px;
      background: white;
      border: 1px solid #999;
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
      padding: 10px 12px;
      font-size: 13px;
      line-height: 1.35;
      pointer-events: none;
    }}

    @media (max-width: 700px) {{
      .page-shell {{
        border-left: 0;
        border-right: 0;
      }}

      .header {{
        padding: 12px 14px 10px;
      }}

      h1 {{
        font-size: 21px;
      }}

      .dek {{
        font-size: 14px;
      }}

      #map {{
        height: 620px;
      }}

      body.statewide-map #map {{
        height: 430px;
      }}

      .spectrum-legend {{
        padding: 10px 12px 12px;
      }}

      .spectrum-title {{
        font-size: 12px;
      }}

      .spectrum-labels {{
        font-size: 11px;
        gap: 4px;
      }}

      .source {{
        font-size: 11px;
        padding: 10px 12px 12px;
      }}
    }}

    @media (max-width: 420px) {{
      body.bucks-map #map {{
        height: 600px;
      }}

      body.statewide-map #map {{
        height: 430px;
      }}

      .spectrum-labels {{
        font-size: 10px;
      }}
    }}
  </style>
</head>
<body class="{ 'statewide-map' if is_state_map else 'bucks-map' }">
  <div class="page-shell">
    <div class="header">
      <h1>{title}</h1>
      <p class="dek">{subtitle}</p>
    </div>

    <div id="map"></div>
    <div id="hoverCard" class="hover-card"></div>

    <div class="spectrum-legend">
      <div class="spectrum-title">{ 'Median household income' if is_state_map else 'Households earning $200K+' }</div>
      <div class="spectrum-bar"></div>
      <div class="spectrum-labels">
        { '<span>Under $75K</span><span>$75K to $99K</span><span>$100K to $124K</span><span>$125K to $149K</span><span>$150K to $199K</span><span>$200K+</span>' if is_state_map else '<span>Less than 10%</span><span>10% to 19.9%</span><span>20% to 29.9%</span><span>30% to 39.9%</span><span>40% to 49.9%</span><span>50% or more</span>' }
      </div>
    </div>

    <div class="source">Source: U.S. Census Bureau, 2020?2024 American Community Survey five-year Data Profile estimates.</div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <script>
    const isStateMetricMap = "{geojson_file}" === "wealthiest_towns_pa.geojson";

    const map = L.map("map", {{
      scrollWheelZoom: false,
      zoomSnap: 0.25,
      zoomDelta: 0.25
    }}).setView([41.0, -77.7], 7);

    L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }}).addTo(map);

    function getColor(value) {{
      if (isStateMetricMap) {{
        if (value >= 200000) return "#00224e";
        if (value >= 150000) return "#31446b";
        if (value >= 125000) return "#666870";
        if (value >= 100000) return "#958f78";
        if (value >= 75000) return "#c8ba6a";
        return "#fee838";
      }}

      if (value >= 50) return "#00224e";
      if (value >= 40) return "#31446b";
      if (value >= 30) return "#666870";
      if (value >= 20) return "#958f78";
      if (value >= 10) return "#c8ba6a";
      return "#fee838";
    }}

    function styleFeature(feature) {{
      const value = isStateMetricMap
        ? feature.properties.median_household_income
        : feature.properties.households_200k_plus_pct;

      return {{
        color: "#555",
        weight: 0.6,
        opacity: 0.8,
        fillColor: getColor(value),
        fillOpacity: 0.78
      }};
    }}

    function ordinal(value) {{
      const number = Number(value);
      const mod100 = number % 100;

      if (mod100 >= 11 && mod100 <= 13) {{
        return `${{number}}th`;
      }}

      switch (number % 10) {{
        case 1:
          return `${{number}}st`;
        case 2:
          return `${{number}}nd`;
        case 3:
          return `${{number}}rd`;
        default:
          return `${{number}}th`;
      }}
    }}

    function makePopup(feature) {{
      const p = feature.properties;

      return `
        <strong>${{p.municipality}}</strong><br>
        ${{p.county}}<br><br>
        <strong>Statewide rank by $200K+ share:</strong> ${{ordinal(p.statewide_rank)}}<br>
        <strong>Households earning $200,000+:</strong> ${{p.households_200k_plus_display}}<br>
        <strong>Median household income:</strong> ${{p.median_household_income_display}}<br>
        <strong>Estimated median income range:</strong> ${{p.median_household_income_range_display}}
      `;
    }}

    let popupIsOpen = false;
    let geojsonLayer;

    const hoverCard = document.getElementById("hoverCard");

    function showHoverCard(event, feature) {{
      if (popupIsOpen) {{
        hideHoverCard();
        return;
      }}

      hoverCard.innerHTML = makePopup(feature);
      hoverCard.style.display = "block";
      moveHoverCard(event);
    }}

    function moveHoverCard(event) {{
      if (popupIsOpen || hoverCard.style.display === "none") {{
        return;
      }}

      const offset = 14;
      const cardWidth = hoverCard.offsetWidth || 260;
      const cardHeight = hoverCard.offsetHeight || 120;

      let left = event.originalEvent.clientX + offset;
      let top = event.originalEvent.clientY + offset;

      if (left + cardWidth > window.innerWidth - 8) {{
        left = event.originalEvent.clientX - cardWidth - offset;
      }}

      if (top + cardHeight > window.innerHeight - 8) {{
        top = event.originalEvent.clientY - cardHeight - offset;
      }}

      hoverCard.style.left = `${{left}}px`;
      hoverCard.style.top = `${{top}}px`;
    }}

    function hideHoverCard() {{
      hoverCard.style.display = "none";
      hoverCard.innerHTML = "";
    }}

    function onEachFeature(feature, layer) {{
      layer.bindPopup(makePopup(feature));

      layer.on({{
        popupopen: event => {{
          popupIsOpen = true;
          hideHoverCard();
        }},

        popupclose: event => {{
          popupIsOpen = false;
          hideHoverCard();
        }},

        mouseover: event => {{
          event.target.setStyle({{ weight: 2, color: "#000", fillOpacity: 0.9 }});
          event.target.bringToFront();
          showHoverCard(event, feature);
        }},

        mousemove: event => {{
          moveHoverCard(event);
        }},

        mouseout: event => {{
          geojsonLayer.resetStyle(event.target);
          hideHoverCard();
        }},

        click: event => {{
          popupIsOpen = true;
          hideHoverCard();
          event.target.openPopup();
        }}
      }});
    }}

    fetch("assets/{geojson_file}")
      .then(response => response.json())
      .then(data => {{
        geojsonLayer = L.geoJSON(data, {{
          style: styleFeature,
          onEachFeature: onEachFeature
        }}).addTo(map);

        const isMobile = window.innerWidth <= 700;
        const isStateMap = "{geojson_file}" === "wealthiest_towns_pa.geojson";

        setTimeout(() => {{
          map.invalidateSize();

          if (isStateMap && isMobile) {{
            // Statewide mobile map: fixed PA-centered view is more predictable in tall/narrow iframe layouts.
            map.setView([40.9, -77.8], 6);
          }} else if (isStateMap) {{
            // Statewide desktop/tablet map: fit Pennsylvania tightly.
            map.fitBounds(geojsonLayer.getBounds(), {{ padding: [8, 8] }});
          }} else if (isMobile) {{
            // Bucks-only mobile map: give it a little breathing room.
            map.fitBounds(geojsonLayer.getBounds(), {{ padding: [30, 30] }});
          }} else {{
            // Bucks-only desktop/tablet map.
            map.fitBounds(geojsonLayer.getBounds(), {{ padding: [10, 10] }});
          }}
        }}, 150);
      }});
  </script>
</body>
</html>
"""
    (DOCS_DIR / output_file).write_text(html, encoding="utf-8")

def make_all_pages():
    make_database_html()

    make_map_html(
        title="Map: Median household income in Pennsylvania",
        subtitle="Pennsylvania municipalities by estimated median household income.",
        geojson_file="wealthiest_towns_pa.geojson",
        output_file="wealthiest-towns-map-pa.html",
    )

    make_map_html(
        title="Map: Wealthiest towns in Bucks County",
        subtitle="Bucks County municipalities by share of households earning $200,000 or more.",
        geojson_file="wealthiest_towns_bucks.geojson",
        output_file="wealthiest-towns-map-bucks.html",
    )


def main():
    if not MUNICIPAL_CSV.exists():
        raise FileNotFoundError(
            f"Missing {MUNICIPAL_CSV}. Run build_wealthiest_towns.py first."
        )

    records = load_municipal_records()
    write_database_json(records)

    download_boundaries()
    make_geojson(records)
    make_all_pages()

    print("Done.")
    print("GitHub Pages files written to:")
    print(f"- {DOCS_DIR / 'wealthiest-towns-database.html'}")
    print(f"- {DOCS_DIR / 'wealthiest-towns-map-pa.html'}")
    print(f"- {DOCS_DIR / 'wealthiest-towns-map-bucks.html'}")
    print()
    print("Assets written to:")
    print(f"- {DATABASE_JSON}")
    print(f"- {PA_GEOJSON}")
    print(f"- {BUCKS_GEOJSON}")


if __name__ == "__main__":
    main()
