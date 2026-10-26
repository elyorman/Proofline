"""Assemble the demo video (docs/demo-script.md) into one narrated, captioned file.

The narration is the script's own words, spoken by an Azure AI Speech neural voice through the
environment's AI Services account, with the developer's Entra ID (no keys). Each sentence is
synthesised on its own, so the captions are timed to the audio exactly. The pictures are the
clips `make video-clips` records from the public link, the recovery command's real output in a
terminal frame, the Proofline mark and the architecture picture. The captions are burned in, so
no caption file sits beside the video for a player to load and show twice.

    make video          # runs/video/proofline-demo.mp4
"""

import hashlib
import html
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs" / "video"
VOICE = os.getenv("PROOFLINE_VOICE", "en-GB-OllieMultilingualNeural")
LEAD, GAP, TAIL = 0.35, 0.3, 0.6  # seconds of silence before, between and after sentences
SIZE = "1920:1080"
# Characters that fit one caption line. The installed libass boxes each line of a caption
# separately, so a caption that wrapped showed two boxes of different widths.
LINE = 84

# What each beat of the script shows; its words come from the script itself.
PICTURES = {
    "The gap": ("title", None),
    "A fan's match": ("clip", "01-fan-68"),
    "The investigation": ("clip", "02-investigation"),
    "It corrects itself": ("clip", "03-correction"),
    "It keeps watching": ("clip", "04-followup-83"),
    "It recovers": ("terminal", None),
    "Ask anything, live": ("clip", "05-live-ask"),
    "The proof": ("clip", "06-scoreboard"),
    "How it's built": ("page", ROOT / "docs" / "architecture.html"),
}


@dataclass
class Beat:
    name: str
    sentences: list[str]
    audio: list[Path] = field(default_factory=list)
    lengths: list[float] = field(default_factory=list)

    @property
    def duration(self) -> float:
        spoken = sum(self.lengths) + GAP * (len(self.lengths) - 1)
        return round(LEAD + spoken + TAIL, 3)


def run(*args: str, **kwargs) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


def seconds(path: Path) -> float:
    return float(
        run(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        )
    )


def beats() -> list[Beat]:
    """Each beat's narration, quoted in the script's last column, split into sentences."""
    rows = [
        r
        for r in (ROOT / "docs" / "demo-script.md").read_text().splitlines()
        if re.match(r"\| \d:\d\d", r)
    ]
    out = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        words = " ".join(re.findall(r'"([^"]+)"', cells[-1]))
        out.append(Beat(cells[1], [s for s in re.split(r"(?<=[.!?])\s+", words) if s]))
    missing = [b.name for b in out if b.name not in PICTURES]
    if missing:
        raise SystemExit(f"no picture for beat(s): {', '.join(missing)}")
    return out


class Speech:
    """Azure AI Speech on the environment's AI Services account, signed in with Entra ID."""

    def __init__(self) -> None:
        env = dict(
            line.split("=", 1)
            for line in run("azd", "env", "get-values").splitlines()
            if "=" in line
        )
        env = {k: v.strip('"') for k, v in env.items()}
        self.region = env["AZURE_LOCATION"]
        self.resource = run(
            "az",
            "cognitiveservices",
            "account",
            "list",
            "-g",
            env["AZURE_RESOURCE_GROUP"],
            "--query",
            "[?kind=='AIServices'].id | [0]",
            "-o",
            "tsv",
        ).strip()
        self.credential = DefaultAzureCredential()

    def say(self, text: str, cache: Path) -> Path:
        target = cache / f"{hashlib.sha1(f'{VOICE}|{text}'.encode()).hexdigest()[:16]}.wav"
        if target.exists():
            return target
        token = self.credential.get_token("https://cognitiveservices.azure.com/.default").token
        ssml = (
            f"<speak version='1.0' xml:lang='en-GB'><voice name='{VOICE}'>"
            f"{html.escape(text)}</voice></speak>"
        )
        reply = httpx.post(
            f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
            content=ssml.encode(),
            headers={
                "Authorization": f"Bearer aad#{self.resource}#{token}",
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm",
                "User-Agent": "proofline-video",
            },
            timeout=60,
        )
        reply.raise_for_status()
        target.write_bytes(reply.content)
        return target


def snap(page: Path | str, png: Path) -> Path:
    url = page if isinstance(page, str) else page.as_uri()
    run(
        "node",
        "--experimental-websocket",
        str(ROOT / "surfaces/web/scripts/snap.mjs"),
        url,
        str(png),
    )
    return png


FRAME = """<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin: 0; width: 1920px; height: 1080px; background: #13261e; color: #eef4ea;
  font-family: "DejaVu Sans", "Segoe UI", sans-serif; display: flex; flex-direction: column;
  justify-content: center; padding: 0 150px; box-sizing: border-box; }}
h1 {{ font: 400 76px Georgia, serif; margin: 0 0 30px; letter-spacing: -1px; }}
h1.dim {{ color: #6f8a7b; }} p {{ font-size: 34px; color: #d7ec9c; margin: 0; }}
.mark {{ position: absolute; left: 150px; top: 110px; font: 600 30px "DejaVu Sans";
  color: #d7ec9c; }}
.mark.big {{ position: static; align-self: center; font-size: 132px; letter-spacing: -3px; }}
.eyebrow {{ font: 600 24px "DejaVu Sans"; letter-spacing: 4px; text-transform: uppercase;
  color: #d7ec9c; margin: 0 0 24px; }}
pre {{ font: 21px/1.55 "DejaVu Sans Mono", monospace; color: #dbe7d6; white-space: pre-wrap;
  margin: 0; }}
.term {{ background: #0c1712; border-radius: 14px; padding: 40px 46px;
  box-shadow: 0 20px 60px #0008; }}
.prompt {{ color: #d7ec9c; }} .hl {{ color: #ffd479; }} .dim {{ color: #7c9486; }}
</style></head><body>{body}</body></html>"""


def title_frames(work: Path) -> list[Path]:
    """The mark alone: the captions carry the opening lines, so the card does not repeat them."""
    page = work / "title.html"
    page.write_text(FRAME.format(body='<div class="mark big">proofline&#8599;</div>'))
    return [snap(page, work / "title.png")]


def terminal_frames(work: Path) -> list[Path]:
    """The recovery command and its real output, selected lines, from the demo take's recordings."""
    command = (
        "uv run proofline case --match m01 --minute 63 --variant A "
        "--kill-agent physical --replay tests/fixtures/studio/m01"
    )
    data = ROOT / "data" / "m01"
    if not data.exists():
        run(
            "uv",
            "run",
            "proofline-engine",
            "generate",
            "--script",
            "engine/scripts/planted/m01.yaml",
            "--out",
            "data/m01/",
            cwd=ROOT,
        )
    output = run(*command.split(), cwd=ROOT).splitlines()
    keep = ("hypotheses,", "checkpoint", "recovered_from_checkpoint", "card ins-")
    lines, seen_claim = [], False
    for line in output:
        if any(k in line for k in keep):
            lines.append(line)
        elif "casual/en" in line and not seen_claim:
            lines.append(line)
            seen_claim = True

    def shown(line: str) -> str:
        text = html.escape(line if len(line) <= 118 else line[:117] + "…")
        if "failed" in line or "recovered" in line:
            return f'<span class="hl">{text}</span>'
        return text

    prompt = f'<span class="prompt">$</span> {html.escape(command)}'
    out = []
    full = prompt + "\n" + "\n".join(map(shown, lines))
    for name, body in (("terminal-a", prompt), ("terminal-b", full)):
        page = work / f"{name}.html"
        # The stopped agent is the test itself; the label keeps its output from reading as a crash.
        label = '<div class="eyebrow">Recovery test</div>'
        page.write_text(FRAME.format(body=f'{label}<div class="term"><pre>{body}</pre></div>'))
        out.append(snap(page, work / f"{name}.png"))
    return out


def still_video(pngs: list[Path], duration: float, target: Path) -> None:
    """One or two stills; with two, the second fades in a third of the way through."""
    frames = int(duration * 30) + 30
    zoom = (  # a slow push in, centred, never past 2.5%
        "scale=1980:-2,zoompan=z='min(zoom+0.0002,1.025)':x='iw/2-(iw/zoom/2)'"
        f":y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps=30"
    )
    if len(pngs) == 1:
        run(
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-i",
            str(pngs[0]),
            "-t",
            f"{duration}",
            "-vf",
            zoom,
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            str(target),
        )
        return
    switch = max(1.2, duration / 3)
    run(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-t",
        f"{duration}",
        "-i",
        str(pngs[0]),
        "-loop",
        "1",
        "-t",
        f"{duration}",
        "-i",
        str(pngs[1]),
        "-filter_complex",
        f"[1]format=rgba,fade=t=in:st={switch:.2f}:d=0.6:alpha=1[b];[0][b]overlay,fps=30,format=yuv420p",
        "-t",
        f"{duration}",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        str(target),
    )


def clip_video(clip: Path, duration: float, target: Path) -> None:
    """The clip fitted to the beat: sped up when longer, its last frame held when shorter."""
    length = seconds(clip)
    factor = min(1.0, duration / length)
    hold = max(0.0, duration - length * factor)
    run(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(clip),
        "-vf",
        f"setpts={factor:.4f}*PTS,fps=30,scale={SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={SIZE}:(ow-iw)/2:(oh-ih)/2,tpad=stop_mode=clone:stop_duration={hold:.2f},format=yuv420p",
        "-t",
        f"{duration}",
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        str(target),
    )


def narration(beat: Beat, target: Path) -> None:
    parts, inputs = [], []
    for i, wav in enumerate(beat.audio):
        inputs += ["-i", str(wav)]
        parts.append(f"[{i}]adelay={int(1000 * (LEAD + sum(beat.lengths[:i]) + GAP * i))}|0[a{i}]")
    mix = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(beat.audio)))
    mix += f"amix=inputs={len(beat.audio)}:normalize=0,apad=whole_dur={beat.duration}[out]"
    run(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        *inputs,
        "-filter_complex",
        mix,
        "-map",
        "[out]",
        "-t",
        f"{beat.duration}",
        "-ar",
        "48000",
        "-ac",
        "2",
        str(target),
    )


def lines(text: str) -> list[str]:
    """Text in pieces that each fit one caption line: broken at the clause nearest its middle,
    else before the nearest "and" or "than", else at the nearest word."""
    if len(text) <= LINE:
        return [text]
    for pattern in (r"[,;:] ", r" (?=(?:and|than) )", r" "):
        cuts = [m.end() for m in re.finditer(pattern, text) if 12 <= m.end() <= len(text) - 12]
        if cuts:
            cut = min(cuts, key=lambda i: abs(i - len(text) / 2))
            return lines(text[:cut].strip()) + lines(text[cut:].strip())
    return [text]


def stamp(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> int:
    clips = OUT
    work = OUT / "build"
    cache = OUT / "tts"
    for folder in (work, cache):
        folder.mkdir(parents=True, exist_ok=True)
    script = beats()
    speech = Speech()
    for beat in script:
        beat.audio = [speech.say(s, cache) for s in beat.sentences]
        beat.lengths = [seconds(w) for w in beat.audio]
    segments, captions, start = [], [], 0.0
    title, terminal = title_frames(work), terminal_frames(work)
    for n, beat in enumerate(script):
        kind, source = PICTURES[beat.name]
        picture, voice, segment = work / f"{n}-v.mp4", work / f"{n}-a.wav", work / f"{n}.mp4"
        if kind == "clip":
            clip = clips / f"{source}.mp4"
            if not clip.exists():
                raise SystemExit(f"{clip} is missing: run make video-clips first")
            clip_video(clip, beat.duration, picture)
        elif kind == "page":
            still_video([snap(source, work / f"{n}.png")], beat.duration, picture)
        else:
            still_video(title if kind == "title" else terminal, beat.duration, picture)
        narration(beat, voice)
        run(
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(picture),
            "-i",
            str(voice),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(segment),
        )
        at = start + LEAD
        for sentence, length in zip(beat.sentences, beat.lengths, strict=True):
            pieces = lines(sentence)  # each on screen for its share of the sentence's speech
            for piece in pieces:
                span = length * len(piece) / sum(map(len, pieces))
                captions.append((at, at + span, piece))
                at += span
            at += GAP
        segments.append(segment)
        start += beat.duration
        print(f"{beat.name:22s} {beat.duration:5.1f}s ({kind})")
    joined = work / "joined.mp4"
    (work / "segments.txt").write_text("".join(f"file '{s}'\n" for s in segments))
    run(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(work / "segments.txt"),
        "-c",
        "copy",
        str(joined),
    )
    srt = work / "captions.srt"
    cues = enumerate(captions, 1)
    srt.write_text(
        "".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n" for i, (a, b, text) in cues)
    )
    style = (
        "FontName=DejaVu Sans,FontSize=11,PrimaryColour=&H00FFFFFF,BackColour=&H99101A15,"
        "BorderStyle=3,Outline=6,Shadow=0,MarginV=26"
    )
    final = OUT / "proofline-demo.mp4"
    run(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(joined),
        "-vf",
        f"subtitles={srt}:force_style='{style}'",
        "-c:a",
        "copy",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        str(final),
    )
    (OUT / "proofline-demo.json").write_text(
        json.dumps(
            {
                "voice": VOICE,
                "seconds": round(start, 1),
                "beats": [{"beat": b.name, "seconds": b.duration} for b in script],
            },
            indent=1,
        )
        + "\n"
    )
    print(f"{final}: {start:.1f} s, captions burned in")
    return 0 if start <= 120 else 1


if __name__ == "__main__":
    sys.exit(main())
