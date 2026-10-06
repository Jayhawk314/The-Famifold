# Framifold

A fillable timeline rubric for making videos with an AI agent.

Fill in what you know: segments, story, mood, narration, voices, and clips on five lanes (Visual, Overlay/text,
Voice, SFX, Music) with start/end, volume or brightness, pan and fades. Leave anything blank, or add a "request"
clip that only describes what is wanted. Export gives the agent a JSON plan plus a brief listing what is decided,
what is requested, and what is BLANK for the agent to propose.

## Run

Double-click `Framifold.bat` (or the desktop shortcut), or:

    cd framifold
    python -m streamlit run app.py --server.port 8510

Needs Python with `streamlit`, `plotly`, `pandas`, and `imageio-ffmpeg` (for media lengths).

## Render a plan (the agent side)

    python framifold/render.py plan.json [out.mp4] [--size 1280x720] [--fps 24]

Places every file exactly as planned (layers, timing, trim, loop, volume/opacity, pan, fades, placement).
Requests and missing files become stand-ins: an orange card showing the request for pictures, silence for sounds,
so a draft exists as soon as a plan does. Writes `out.report.md` listing what was placed, what stood in, and what
was cut. Agents: see `.claude/skills/framifold-build/SKILL.md` for how to turn requests into real files.

## Notes

- The asset library also scans `../market_system_video/assets` and its Blender renders when this folder sits inside
  `komposos-labs-videos`. Files dropped into `assets/` here appear too.
- Saved projects go to `framifold/projects/`.
- Not yet built: drag on the timeline itself (sliders do the moving), a render button in the app, a plan-vs-video checker, clip stages
  (label → described → specified → made → approved), a storyboard view, "agent decides" clips and lengths.
