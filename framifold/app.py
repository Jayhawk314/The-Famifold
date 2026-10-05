"""Framifold: a fillable timeline rubric for making a video with an AI agent.

You fill in what you know (story, mood, narration, voices, sounds, images, timing, loudness, brightness).
Leave anything blank or add a "request" clip ("Blender: dials turning, 8 s"). Export gives the agent
a JSON plan plus a plain brief of what is decided, what is requested, and what is still blank.

Run:  streamlit run app.py
"""
import json, re, subprocess, time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
PROJECTS = HERE / "projects"
PROJECTS.mkdir(exist_ok=True)
VIDEOS = HERE.parent.parent  # komposos-labs-videos
ASSET_ROOTS = {
    "Framifold assets": HERE.parent / "assets",
    "Market video SFX": VIDEOS / "market_system_video" / "assets" / "sfx",
    "Market video music": VIDEOS / "market_system_video" / "assets" / "music",
    "Market video stills": VIDEOS / "market_system_video" / "assets" / "stills",
    "Market video Blender": VIDEOS / "market_system_video" / "blender",
    "Voice previews": VIDEOS / "market_system_video" / "voice_previews",
}
KINDS = {".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".flac": "audio", ".m4a": "audio",
         ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
         ".mp4": "video", ".mov": "video", ".webm": "video"}
LANES = ["Visual", "Overlay / text", "Voice", "SFX", "Music"]
LANE_COLOURS = {"Visual": "#4C78A8", "Overlay / text": "#B279A2", "Voice": "#F58518",
                "SFX": "#54A24B", "Music": "#E45756"}
SEG_COLS = ["name", "duration_s", "story", "mood", "narration", "voice", "notes"]
STRICT_RULES = {
    "Strict": ["- Filled fields are exact instructions: follow them as written. Change nothing, even to improve it.",
               "- BLANK fields: do not invent. Ask James what goes there before making anything for it.",
               "- If something in the plan cannot be done as written, stop and say so. Do not substitute."],
    "Balanced": ["- Filled fields are decisions: follow them.",
                 "- BLANK fields: propose something that fits the rest of the plan, mark it as a proposal, "
                 "and ask James before treating it as decided."],
    "Loosey-goosey": ["- Everything here is an idea, not an instruction. Improvise, add, cut or reorder if it makes a better video.",
                      "- BLANK fields: your choice.",
                      "- At the end, list every change from the plan and why, so James can see what moved."],
}
BLANK_TAG = {"Strict": "BLANK (ask James)", "Balanced": "BLANK (agent proposes, James approves)",
             "Loosey-goosey": "BLANK (agent's choice)"}

st.set_page_config(page_title="Framifold", layout="wide")


# ------------------------------------------------------------------ project state

def blank_project():
    return dict(meta=dict(title="", logline="", theme="", mood="", audience="", target_length_s=180,
                          voices="", look="", rules="", notes=""),
                segments=[dict(name="Cold open", duration_s=30.0, story="", mood="", narration="", voice="", notes="")],
                clips=[], next_id=1)


def set_project(p):
    st.session_state.project = p
    st.session_state.pop("strictness_w", None)  # let the radio pick up the loaded project's setting
    st.session_state.editor_rev = st.session_state.get("editor_rev", 0) + 1
    st.session_state.seg_base = pd.DataFrame(p["segments"], columns=SEG_COLS)


if "project" not in st.session_state:
    set_project(blank_project())
P = st.session_state.project


@st.cache_data(show_spinner=False)
def media_duration(path: str, mtime: float):
    try:
        import imageio_ffmpeg
        r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", path], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
        return round(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), 2) if m else None
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def scan_assets(_stamp):
    rows = []
    for label, root in ASSET_ROOTS.items():
        if not root.exists():
            continue
        for f in sorted(root.rglob("*")):
            kind = KINDS.get(f.suffix.lower())
            if not kind or "frames" in f.parts:
                continue
            dur = media_duration(str(f), f.stat().st_mtime) if kind != "image" else None
            rows.append(dict(source=label, name=f.stem, kind=kind, duration_s=dur, path=str(f)))
    return rows


def total_length():
    return round(sum(float(s.get("duration_s") or 0) for s in P["segments"]), 2)


def seg_bounds():
    t, out = 0.0, []
    for s in P["segments"]:
        d = float(s.get("duration_s") or 0)
        out.append((t, t + d, s))
        t += d
    return out


def fmt(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ------------------------------------------------------------------ sidebar: project + the big picture

with st.sidebar:
    st.header("Project")
    saved = sorted(p.stem for p in PROJECTS.glob("*.json"))
    c1, c2 = st.columns(2)
    pick = c1.selectbox("Open", ["(new)"] + saved, label_visibility="collapsed")
    if c2.button("Load", width="stretch"):
        set_project(blank_project() if pick == "(new)" else json.loads((PROJECTS / f"{pick}.json").read_text(encoding="utf-8")))
        st.rerun()

    m = P["meta"]
    m["title"] = st.text_input("Title", m["title"])
    m["logline"] = st.text_area("Story in one or two lines", m["logline"], height=70)
    m["theme"] = st.text_input("Theme (what it is really about)", m["theme"])
    m["mood"] = st.text_input("Overall mood", m["mood"])
    m["audience"] = st.text_input("Audience", m["audience"])
    m["target_length_s"] = st.number_input("Target length (s)", 10, 3600, int(m["target_length_s"]), 10)
    m["voices"] = st.text_area("Voice cast (who speaks, which voice)", m["voices"], height=70)
    m["look"] = st.text_area("Look (style, colour, Blender / stills / footage)", m["look"], height=70)
    m["rules"] = st.text_area("Rules for the agent (must / must not)", m["rules"], height=70)
    m["notes"] = st.text_area("Other notes", m["notes"], height=70)
    m["strictness"] = st.radio("How strictly the agent follows this plan", list(STRICT_RULES),
                               index=list(STRICT_RULES).index(m.get("strictness", "Balanced")), key="strictness_w",
                               help="Strict: exactly as written, ask about blanks. Balanced: follow it, propose blanks. "
                                    "Loosey-goosey: ideas only, improvise, list the changes.")

    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", m["title"].strip()) or "untitled"
    if st.button(f"Save as projects/{fname}.json", type="primary", width="stretch"):
        (PROJECTS / f"{fname}.json").write_text(json.dumps(P, indent=2), encoding="utf-8")
        st.success("Saved.")


# ------------------------------------------------------------------ helpers for clips

TOTAL = total_length()
ASSETS = scan_assets(int(time.time() // 300))
WANT = {"Visual": ("image", "video"), "Overlay / text": ("image", "video"), "Voice": ("audio",),
        "SFX": ("audio",), "Music": ("audio",)}


def clip_label(c):
    return f"#{c['id']} · {c['lane']} · " + (c["asset_name"] or "REQUEST: " + c["request"][:40])  # no times: label must not change while editing


def preview(o, where=st):
    if o["kind"] == "audio":
        where.audio(o["path"])
    elif o["kind"] == "image":
        where.image(o["path"], width=360)
    else:
        where.video(o["path"])


@st.dialog("Add a clip", width="large")
def add_dialog(lane):
    st.markdown(f"Adding to the **{lane}** lane.")
    mode = st.radio("Source", ["From library", "Request (agent finds or makes it)"], horizontal=True)
    segs = seg_bounds()
    seg_names = [f"{i+1}. {s.get('name') or 'segment'} ({fmt(a)})" for i, (a, b, s) in enumerate(segs)]
    at_seg = seg_names.index(st.selectbox("Start at segment", seg_names)) if segs else None
    o, request = None, ""
    if mode == "From library":
        q = st.text_input("Search the library", "")
        opts = [a for a in ASSETS if a["kind"] in WANT[lane] and q.lower() in (a["name"] + a["source"]).lower()]
        labels = [f"{x['name']}  ·  {x['source']}" + (f"  ·  {x['duration_s']}s" if x["duration_s"] else "") for x in opts]
        if opts:
            o = opts[labels.index(st.selectbox(f"{len(opts)} matching files", labels))]
            preview(o)
        else:
            st.warning("Nothing matches. Try another word, or switch to Request.")
    else:
        request = st.text_area("Describe what is wanted",
                               placeholder="e.g. Blender: a brass machine waking up, slow push-in · or · distant closing bell")
    if st.button("Add clip", type="primary", disabled=(o is None and not request.strip()) or not segs):
        start = segs[at_seg][0]
        length = o["duration_s"] if o and o["duration_s"] else (segs[at_seg][1] - start)
        c = dict(id=P["next_id"], lane=lane, start=round(start, 2), end=round(min(start + length, max(TOTAL, start + 0.5)), 2),
                 asset_name=o["name"] if o else "", asset_path=o["path"] if o else "", request=request.strip(),
                 level=1.0 if lane in ("Visual", "Overlay / text", "Voice") else 0.5, pan=0.0,
                 fade_in=0.0, fade_out=0.0, notes="")
        P["clips"].append(c)
        P["next_id"] += 1
        st.session_state.edit_pick = clip_label(c)
        st.rerun()


@st.dialog("Add a segment")
def segment_dialog():
    name = st.text_input("Segment name", f"Segment {len(P['segments']) + 1}")
    dur = st.number_input("Length (s)", 0.5, 1200.0, 20.0, 0.5)
    story = st.text_area("What happens (optional)")
    if st.button("Add segment", type="primary"):
        P["segments"].append(dict(name=name, duration_s=dur, story=story, mood="", narration="", voice="", notes=""))
        set_project(P)
        st.rerun()


# ------------------------------------------------------------------ timeline picture

st.title(P["meta"]["title"] or "Framifold")
st.caption(f"Length {fmt(TOTAL)} of target {fmt(P['meta']['target_length_s'])} · "
           f"{len(P['segments'])} segments · {len(P['clips'])} clips")


LAYOUTS = ["Full screen", "Picture-in-picture, top right", "Picture-in-picture, bottom left", "Centred, small",
           "Left half", "Right half", "Lower third (text bar)"]
SS = st.session_state


def assign_layers():
    """Overlapping clips in a lane stack into layers 1, 2, 3 ... (first free layer wins). All layers play together;
    for pictures, a higher layer is drawn on top of a lower one."""
    counts = {}
    for lane in LANES:
        ends = []
        for c in sorted([c for c in P["clips"] if c["lane"] == lane], key=lambda c: (c["start"], c["id"])):
            for i, e in enumerate(ends):
                if c["start"] >= e - 1e-6:
                    ends[i], c["layer"] = c["end"], i + 1
                    break
            else:
                ends.append(c["end"])
                c["layer"] = len(ends)
        counts[lane] = max(1, len(ends))
    return counts


def row_name(lane, layer, counts):
    return lane if counts[lane] == 1 else f"{lane} {layer}"


def lane_rows(counts):
    rows = ["Segments"]
    for lane in LANES:
        n = range(1, counts[lane] + 1)
        rows += [row_name(lane, i, counts) for i in (reversed(n) if lane in ("Visual", "Overlay / text") else n)]
    return rows


def active_at(t):
    return [c for c in P["clips"] if c["start"] <= t < c["end"]]


def asset_duration(c):
    m = [a for a in ASSETS if a["path"] == c.get("asset_path")]
    return m[0]["duration_s"] if m else None


LAYER_COUNTS = assign_layers()


def timeline_figure(moment):
    fig = go.Figure()
    rows = lane_rows(LAYER_COUNTS)
    for i, (a, b, s) in enumerate(seg_bounds()):
        fig.add_bar(y=["Segments"], x=[b - a], base=[a], orientation="h", marker_color=["#888", "#AAA"][i % 2],
                    customdata=[f"seg{i}"], text=s.get("name") or f"seg {i+1}", textposition="inside",
                    insidetextanchor="middle", hovertext=f"{s.get('name')}<br>{fmt(a)}-{fmt(b)}<br>{s.get('mood') or ''}",
                    hoverinfo="text", showlegend=False)
        fig.add_vline(x=a, line_dash="dot", line_color="#999", line_width=1)
    for r in rows[1:]:  # an invisible marker per row so empty lanes still show
        fig.add_bar(y=[r], x=[0.001], base=[0], orientation="h", marker_color="rgba(0,0,0,0)", hoverinfo="skip", showlegend=False)
    for c in P["clips"]:
        label = c.get("asset_name") or ("REQUEST: " + c.get("request", ""))[:40]
        fig.add_bar(y=[row_name(c["lane"], c["layer"], LAYER_COUNTS)], x=[max(c["end"] - c["start"], 0.15)], base=[c["start"]],
                    orientation="h", marker_color=LANE_COLOURS[c["lane"]], customdata=[c["id"]],
                    opacity=0.35 + 0.65 * min(c.get("level", 1.0), 1.0),
                    marker_pattern_shape="/" if not c.get("asset_path") else "",
                    marker_line=dict(color="white", width=3) if c["id"] == SS.get("editing_id") else None,
                    text=f"#{c['id']} {label}", textposition="inside", insidetextanchor="start",
                    hovertext=f"#{c['id']} {label}<br>{fmt(c['start'])}-{fmt(c['end'])}<br>level {c.get('level', 1):.0%}<br>click to edit",
                    hoverinfo="text", showlegend=False)
    fig.add_vline(x=moment, line_color="#FF4B4B", line_width=2)
    end = max([TOTAL, 1] + [c["end"] for c in P["clips"]])
    if end > TOTAL:
        fig.add_vrect(x0=TOTAL, x1=end, fillcolor="#FF4B4B", opacity=0.12, line_width=0)
    fig.update_layout(barmode="overlay", height=70 + 40 * len(rows), margin=dict(l=10, r=10, t=10, b=30),
                      clickmode="event+select", dragmode=False,
                      xaxis=dict(range=[0, end], title="seconds", dtick=max(1, round(end / 20))),
                      yaxis=dict(categoryorder="array", categoryarray=list(reversed(rows))))
    return fig


bcols = st.columns(len(LANES) + 1)
for col, lane in zip(bcols, LANES):
    if col.button(rf"\+ {lane}", width="stretch", key=f"add_{lane}"):
        add_dialog(lane)
if bcols[-1].button(r"\+ Segment", width="stretch"):
    segment_dialog()

MMAX = float(max(TOTAL, 0.1))
SS.moment = min(float(SS.get("moment", 0.0)), MMAX)
moment = st.slider("Look at a moment (red line): what is on screen and in your ears at this second", 0.0, MMAX,
                   step=0.1, key="moment")
event = st.plotly_chart(timeline_figure(moment), width="stretch", on_select="rerun", selection_mode="points",
                        key=f"tl_{len(P['clips'])}_{TOTAL}")
picked = [p.get("customdata") for p in (event.selection.points if event else [])]
picked = [x[0] if isinstance(x, list) else x for x in picked]
if picked and picked != SS.get("last_pick"):
    SS.last_pick = picked
    hit = [c for c in P["clips"] if c["id"] == picked[0]]
    if hit:
        SS.edit_pick = clip_label(hit[0])

now = sorted(active_at(moment), key=lambda c: (LANES.index(c["lane"]), -c["layer"]))
if now:
    parts = []
    for c in now:
        what = c["asset_name"] or "REQUEST: " + c["request"][:30]
        if c["lane"] in ("Visual", "Overlay / text"):
            parts.append(f"**{c['lane']} layer {c['layer']}**: {what} ({c.get('placement', 'Full screen')}, {c['level']:.0%})")
        else:
            parts.append(f"**{c['lane']} {c['layer']}**: {what} (vol {c['level']:.0%}, at {moment - c['start'] + c.get('trim_in', 0):.1f}s into it)")
    st.markdown(f"At **{fmt(moment)}**: " + " · ".join(parts))
else:
    st.markdown(f"At **{fmt(moment)}**: nothing playing.")
st.caption("Overlapping clips in a lane stack into layers (SFX 1, SFX 2 ...) and all play together. For pictures, the "
           "higher layer covers the lower one unless it is smaller (picture-in-picture) or see-through (opacity below 100%). "
           "Striped = request, fainter = quieter, white outline = the clip being edited, red zone = past the end of the film.")


# ------------------------------------------------------------------ selected clip editor (right under the picture)

def _clip(k):
    return next(c for c in P["clips"] if c["id"] == k)


def _set(c, start, end):
    start = max(0.0, round(start, 2))
    c["start"], c["end"] = start, round(max(end, start + 0.1), 2)


def on_time(k, field, span=None):
    c = _clip(k)
    if field == "start":
        length = c["end"] - c["start"]
        _set(c, SS[f"st_{k}"], SS[f"st_{k}"] + length if SS.get(f"lock_{k}", True) else c["end"])
    elif field == "end":
        _set(c, c["start"], SS[f"en_{k}"])
    elif field == "len":
        _set(c, c["start"], c["start"] + SS[f"ln_{k}"])
    elif field == "rng":
        _set(c, *SS[f"rng_{k}_{span}"])


def on_move(k, how):
    c = _clip(k)
    length = c["end"] - c["start"]
    segs = seg_bounds()
    here = next(((a, b) for a, b, s in segs if a <= c["start"] < b), (0.0, TOTAL))
    if isinstance(how, (int, float)):
        _set(c, c["start"] + how, c["end"] + how)
    elif how == "seg_start":
        _set(c, here[0], here[0] + length)
    elif how == "fit_seg":
        _set(c, *here)
    elif how == "after_prev":
        prev = [x["end"] for x in P["clips"] if x["lane"] == c["lane"] and x["id"] != k and x["start"] < c["start"]]
        if prev:
            _set(c, max(prev), max(prev) + length)
    elif how == "to_end":
        _set(c, c["start"], TOTAL)
    elif how == "file_len":
        d = asset_duration(c)
        if d:
            _set(c, c["start"], c["start"] + d - c.get("trim_in", 0.0))
    elif how == "moment":
        _set(c, SS.get("moment", 0.0), SS.get("moment", 0.0) + length)


if P["clips"]:
    # fixed order (lane, then number): moving a clip must not reshuffle the list under the dropdown
    by_label = {clip_label(c): c for c in sorted(P["clips"], key=lambda c: (LANES.index(c["lane"]), c["id"]))}
    if SS.get("edit_pick") not in by_label:  # label changed (e.g. request text edited): stay on the same clip
        same = [lab for lab, c in by_label.items() if c["id"] == SS.get("editing_id")]
        SS.edit_pick = same[0] if same else next(iter(by_label))
    with st.container(border=True):
        c = by_label[st.selectbox("Editing clip", list(by_label), key="edit_pick")]
        k = c["id"]
        SS.editing_id = k
        for key, f in (("trim_in", 0.0), ("loop", False), ("placement", "Full screen")):
            c.setdefault(key, f)
        span = float(max(TOTAL, c["end"], 1.0))
        SS[f"st_{k}"], SS[f"en_{k}"] = float(c["start"]), float(c["end"])  # keep every timing box in step with the clip
        SS[f"ln_{k}"], SS[f"rng_{k}_{span}"] = round(c["end"] - c["start"], 2), (float(c["start"]), float(c["end"]))
        dur = asset_duration(c)

        st.markdown(f"**Timing** · layer {c['layer']} of the {c['lane']} lane"
                    + (f" · the file is {dur:g} s long" if dur else ""))
        t1, t2, t3, t4 = st.columns([2, 2, 2, 2])
        t1.number_input("Start (s)", 0.0, 7200.0, step=0.1, format="%.2f", key=f"st_{k}", on_change=on_time, args=(k, "start"))
        t2.number_input("End (s)", 0.0, 7200.0, step=0.1, format="%.2f", key=f"en_{k}", on_change=on_time, args=(k, "end"))
        t3.number_input("Length (s)", 0.1, 7200.0, step=0.1, format="%.2f", key=f"ln_{k}", on_change=on_time, args=(k, "len"))
        t4.checkbox("Keep length when moving start", True, key=f"lock_{k}")
        st.slider("Start and end (drag either end)", 0.0, span, step=0.1, key=f"rng_{k}_{span}",
                  on_change=on_time, args=(k, "rng", span))
        n = st.columns(10)
        for col, (lab, how) in zip(n, [("◀ 1s", -1.0), ("◀ 0.1", -0.1), ("0.1 ▶", 0.1), ("1s ▶", 1.0),
                                        ("Start at red line", "moment"), ("Snap to segment start", "seg_start"),
                                        ("Fill segment", "fit_seg"), ("After previous clip", "after_prev"),
                                        ("Run to film end", "to_end"), ("Match file length", "file_len")]):
            col.button(lab, key=f"mv_{how}_{k}", on_click=on_move, args=(k, how), width="stretch",
                       disabled=(how == "file_len" and not dur))
        if c["end"] > TOTAL:
            st.warning(f"This clip runs {c['end'] - TOTAL:.1f} s past the end of the film ({fmt(TOTAL)}). "
                       "Shorten it or lengthen a segment.")

        is_audio = c["lane"] in ("Voice", "SFX", "Music")
        st.markdown("**Source and look**" if not is_audio else "**Source and sound**")
        x1, x2, x3, x4 = st.columns(4)
        c["level"] = x1.slider("Volume" if is_audio else "Brightness / opacity", 0.0, 1.0 if is_audio else 1.5,
                               float(c["level"]), 0.05, key=f"lvl_{k}")
        if is_audio:
            c["pan"] = x2.slider("Pan (left / right)", -1.0, 1.0, float(c["pan"]), 0.1, key=f"pan_{k}")
        else:
            c["placement"] = x2.selectbox("Placement on screen", LAYOUTS, LAYOUTS.index(c["placement"]), key=f"pl_{k}")
        c["fade_in"] = x3.number_input("Fade in (s)", 0.0, 30.0, float(c["fade_in"]), 0.25, key=f"fi_{k}")
        c["fade_out"] = x4.number_input("Fade out (s)", 0.0, 30.0, float(c["fade_out"]), 0.25, key=f"fo_{k}")
        if dur:
            y1, y2 = st.columns(2)
            c["trim_in"] = y1.number_input("Start this far into the file (s)", 0.0, float(dur), float(min(c["trim_in"], dur)),
                                           0.1, key=f"tr_{k}", help="Skip the first part of the file, e.g. a silent lead-in.")
            c["loop"] = y2.checkbox("Loop the file if the clip is longer", c["loop"], key=f"lp_{k}")
            used = c["end"] - c["start"]
            if used > dur - c["trim_in"] + 0.05 and not c["loop"]:
                st.warning(f"The clip is {used:.1f} s but only {dur - c['trim_in']:.1f} s of the file is left after the start "
                           "point. Turn on Loop, use Match file length, or let the agent know what should fill the gap.")
            with st.expander("Preview"):
                preview(next(a for a in ASSETS if a["path"] == c["asset_path"]))
        elif c["asset_path"]:
            with st.expander("Preview"):
                m = [a for a in ASSETS if a["path"] == c["asset_path"]]
                preview(m[0]) if m else st.caption("File not found in the library.")
        else:
            c["request"] = st.text_area("Request", c["request"], key=f"req_{k}")
        c["notes"] = st.text_input("Notes for the agent", c["notes"], key=f"nt_{k}")
        d1, d2 = st.columns([1, 5])
        if d1.button("Apply to picture", type="primary"):
            st.rerun()
        if d2.button("Delete clip"):
            P["clips"] = [x for x in P["clips"] if x["id"] != k]
            SS.pop("edit_pick", None)
            st.rerun()

tab_seg, tab_assets, tab_export = st.tabs(["Segments (story, mood, narration)", "Asset library", "Export for the agent"])

# ------------------------------------------------------------------ segments

with tab_seg:
    st.write("One row per segment, in order. Type in the empty bottom row to add one. Blank boxes are left for the agent to propose.")
    edited = st.data_editor(
        st.session_state.seg_base, key=f"seg_ed_{st.session_state.editor_rev}", num_rows="dynamic",
        width="stretch", hide_index=False,
        column_config={
            "name": st.column_config.TextColumn("Segment", width="small"),
            "duration_s": st.column_config.NumberColumn("Length (s)", min_value=0.5, max_value=1200, step=0.5, default=20.0),
            "story": st.column_config.TextColumn("What happens (story)", width="large"),
            "mood": st.column_config.TextColumn("Mood / theme"),
            "narration": st.column_config.TextColumn("Narration text (blank = agent drafts)", width="large"),
            "voice": st.column_config.TextColumn("Voice"),
            "notes": st.column_config.TextColumn("Notes"),
        })
    new_segs = edited.fillna("").to_dict("records")
    for s in new_segs:
        try:
            s["duration_s"] = float(s["duration_s"] or 0)
        except ValueError:
            s["duration_s"] = 0.0
    if new_segs != P["segments"]:
        P["segments"] = new_segs
        st.rerun()

# ------------------------------------------------------------------ asset library

with tab_assets:
    st.write(f"{len(ASSETS)} files found in: " + ", ".join(f"**{k}**" for k, v in ASSET_ROOTS.items() if v.exists()))
    st.caption(f"Drop new files into {ASSET_ROOTS['Framifold assets']} and they appear here within 5 minutes (or press R).")
    st.dataframe(pd.DataFrame(ASSETS).drop(columns=["path"]) if ASSETS else pd.DataFrame(), width="stretch", height=420)

# ------------------------------------------------------------------ export

def brief():
    m, L = P["meta"], []
    mode = m.get("strictness", "Balanced")
    blank = lambda v: v if str(v).strip() else BLANK_TAG[mode]
    L += [f"# Agent brief: {m['title'] or 'untitled'}", "",
          f"Built from the Framifold rubric. Make the video this describes. **Strictness: {mode}.**",
          *STRICT_RULES[mode],
          "- REQUEST clips: find (Freesound CC0, Wikimedia Commons; log source and licence) or make (Blender, cards) what is described.",
          "- Layers: clips that overlap in time all play together. Sounds mix at their volumes. Pictures stack: "
          "a higher layer covers a lower one unless it is smaller (placement) or see-through (brightness/opacity below 100%).",
          "- Ask James before any ElevenLabs spend, upload, publish or push.",
          "- Report what was done, what was not done, and anything that looks wrong. Never hide a problem.", "",
          "## The whole film",
          f"- Story: {blank(m['logline'])}", f"- Theme: {blank(m['theme'])}", f"- Mood: {blank(m['mood'])}",
          f"- Audience: {blank(m['audience'])}", f"- Target length: {fmt(m['target_length_s'])} (timeline now {fmt(TOTAL)})",
          f"- Voices: {blank(m['voices'])}", f"- Look: {blank(m['look'])}", f"- Rules: {blank(m['rules'])}",
          f"- Notes: {m['notes'] or '-'}", ""]
    for i, (a, b, s) in enumerate(seg_bounds()):
        L += [f"## Segment {i+1}: {s.get('name') or 'unnamed'} ({fmt(a)} to {fmt(b)}, {b - a:g} s)",
              f"- Story: {blank(s.get('story', ''))}", f"- Mood: {blank(s.get('mood', ''))}",
              f"- Narration: {blank(s.get('narration', ''))}", f"- Voice: {blank(s.get('voice', ''))}"]
        if s.get("notes"):
            L.append(f"- Notes: {s['notes']}")
        inside = [c for c in P["clips"] if c["start"] < b and c["end"] > a]
        if inside:
            L.append("- Clips in this segment:")
        for c in sorted(inside, key=lambda c: (LANES.index(c["lane"]), c.get("layer", 1), c["start"])):
            what = f"file {c['asset_path']}" if c["asset_path"] else f"REQUEST: {c['request']}"
            lvl = ("volume" if c["lane"] in ("Voice", "SFX", "Music") else "brightness") + f" {c['level']:.0%}"
            extra = f", pan {c['pan']:+.1f}" if c["lane"] in ("Voice", "SFX", "Music") and c["pan"] else ""
            fades = f", fade in {c['fade_in']}s / out {c['fade_out']}s" if c["fade_in"] or c["fade_out"] else ""
            if c["lane"] in ("Visual", "Overlay / text"):
                extra += f", {c.get('placement', 'Full screen')}"
            if c.get("trim_in"):
                extra += f", start {c['trim_in']:g}s into the file"
            if c.get("loop"):
                extra += ", loop"
            L.append(f"  - #{c['id']} {c['lane']} layer {c.get('layer', 1)} {fmt(c['start'])}-{fmt(c['end'])}: {what} ({lvl}{extra}{fades})"
                     + (f". Note: {c['notes']}" if c["notes"] else ""))
        L.append("")
    return "\n".join(L)


with tab_export:
    st.write("Two exports: the **JSON plan** (exact timings and levels, for the build script) and the **brief** (plain text an agent reads first).")
    b = brief()
    e1, e2 = st.columns(2)
    e1.download_button("Download plan (JSON)", json.dumps(P, indent=2), f"{fname}.json", "application/json", width="stretch")
    e2.download_button("Download brief (Markdown)", b, f"{fname}_brief.md", "text/markdown", width="stretch")
    if st.button("Write both into the projects folder"):
        (PROJECTS / f"{fname}.json").write_text(json.dumps(P, indent=2), encoding="utf-8")
        (PROJECTS / f"{fname}_brief.md").write_text(b, encoding="utf-8")
        st.success(f"Wrote projects/{fname}.json and projects/{fname}_brief.md")
    st.markdown("---")
    st.markdown(b)
