---
name: brazil-map-plots
description: Create and revise Brazil map figures for this BVR project, including municipality/state context maps, treatment-year choropleths, hybrid municipality hatching, South America context, ocean background, legends, borders, and publication-ready PNG/PDF outputs under resources/maps.
---

# Brazil Map Plots

## Purpose

Use this skill for project maps of Brazil, especially municipal or state maps that need the paper's South America context, light-blue ocean, black frame, municipality/state borders, BVR treatment-year colors, or hybrid municipality hatching.

Prefer editing and running the existing plotting scripts instead of rewriting the map from scratch:

- `src/analysis/plot_brazil_municipality_context_map.R` for the plain Brazil municipality context map.
- `src/analysis/plot_brazil_bvr_treatment_map.R` for the BVR first-treatment-year map with hybrid hatching.

## Required Inputs

Use the repository's existing geodata and panel files:

- Municipal geometries: `data/clean/geodata/ibge_municipalities_2010/br_municipios_2010.shp`
- Americas context: `data/clean/geodata/natural_earth_americas_10m/ne_10m_admin_0_countries_americas.shp`
- BVR panel: `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.csv`

The BVR map should use:

- `municipality_id` as the join key, converted to character on both sides.
- `year_first_any_bvr` for first-treatment-year colors.
- `hybrid == 1` at any observed year to identify municipalities with diagonal hatch lines.
- Treatment-year bins `2008`, `2010`, `2012`, `2014`, `2016`, and `2018`.

## Visual Defaults

Keep these defaults unless the user asks for a different design:

- Exclude Fernando de Noronha from Brazil maps with `CD_GEOCODM != "2605459"`.
- Use South America surrounding countries in a light neutral fill.
- Use a light-blue ocean and panel background.
- Draw a full black map frame and keep `plot.margin = margin(0, 0, 0, 0)`.
- Keep Brazil's outline darker and thicker than internal municipality borders.
- Use thin municipality borders; make them thinner rather than visually dominant.
- Do not add a title unless requested.
- Save both PNG and PDF under `resources/maps/`.

For BVR treatment-year maps:

- Use purple shades that get darker over later first-treatment years.
- Leave never-treated or not-yet-treated municipalities in the neutral base fill.
- Show hybrid municipalities with tight diagonal hatch lines, not merely dashed outlines.
- Draw hybrid hatch lines in a light neutral color, preferably the same as the never-treated municipality fill, so they remain visible over purple treatment fills.
- Place the treatment-year legend in the top-right corner.
- Use a two-column, three-row legend for the six treatment years.

## Workflow

1. Identify whether the user wants the plain context map, the BVR treatment-year map, or a variant.
2. Patch the relevant script rather than producing an ad hoc one-off file.
3. Preserve the output basename unless the user requests a rename:
   - Plain context map: `brazil_municipalities.png` and `brazil_municipalities.pdf`.
   - BVR treatment map: `brazil_municipalities_bvr_treatment_year.png` and `brazil_municipalities_bvr_treatment_year.pdf`.
4. Run the script from the repository root:

```bash
Rscript src/analysis/plot_brazil_municipality_context_map.R
Rscript src/analysis/plot_brazil_bvr_treatment_map.R
```

5. Validate the output:
   - Confirm PNG and PDF were written under `resources/maps/`.
   - Check PNG dimensions with `sips -g pixelWidth -g pixelHeight`.
   - For BVR maps, report counts by first-treatment year and the number of hybrid municipalities hatched.
   - Record unplotted panel municipalities in `resources/maps/brazil_municipalities_bvr_treatment_year_not_plotted.csv`.
6. Use `view_image` on the PNG before finalizing design changes when the request is visual.

## Common Variants

- **Municipality borders darker/thicker/thinner:** adjust the relevant `geom_sf(... linewidth = ...)` and `color` in the municipality layer.
- **State borders:** create state outlines by grouping municipality geometries by state code or state abbreviation and using `st_union()`; draw that layer above municipalities and below the Brazil outline.
- **Legend edits:** adjust `guides(fill = guide_legend(...))` and the `legend.*` theme entries in the BVR script.
- **Zoom/crop edits:** adjust `map_xlim`, `map_ylim`, and the derived export height together so the map frame and output aspect ratio remain aligned.
- **Hybrid marking edits:** keep the lightweight diagonal line overlay approach in `plot_brazil_bvr_treatment_map.R`; package-level polygon patterning can be too slow for all municipalities.

## Reporting

In the final response, include links to the generated PNG/PDF, mention any script changed, and state any important coverage caveat such as municipalities not plotted because they do not exist in the 2010 IBGE shapefile or were intentionally excluded.
