from pathlib import Path
import sys
import html

import pandas as pd

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

ACS_YEAR = 2024

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"
STORY_DIR = PROJECT_DIR / "story_outputs"
STORY_DIR.mkdir(exist_ok=True)


def money(value):
    if pd.isna(value):
        return "not available"
    return f"${value:,.0f}"


def pct(value):
    if pd.isna(value):
        return "not available"
    return f"{value:.1f}%"


def rank_label(value):
    value = int(value)

    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")

    return f"{value}{suffix}"


def format_income_range(low, high):
    return f"{money(low)} to {money(high)}"


def make_statewide_top_10_list(top_10_pa):
    lines = [
        "Top 10 Pennsylvania municipalities by share of households earning $200,000 or more",
        "",
        f"Source: {ACS_YEAR} American Community Survey five-year estimates.",
        "",
    ]

    for _, row in top_10_pa.iterrows():
        lines.append(
            f"{int(row['state_rank'])}. {row['municipality']}, {row['county']}: "
            f"{pct(row['pct_200k_plus'])} of households earned $200,000 or more. "
            f"Estimated median household income range: "
            f"{format_income_range(row['median_income_low'], row['median_income_high'])}."
        )

    return "\n".join(lines)


def make_bucks_top_10_list(top_10_bucks):
    lines = [
        "Top 10 Bucks County municipalities by share of households earning $200,000 or more",
        "",
        f"Source: {ACS_YEAR} American Community Survey five-year estimates.",
        "",
    ]

    for i, (_, row) in enumerate(top_10_bucks.iterrows(), start=1):
        lines.append(
            f"{i}. {row['municipality']}: "
            f"{pct(row['pct_200k_plus'])} of households earned $200,000 or more. "
            f"That ranked {rank_label(row['state_rank'])} statewide. "
            f"Estimated median household income range: "
            f"{format_income_range(row['median_income_low'], row['median_income_high'])}."
        )

    return "\n".join(lines)


def make_county_context(counties):
    bucks = counties[counties["county"] == "Bucks County"].iloc[0]
    top_counties = counties.sort_values("state_county_income_rank").head(5)

    lines = [
        "County median household income context",
        "",
        f"Bucks County ranked {rank_label(bucks['state_county_income_rank'])} among Pennsylvania counties "
        f"for estimated median household income in the {ACS_YEAR} American Community Survey five-year estimates.",
        "",
        f"Bucks County's estimated median household income was {money(bucks['median_income'])}, "
        f"with a margin-of-error range of {format_income_range(bucks['median_income_low'], bucks['median_income_high'])}.",
        "",
        "The top five Pennsylvania counties by estimated median household income were:",
        "",
    ]

    for _, row in top_counties.iterrows():
        lines.append(
            f"{int(row['state_county_income_rank'])}. {row['county']}: "
            f"{money(row['median_income'])} "
            f"({format_income_range(row['median_income_low'], row['median_income_high'])})"
        )

    return "\n".join(lines)


def make_top_50_county_context(county_counts):
    lines = [
        "County breakdown of the statewide top 50",
        "",
        "Number of municipalities each county placed in the statewide top 50:",
        "",
    ]

    for _, row in county_counts.iterrows():
        town_word = "municipality" if row["towns_in_top_50"] == 1 else "municipalities"
        lines.append(f"{row['county']}: {int(row['towns_in_top_50'])} {town_word}")

    return "\n".join(lines)


def make_story_shell(top_10_pa, top_10_bucks, counties):
    top_state = top_10_pa.iloc[0]
    top_bucks = top_10_bucks.iloc[0]
    bucks_county = counties[counties["county"] == "Bucks County"].iloc[0]

    lines = [
        "Story shell",
        "",
        f"More than half of households in {top_bucks['municipality']} earned at least $200,000, "
        f"making it the highest-ranked Bucks County municipality in a new analysis of "
        f"{ACS_YEAR} American Community Survey five-year estimates.",
        "",
        f"{top_bucks['municipality']} ranked {rank_label(top_bucks['state_rank'])} statewide, "
        f"with {pct(top_bucks['pct_200k_plus'])} of households earning $200,000 or more. "
        f"The municipality's estimated median household income range was "
        f"{format_income_range(top_bucks['median_income_low'], top_bucks['median_income_high'])}.",
        "",
        f"Statewide, {top_state['municipality']} in {top_state['county']} ranked No. 1, "
        f"with {pct(top_state['pct_200k_plus'])} of households earning $200,000 or more.",
        "",
        f"Bucks County also ranked {rank_label(bucks_county['state_county_income_rank'])} among Pennsylvania counties "
        f"for estimated median household income. The county's estimated median household income was "
        f"{money(bucks_county['median_income'])}, with a margin-of-error range of "
        f"{format_income_range(bucks_county['median_income_low'], bucks_county['median_income_high'])}.",
        "",
        "Methodology note:",
        f"This analysis used {ACS_YEAR} American Community Survey five-year Data Profile estimates. "
        "Municipal rankings are based on DP03_0061PE, the estimated percentage of households earning "
        "$200,000 or more. Median household income ranges were calculated using DP03_0062E and "
        "DP03_0062M, the estimate and margin of error for median household income.",
    ]

    return "\n".join(lines)


def text_to_cms_html(text):
    lines = text.splitlines()
    parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                parts.append("</ol>")
                in_list = False
            continue

        split_line = stripped.split(". ", 1)

        if len(split_line) == 2 and split_line[0].isdigit():
            if not in_list:
                parts.append("<ol>")
                in_list = True
            parts.append(f"<li>{html.escape(split_line[1])}</li>")
            continue

        if in_list:
            parts.append("</ol>")
            in_list = False

        if stripped.endswith(":") or stripped in [
            "Story shell",
            "County median household income context",
            "County breakdown of the statewide top 50",
            "Top 10 Pennsylvania municipalities by share of households earning $200,000 or more",
            "Top 10 Bucks County municipalities by share of households earning $200,000 or more",
            "Methodology note:",
        ]:
            parts.append(f"<h2>{html.escape(stripped)}</h2>")
        else:
            parts.append(f"<p>{html.escape(stripped)}</p>")

    if in_list:
        parts.append("</ol>")

    return "\n".join(parts)


def make_html_copy_page(outputs):
    section_order = [
        ("story_shell.txt", "Story shell"),
        ("bucks_top_10_list.txt", "Bucks County top 10"),
        ("statewide_top_10_list.txt", "Statewide top 10"),
        ("county_income_context.txt", "County income context"),
        ("top_50_county_context.txt", "Top 50 county breakdown"),
    ]

    sections = []

    for filename, label in section_order:
        raw_text = outputs[filename]
        cms_html = text_to_cms_html(raw_text)

        sections.append(f"""
<section class="copy-section">
  <div class="section-header">
    <h1>{html.escape(label)}</h1>
    <button onclick="copyPlainText('{filename}')">Copy plain text</button>
  </div>

  <textarea id="{filename}" class="copy-source">{html.escape(raw_text)}</textarea>

  <div class="cms-copy">
    {cms_html}
  </div>
</section>
""")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ACS income story copy</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      max-width: 960px;
      margin: 40px auto;
      padding: 0 20px 60px;
      line-height: 1.5;
      color: #222;
      background: #f7f7f7;
    }}

    .copy-section {{
      background: white;
      border: 1px solid #ddd;
      border-radius: 10px;
      padding: 24px;
      margin-bottom: 28px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }}

    .section-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid #eee;
      margin-bottom: 18px;
    }}

    h1 {{
      font-size: 24px;
      margin: 0 0 12px;
    }}

    h2 {{
      font-size: 20px;
      margin: 18px 0 8px;
    }}

    p {{
      margin: 0 0 14px;
    }}

    ol {{
      margin-top: 0;
      padding-left: 26px;
    }}

    li {{
      margin-bottom: 10px;
    }}

    button {{
      cursor: pointer;
      border: 1px solid #333;
      border-radius: 6px;
      background: #fff;
      padding: 8px 12px;
      font-size: 14px;
    }}

    button:hover {{
      background: #eee;
    }}

    .copy-source {{
      position: absolute;
      left: -9999px;
      height: 1px;
      width: 1px;
    }}

    .note {{
      margin-bottom: 24px;
      color: #555;
    }}
  </style>
</head>
<body>
  <h1>ACS income story copy</h1>
  <p class="note">Use the buttons to copy plain text, or select formatted text from the boxes below for CMS paste testing.</p>

  {''.join(sections)}

  <script>
    function copyPlainText(id) {{
      const textarea = document.getElementById(id);
      navigator.clipboard.writeText(textarea.value);
    }}
  </script>
</body>
</html>
"""


def main():
    top_10_pa = pd.read_csv(OUTPUT_DIR / "top_10_pa_wealthiest_towns.csv")
    top_10_bucks = pd.read_csv(OUTPUT_DIR / "top_10_bucks_wealthiest_towns.csv")
    counties = pd.read_csv(OUTPUT_DIR / "pa_county_median_income_rankings.csv")
    county_counts = pd.read_csv(OUTPUT_DIR / "county_counts_in_top_50.csv")

    outputs = {
        "statewide_top_10_list.txt": make_statewide_top_10_list(top_10_pa),
        "bucks_top_10_list.txt": make_bucks_top_10_list(top_10_bucks),
        "county_income_context.txt": make_county_context(counties),
        "top_50_county_context.txt": make_top_50_county_context(county_counts),
        "story_shell.txt": make_story_shell(top_10_pa, top_10_bucks, counties),
    }

    for filename, output_text in outputs.items():
        out_path = STORY_DIR / filename
        out_path.write_text(output_text, encoding="utf-8")

    html_path = STORY_DIR / "story_copy.html"
    html_path.write_text(make_html_copy_page(outputs), encoding="utf-8")

    print("Done.")
    print(f"Story/list files written to: {STORY_DIR}")
    print()
    for filename in outputs:
        print(f"- {filename}")
    print("- story_copy.html")


if __name__ == "__main__":
    main()
