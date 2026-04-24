# Media Asset Specifications

All media assets for the homepage and login page should be placed in this directory.

## Required Assets

### Homepage Hero

| File | Format | Dimensions | Max Size | Purpose |
|------|--------|------------|----------|---------|
| `hero-loop.mp4` | H.264 MP4 | 1920×1080 | 4 MB | Hero background loop (8-15s) |
| `hero-loop.webm` | VP9 WebM | 1920×1080 | 3 MB | Hero background loop (WebM variant) |
| `hero-poster.jpg` | JPEG | 1920×1080 | 200 KB | First frame / loading poster |
| `hero-fallback.jpg` | JPEG | 1920×1080 | 300 KB | Static fallback when video unavailable |

### Homepage Demo Section

| File | Format | Dimensions | Max Size | Purpose |
|------|--------|------------|----------|---------|
| `demo-dashboard.mp4` | H.264 MP4 | 1280×720 | 3 MB | Dashboard walkthrough loop (10-20s) |
| `demo-dashboard.webm` | VP9 WebM | 1280×720 | 2.5 MB | Dashboard walkthrough (WebM variant) |
| `demo-poster.jpg` | JPEG | 1280×720 | 150 KB | Demo section poster image |
| `demo-fallback.jpg` | JPEG | 1280×720 | 200 KB | Static dashboard preview |

### Login Side Panel

| File | Format | Dimensions | Max Size | Purpose |
|------|--------|------------|----------|---------|
| `login-panel.mp4` | H.264 MP4 | 960×1080 | 2.5 MB | Login side panel ambient loop (10-20s) |
| `login-panel.webm` | VP9 WebM | 960×1080 | 2 MB | Login side panel (WebM variant) |
| `login-poster.jpg` | JPEG | 960×1080 | 150 KB | Login panel poster |
| `login-fallback.jpg` | JPEG | 960×1080 | 200 KB | Login panel static fallback |

## Video Production Guidelines

### Content Direction
- **Hero**: Abstract data visualization — flowing particle networks, map pin clusters
  materializing, score gauges animating, subtle AI pulse effects
- **Demo**: Screen recording of the actual dashboard with smooth scroll and interactions,
  color-graded to match the dark theme
- **Login panel**: Slow ambient motion — abstract topographic map lines, gentle data
  flow particles, or a subtle dark cityscape with glowing data points

### Technical Requirements
- Loop seamlessly (match first and last frames)
- No audio track (reduces file size)
- Encode at CRF 28-32 for H.264, CRF 35-40 for VP9
- Use 24fps for ambient loops, 30fps for demo recordings
- Apply slight vignette and color grade to match the dark theme palette
- Test on mobile — videos should degrade gracefully

### Color Palette Reference
- Background: `#090b12` (near-black)
- Accent teal: `#14b8a6`
- Accent blue: `#3b82f6`
- Surface: `#0f172a` (dark slate)
- Text: `#e5edf8` (light)
- Muted: `#8b9bb3`

## Image Optimization Checklist
- [ ] Export JPEGs at quality 80-85
- [ ] Strip EXIF metadata
- [ ] Use progressive JPEG encoding
- [ ] Consider AVIF as a future format upgrade
- [ ] Test loading on throttled 3G connection
