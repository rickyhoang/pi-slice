# π slice

Video splicing tool for creating robot operation documentation. Slice videos into annotated steps, generate Notion-ready instruction docs, and export everything as a ZIP.

## Setup (do this once)

**Requirements:** Python 3.9+

```
pip install flask imageio-ffmpeg
```

Start the server:
```
python serve.py
```

Open Chrome and go to:
```
http://localhost:8080/video-splicer.html
```

---

## Usage

### Importing videos
- Drag and drop one or more video files onto the import screen, or click to browse
- All imported videos appear in the **left sidebar** — click any to switch it into the player
- Supported formats: MP4, MOV, WebM, AVI, MKV

### Marking segments
- Seek to a point, press **Q** to set the start and **E** to set the end
- Press **Enter** (or click **+ Add**) to create the segment
- Segments appear in the **right panel** — drag the ⠿ handle to reorder
- Click any segment card to jump the video to that point
- Click a segment band on the timeline to highlight the matching card

### Multi-view (4-screen sync)
- Click **⊞ Multi-View** to switch to a 4-screen grid
- Slots are labelled **Base / Left / Right / Top** by default — click the label to rename
- Drag a video from the left sidebar directly onto a slot, or click a slot to assign
- All 4 screens play, pause, and seek in sync from the shared timeline
- Press **Enter** in multi-view to create one segment per assigned slot simultaneously — each is tagged with its perspective (Base, Left, Right, Top) and grouped as one step
- Segments from the same step are visually grouped in the right panel

### Annotating segments
- Each segment card has **L / R / B** perspective badges (set automatically from multi-view slots)
- Expand **📝 Notes** on any card to write step notes
- For multi-view groups, notes sync across all angle cards automatically
- The **⚠ banner** at the top of the segment list shows how many steps are missing notes
- Cards with notes show a **green left border** for quick visual scanning
- Click **📝** in the panel header to expand or collapse all notes at once

### Exporting
- **↓ Export All** — downloads every segment as individual video files
- **↓ Export Selected** — appears when you have segments checked; exports only those
- **⛓ Join** — combines all (or selected) segments into one MP4
- **📋 Notion Ready** — sets all segments to MP4 CRF 28 in one click (good for Notion upload sizes)
- Each segment has a **format dropdown** (Same as source / MP4 / WebM / GIF) and a **quality dropdown** (Fast copy / High / Good / Small)

### Instruction generator
- Click **📄 Instructions** in the panel footer to open the instruction generator
- Fill in metadata, props, start/final state, clean-up, PPE, and ergonomics
- Each segment's notes and perspective labels feed into the step list automatically
- Click **Generate** to preview the full Notion-formatted markdown
- **Copy for Notion** — copies the markdown to clipboard, paste directly into Notion
- **📦 Export ZIP** — downloads a ZIP containing all video clips + `instructions.md`

### Other features
- **✏ Draw** — annotate directly on the video frame; tools include pen, arrow, rectangle, circle, text, eraser. Works in multi-view too (click a cell to select it as the draw target). **Save PNG** exports the current frame with annotations burned in.
- **Thumbnail scrub** — hover over the timeline to preview frames; hover over a segment card to see its start frame
- **Timeline zoom** — scroll the timeline to zoom in (up to 80×). The zoom level badge resets on click.
- **Batch rename** — click **✎** in the panel header to rename selected segments using patterns: `{n}` = number, `{video}` = source filename, `{time}` = timestamp
- **☑ Select mode** — click **☑** in the panel header to show checkboxes; Export All / Join / ZIP respect the selection
- **Session auto-save** — all segments, notes, and settings are saved automatically; a restore prompt appears on next visit
- **Dark / light mode** — click 🌙 in the top-right corner; preference is remembered

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / pause |
| `Q` | Set start point |
| `E` | Set end point |
| `Enter` | Add segment |
| `F` | Fullscreen |
| `,` / `.` | Step one frame back / forward |
| `Ctrl+Z` | Undo last segment or drawing stroke |
| `← →` | Seek 1s (hold `Shift` for 10s) |
| `J` / `L` | Seek −5s / +5s |
| `K` | Play / pause |
