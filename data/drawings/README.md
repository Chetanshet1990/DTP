# Public Representative Drawings

These PDFs are public representative engineering drawings/tutorial drawings for
the sheet-metal categories used in the procurement cost-intelligence prototype.
They are not proprietary drawings for the synthetic sample parts; they are
reference drawings suitable for testing OCR/feature-extraction workflows and for
first-review demonstration material.

| File | Representative category | Source |
|---|---|---|
| `mit_ocw_metal_bracket.pdf` | Bracket | MIT OpenCourseWare, 2.007 Design and Manufacturing I, metal bracket project PDF: https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/resources/mit2_007s09_metal_bracket/ |
| `umaine_sheetmetal_bracket_example.pdf` | Bracket / flat pattern | University of Maine Mechanical Engineering MEE120 sheet metal example: https://umaine.edu/mechanical-engineering-mee120/wp-content/uploads/sites/363/2018/06/sheetmetal_example2.pdf |
| `njit_sheet_metal_clip.pdf` | Sheet-metal clip / bracket-like part | NJIT Open Educational Resource, Engineering Design and Analysis using Creo CAD, CAE, and Manufacturing Applications, Chapter 10 Sheet Metal Clip: https://digitalcommons.njit.edu/oat/2/ |
| `njit_control_bracket_engineering_drawing.pdf` | Control bracket / bracket drawing | NJIT Open Educational Resource, Engineering Design and Analysis using Creo CAD, CAE, and Manufacturing Applications, Chapter 18 Engineering Drawing - Control Bracket: https://digitalcommons.njit.edu/oat/2/ |
| `hammond_csfc88_flush_cover_panel.pdf` | Cover / panel | AutomationDirect / Hammond CSFC88 2D drawing: https://cdn.automationdirect.com/static/drawings/CSFC88.pdf |
| `hammond_1554epl_internal_panel.pdf` | Internal panel / mounting panel | Hammond Manufacturing 1554EPL drawing: https://www.hammfg.com/files/parts/pdf/1554EPL.pdf |

Suggested prototype use:

- Bracket parts: `SM-1001`, `SM-1005`, `SM-1009`, `SM-1013`, `SM-1017`,
  `SM-1021`, `SM-1025`, `SM-1029`
- Mounting plate parts: `SM-1002`, `SM-1006`, `SM-1010`, `SM-1014`,
  `SM-1018`, `SM-1022`, `SM-1026`
- Cover / panel parts: `SM-1003`, `SM-1007`, `SM-1011`, `SM-1015`,
  `SM-1019`, `SM-1023`, `SM-1027`, `SM-1030`

## SM-1001 Searchable Drawing

`SM-1001_searchable.pdf` is the ingestion-ready version of the supplied
image-based A3 drawing. Its visible appearance is preserved and an invisible,
searchable PDF text layer supplies the exact fields required by the frontend:
category, material, material grade, thickness, length, width, weight, bend count,
hole count, and surface finish.

The searchable drawing specifies two bends and sixteen hole-equivalent elements.
The selected part ID in the frontend is authoritative, so drawing Part ID parsing
is not required.

After the user reviews and commits an uploaded drawing, the physical file is saved
under `data/drawings/committed/<part_id>/`. The active part master records the
stored relative path, SHA-256 hash, and UTC commit timestamp. Drawings that fail
validation or the ML dry-run are not retained.

Regenerate the searchable file with:

```bash
python3 scripts/generate_searchable_drawing.py \
  --input /path/to/SM-1001.pdf \
  --output data/drawings/SM-1001_searchable.pdf
```
