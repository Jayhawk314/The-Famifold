"""Render any Framifold plan (JSON) to a video. The general, method-free half of the agent side.

    python render.py plan.json [out.mp4] [--size 1280x720] [--fps 24]

Files on the timeline are placed exactly as planned: layers, start/end, trim-in, loop, volume or opacity, pan,
fades and placement. REQUEST clips (and files that cannot be found) become stand-ins: a card showing the request
text for pictures, silence for sounds. So a draft cut exists as soon as a plan does. The agent's job is then the
same for every video: replace requests with real files in the plan, and render again.

Writes <out>.mp4 and <out>.report.md (what was placed, what stood in, what was cut or wrong).
Pictures: level 0-1 = opacity (see-through over lower layers), 1-1.5 = brighter. Sounds: level = volume.
A video clip on a picture lane is used for its picture only; put its sound on a sound lane to hear it.
"""
import json, re, subprocess, sys, tempfile, textwrap
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
PICTURE_LANES = ["Visual", "Overlay / text"]
SOUND_LANES = ["Voice", "SFX", "Music"]
LANES = PICTURE_LANES + SOUND_LANES
IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PAD = 40


def duration(path):
    r = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def assign_layers(clips):
    """Same rule as the app: overlapping clips in a lane take the first free layer (1, 2, 3 ...)."""
    for lane in LANES:
        ends = []
        for c in sorted([c for c in clips if c["lane"] == lane], key=lambda c: (c["start"], c["id"])):
            for i, e in enumerate(ends):
                if c["start"] >= e - 1e-6:
                    ends[i], c["layer"] = c["end"], i + 1
                    break
            else:
                ends.append(c["end"])
                c["layer"] = len(ends)


def font(size):
    for f in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def stand_in_card(c, W, H, out, why):
    """A plain card for a picture that does not exist yet, so the draft shows what belongs here."""
    img = Image.new("RGB", (W, H), (24, 28, 38))
    d = ImageDraw.Draw(img)
    d.rectangle((12, 12, W - 12, H - 12), outline=(245, 133, 24), width=4)
    d.text((48, 40), f"#{c['id']} · {c['lane']} layer {c['layer']} · {why}", font=font(H // 28), fill=(245, 133, 24))
    body = c.get("request") or c.get("asset_path") or "(no description)"
    y = H // 4
    for line in textwrap.wrap(body, 44)[:6]:
        d.text((48, y), line, font=font(H // 14), fill=(235, 238, 245))
        y += H // 11
    if c.get("notes"):
        d.text((48, H - H // 7), "Note: " + c["notes"][:90], font=font(H // 30), fill=(160, 168, 185))
    img.save(out)


def placement(c, W, H):
    """Scale filter and overlay position for the clip's placement."""
    p = c.get("placement", "Full screen")
    fit = lambda w, h: f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease"
    fill = lambda w, h: f"scale=w={w}:h={h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    pw, ph = int(W * 0.35) // 2 * 2, int(H * 0.35) // 2 * 2
    return {
        "Picture-in-picture, top right": (fit(pw, ph), f"W-w-{PAD}", f"{PAD}"),
        "Picture-in-picture, bottom left": (fit(pw, ph), f"{PAD}", f"H-h-{PAD}"),
        "Centred, small": (fit(W // 2, H // 2), "(W-w)/2", "(H-h)/2"),
        "Left half": (fill(W // 2, H), "0", "0"),
        "Right half": (fill(W // 2, H), f"{W // 2}", "0"),
        "Lower third (text bar)": (fit(W, H // 3), "(W-w)/2", "H-h"),
    }.get(p, (fill(W, H), "0", "0"))


def render(plan_path, out=None, W=1280, H=720, fps=24):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    out = Path(out) if out else plan_path.with_suffix(".mp4")
    total = round(sum(float(s.get("duration_s") or 0) for s in plan["segments"]), 3)
    if total <= 0:
        sys.exit("The plan has no length: give the segments a length first.")
    clips = [dict(c) for c in plan["clips"]]
    assign_layers(clips)
    tmp = Path(tempfile.mkdtemp(prefix="framifold_"))
    report = dict(placed=[], stood_in=[], trimmed=[], skipped=[])

    inputs, graph = [], []
    graph.append(f"color=c=black:s={W}x{H}:r={fps}:d={total}[base]")
    last = "base"

    # ---------------------------------------------------------------- pictures: lane order, then layer (higher on top)
    pics = sorted([c for c in clips if c["lane"] in PICTURE_LANES],
                  key=lambda c: (PICTURE_LANES.index(c["lane"]), c["layer"], c["start"]))
    for c in pics:
        start, end = max(0.0, c["start"]), min(c["end"], total)
        if end - start < 0.04:
            report["skipped"].append(f"#{c['id']} {c['lane']}: starts at or after the film's end ({total:g} s)")
            continue
        if c["end"] > total:
            report["trimmed"].append(f"#{c['id']} {c['lane']}: cut at the film's end ({c['end']:g} → {total:g} s)")
        length = end - start
        src = Path(c["asset_path"]) if c.get("asset_path") else None
        if not src or not src.exists():
            why = "REQUEST" if not src else "MISSING FILE"
            card = tmp / f"card_{c['id']}.png"
            stand_in_card(c, W, H, card, why)
            src, is_image = card, True
            report["stood_in"].append(f"#{c['id']} {c['lane']} {start:g}-{end:g}s: {why}: {c.get('request') or c.get('asset_path')}")
        else:
            is_image = src.suffix.lower() in IMAGE
            report["placed"].append(f"#{c['id']} {c['lane']} layer {c['layer']} {start:g}-{end:g}s: {src.name}")
        n = inputs.count("-i")  # index of the input about to be added
        if is_image:
            inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{length:.3f}", "-i", str(src)]
        else:
            if c.get("loop"):
                inputs += ["-stream_loop", "-1"]
            inputs += ["-ss", f"{c.get('trim_in', 0) or 0:.3f}", "-t", f"{length:.3f}", "-i", str(src)]
        scale, x, y = placement(c, W, H)
        level = float(c.get("level", 1.0))
        f = [scale, f"fps={fps}", "format=rgba"]
        if level > 1.0:
            f.append(f"eq=brightness={min((level - 1.0) * 0.4, 0.3):.3f}")
        if level < 1.0:
            f.append(f"colorchannelmixer=aa={max(level, 0):.3f}")
        if c.get("fade_in"):
            f.append(f"fade=t=in:st=0:d={c['fade_in']}:alpha=1")
        if c.get("fade_out"):
            f.append(f"fade=t=out:st={max(length - c['fade_out'], 0):.3f}:d={c['fade_out']}:alpha=1")
        f.append(f"setpts=PTS-STARTPTS+{start:.3f}/TB")
        graph.append(f"[{n}:v]{','.join(f)}[p{n}]")
        graph.append(f"[{last}][p{n}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{start:.3f},{end:.3f})'[v{n}]")
        last = f"v{n}"
    graph.append(f"[{last}]format=yuv420p[vout]")

    # ---------------------------------------------------------------- sounds: every clip mixed at its own volume
    mix = []
    for c in sorted([c for c in clips if c["lane"] in SOUND_LANES], key=lambda c: (SOUND_LANES.index(c["lane"]), c["layer"])):
        start, end = max(0.0, c["start"]), min(c["end"], total)
        src = Path(c["asset_path"]) if c.get("asset_path") else None
        if end - start < 0.04:
            report["skipped"].append(f"#{c['id']} {c['lane']}: starts at or after the film's end ({total:g} s)")
            continue
        if not src or not src.exists():
            why = "REQUEST" if not src else "MISSING FILE"
            report["stood_in"].append(f"#{c['id']} {c['lane']} {start:g}-{end:g}s: {why} (silence): {c.get('request') or c.get('asset_path')}")
            continue
        if c["end"] > total:
            report["trimmed"].append(f"#{c['id']} {c['lane']}: cut at the film's end ({c['end']:g} → {total:g} s)")
        length, trim = end - start, float(c.get("trim_in", 0) or 0)
        d = duration(src)
        if d and not c.get("loop") and length > d - trim + 0.05:
            report["trimmed"].append(f"#{c['id']} {c['lane']}: file runs out {d - trim:.1f} s in; silent for the last "
                                     f"{length - (d - trim):.1f} s (turn on Loop or shorten)")
        n = inputs.count("-i")  # index of the input about to be added
        if c.get("loop"):
            inputs += ["-stream_loop", "-1"]
        inputs += ["-i", str(src)]
        pan = float(c.get("pan", 0) or 0)
        gl, gr = min(1.0, 1.0 - pan), min(1.0, 1.0 + pan)
        f = [f"atrim=start={trim:.3f}:duration={length:.3f}", "asetpts=PTS-STARTPTS",
             "aformat=sample_rates=48000:channel_layouts=stereo", f"pan=stereo|c0={gl:.3f}*c0|c1={gr:.3f}*c1",
             f"volume={float(c.get('level', 1.0)):.3f}"]
        if c.get("fade_in"):
            f.append(f"afade=t=in:st=0:d={c['fade_in']}")
        if c.get("fade_out"):
            f.append(f"afade=t=out:st={max(length - c['fade_out'], 0):.3f}:d={c['fade_out']}")
        f.append(f"adelay={int(start * 1000)}:all=1")
        graph.append(f"[{n}:a]{','.join(f)}[a{n}]")
        mix.append(f"[a{n}]")
        report["placed"].append(f"#{c['id']} {c['lane']} {c['layer']} {start:g}-{end:g}s: {src.name} (vol {c.get('level', 1):.0%}, pan {pan:+.1f})")
    if mix:
        graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,apad=whole_dur={total},atrim=0:{total}[aout]")
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{total}[aout]")

    script = tmp / "graph.txt"
    script.write_text(";\n".join(graph), encoding="utf-8")
    cmd = [FF, "-y", "-loglevel", "error", *inputs, "-/filter_complex", str(script), "-map", "[vout]", "-map", "[aout]",
           "-t", f"{total}", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{r.stderr[-3000:]}\n(filter graph kept at {script})")

    got = duration(out)
    title = plan.get("meta", {}).get("title") or plan_path.stem
    lines = [f"# Render report: {title}", "", f"- Output: {out}", f"- Planned length {total:g} s, rendered {got:.2f} s"
             + ("" if got and abs(got - total) < 0.2 else "  **MISMATCH: check this**"),
             f"- {len(report['placed'])} clips placed, {len(report['stood_in'])} stand-ins, "
             f"{len(report['trimmed'])} trimmed or short, {len(report['skipped'])} skipped", ""]
    for k, head in (("stood_in", "Stand-ins (still to find or make)"), ("trimmed", "Cut or running short"),
                    ("skipped", "Skipped"), ("placed", "Placed")):
        if report[k]:
            lines += [f"## {head}", *[f"- {x}" for x in report[k]], ""]
    rep = out.with_suffix(".report.md")
    rep.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:5]))
    print(f"Report: {rep}")
    return out, report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Render a Framifold plan to a video.")
    ap.add_argument("plan")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    W, H = map(int, a.size.split("x"))
    render(a.plan, a.out, W, H, a.fps)
