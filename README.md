# π slice

Video splicing tool for creating robot operation documentation.

## Setup (do this once)

**Requirements:** Python 3.9+

1. Install dependencies:
   ```
   pip install flask imageio-ffmpeg
   ```

2. Start the server:
   ```
   python serve.py
   ```

3. Open Chrome and go to:
   ```
   http://localhost:8080/video-splicer.html
   ```

## Usage

- **Import** videos by dragging them onto the page
- **Mark clips** with `Q` (start) / `E` (end) / `Enter` (add segment)
- **Multi-view** — click ⊞ Multi-View to sync 4 camera angles at once
- **Draw** — click ✏ Draw to annotate frames, save as PNG
- **Export** individual clips, or use ⛓ Join to combine all segments
- **📋 Notion Ready** — sets all segments to MP4 CRF 28 for Notion uploads
- **Export Notes** — downloads a markdown doc with all step timestamps and notes

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
| `← →` | Seek 1s  (hold Shift for 10s) |
