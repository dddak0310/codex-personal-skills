# Browser / HTML Screenshot

Use this reference when the main visual is the user-facing screen of an APGPAS
web page, an HTML report, or another browser-rendered interface.

This is different from the screenshot taken during PPTX export: the export
captures the slide HTML, while this workflow captures the source page before it
is placed into the slide.

## Choose the right presentation form

| Source state | Preferred output | Slide treatment |
|---|---|---|
| One stable page state | PNG screenshot | Large image with a short state/explanation card |
| Old and new page states | Two PNG screenshots | Before/After layout 6, same viewport and zoom |
| Scroll, animation, or interaction is the point | MP4 or live browser demo | Video layout 5; use a static frame as the PPTX fallback |
| A long report page | Several meaningful viewport screenshots | Split into slides; do not shrink the entire page until text is unreadable |

The screenshot should show the page content, not the browser's address bar,
tabs, developer tools, or unrelated sidebars, unless the browser chrome itself
is part of the point being demonstrated.

## Capture workflow

### 1. Prepare the source page

- Identify the environment and page state: for example, APGPAS dev, a local
  HTML report, or a specific report/result view.
- For a local HTML report, serve it over HTTP with the report preview helper or
  another same-origin local server before opening it in the browser. Do not
  rely on a `file://` page if its assets or scripts need HTTP loading.
- For APGPAS, use the already authorized browser session. Never put passwords,
  tokens, signed URLs, or private keys into the slide, filename, caption, or
  query-string example.
- Wait until dynamic content, charts, images, and fonts have finished loading.
  Capture the state that the audience is meant to understand, not a loading
  skeleton or an accidentally empty result.

### 2. Capture a slide-safe viewport

- Capture at **1280 × 720** when the browser tool supports a fixed viewport;
  otherwise crop the result to a 16:9 content rectangle without stretching it.
- Keep the same viewport, zoom, and crop for Before/After screenshots.
- Prefer a single initial viewport with no scrolling. If the important content
  does not fit, use multiple slides or a video instead of relying on a scrollable
  element that PPTX export will not capture.
- If browser screenshot automation is available, use the user-visible page
  state from that browser session. If it is not available, a manually captured
  and reviewed PNG is a valid input; do not invent a tool-specific command.

### 3. Store and sanitize the asset

Save the reviewed image under the report's local data directory:

```text
${REPORT_ROOT}/YYYYMMDD/data/apgpas-ui-result.png
```

Use a stable descriptive name such as `apgpas-ui-before.png` or
`html-report-summary.png`. Before keeping or committing the asset:

- remove or mask patient/specimen identifiers, credentials, tokens, internal
  hostnames, and unrelated personal information unless the audience and
  repository explicitly authorize them;
- remove URL query parameters that contain access tokens or signed links;
- keep only the de-identified screenshot needed to support the slide claim;
- do not commit raw production screenshots or an unredacted capture just
  because it is under `data/`.

### 4. Place it in the slide

Use layout 1 for one screenshot with a short explanation card, or layout 6 for
Before/After. Keep the image local and relative so the portable `deck.html`
does not depend on the APGPAS session or a live server:

```html
<div style="flex:2;display:flex;align-items:center;justify-content:center;">
  <img src="data/apgpas-ui-result.png"
       alt="APGPAS result page after the change"
       style="max-width:100%;max-height:460px;object-fit:contain;
              border:1px solid #e5e7eb;border-radius:6px;">
</div>
<div class="info-card blue">
  <div class="card-title">畫面狀態</div>
  Dev environment；結果頁已顯示修正後的欄位。
</div>
```

Add a short caption or side-card note with the environment, page/state, and
capture date when that context is needed. Do not turn the caption into a long
URL or a dump of the page's raw data.

## Validation checklist

After adding the image:

1. Open the single slide and the built `deck.html` through the normal preview
   flow.
2. Confirm the image loads without the APGPAS login session or an external
   network request.
3. Inspect at presentation scale: text in the source page must be readable,
   the image must not be stretched or clipped, and no browser chrome or
   unrelated content should appear.
4. Run the normal layout audit and check the screenshot manually at enlarged
   scale. A passing HTML/layout check does not prove that the source page was
   captured in the intended state.
5. For Before/After, verify that the two captures use the same viewport, zoom,
   crop, and comparable page state.
