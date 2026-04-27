"""
VeoVision web server with:
- range-aware static video serving
- sample discovery APIs
- upload + model-run APIs (background jobs)
"""

from __future__ import annotations

import cgi
import http.server
import json
import os
import shutil
import socketserver
import sys
import threading
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
VEO_PROJECT_DIR = REPO_ROOT / "veo_project"

for path in (REPO_ROOT, TOOLS_DIR, VEO_PROJECT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

REGULAR_SAMPLE_DIR = REPO_ROOT / "regular_clips" / "sample_content"
REGULAR_DATA_DIR = REPO_ROOT / "regular_clips" / "data_content"
FAMOUS_SAMPLE_DIR = REPO_ROOT / "famous_clips" / "sample_content"
FAMOUS_DATA_DIR = REPO_ROOT / "famous_clips" / "data_content"
UPLOADED_SAMPLE_DIR = REPO_ROOT / "uploaded_clips" / "sample_content"
UPLOADED_DATA_DIR = REPO_ROOT / "uploaded_clips" / "data_content"

CLIP_BUCKETS = {
    "regular": {"sample": REGULAR_SAMPLE_DIR, "data": REGULAR_DATA_DIR},
    "famous": {"sample": FAMOUS_SAMPLE_DIR, "data": FAMOUS_DATA_DIR},
    "uploaded": {"sample": UPLOADED_SAMPLE_DIR, "data": UPLOADED_DATA_DIR},
}


@dataclass
class JobState:
    id: str
    category: str
    clip_id: str
    source_video_path: str
    status: str = "queued"  # queued, running, done, failed
    stage: str = "queued"
    progress: int = 0
    message: str = ""
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error: Optional[str] = None
    outputs: Dict[str, str] = field(default_factory=dict)
    run_mode: str = "full"  # full, missing, stats, pitch2d, heatmap, ball


JOBS: Dict[str, JobState] = {}
JOBS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _safe_name(name: str) -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in {"_", "-", "."}:
            keep.append(ch)
        else:
            keep.append("_")
    cleaned = "".join(keep).strip("._")
    return cleaned or "uploaded_clip"


def _clip_outputs(bucket: str, clip_id: str) -> Dict[str, Path]:
    data_dir = CLIP_BUCKETS[bucket]["data"]
    return {
        "combined": data_dir / f"{clip_id}_combined_result.mp4",
        "combined_browser": data_dir / f"{clip_id}_combined_result_browser.mp4",
        "pitch2d": data_dir / f"{clip_id}_2d_pitch.mp4",
        "pitch2d_browser": data_dir / f"{clip_id}_2d_pitch_browser.mp4",
        "heatmap": data_dir / f"{clip_id}_combined_pitch_heatmap.mp4",
        "heatmap_browser": data_dir / f"{clip_id}_combined_pitch_heatmap_browser.mp4",
        "ball": data_dir / f"{clip_id}_ball_tracking.mp4",
        "ball_browser": data_dir / f"{clip_id}_ball_tracking_browser.mp4",
        "stats_json": data_dir / f"{clip_id}_match_stats.json",
        "stats_csv": data_dir / f"{clip_id}_match_stats.csv",
    }


def _stage_ready(outputs: Dict[str, Path], stage: str) -> bool:
    if stage == "combined":
        return outputs["combined_browser"].exists() or outputs["combined"].exists()
    if stage == "pitch2d":
        return outputs["pitch2d_browser"].exists() or outputs["pitch2d"].exists()
    if stage == "heatmap":
        return outputs["heatmap_browser"].exists() or outputs["heatmap"].exists()
    if stage == "ball":
        return outputs["ball_browser"].exists() or outputs["ball"].exists()
    if stage == "stats":
        return outputs["stats_json"].exists() and outputs["stats_csv"].exists()
    return False


def _missing_stages(outputs: Dict[str, Path]) -> List[str]:
    ordered = ["combined", "pitch2d", "heatmap", "ball", "stats"]
    return [stage for stage in ordered if not _stage_ready(outputs, stage)]


def _ensure_browser_version(source_path: Path, browser_path: Path, converter) -> None:
    if browser_path.exists():
        return
    if source_path.exists():
        converter(source_path, browser_path)


def _migrate_legacy_uploaded_clips() -> None:
    uploaded_sample_dir = CLIP_BUCKETS["uploaded"]["sample"]
    uploaded_data_dir = CLIP_BUCKETS["uploaded"]["data"]
    uploaded_sample_dir.mkdir(parents=True, exist_ok=True)
    uploaded_data_dir.mkdir(parents=True, exist_ok=True)

    for legacy_bucket in ("regular", "famous"):
        legacy_sample_dir = CLIP_BUCKETS[legacy_bucket]["sample"]
        legacy_sample_dir.mkdir(parents=True, exist_ok=True)
        legacy_data_dir = CLIP_BUCKETS[legacy_bucket]["data"]
        legacy_data_dir.mkdir(parents=True, exist_ok=True)

        for sample_file in legacy_sample_dir.glob("*_uploaded_*.mp4"):
            clip_id = sample_file.stem
            target_sample = uploaded_sample_dir / sample_file.name
            if sample_file.exists() and not target_sample.exists():
                shutil.move(str(sample_file), str(target_sample))

            legacy_outputs = _clip_outputs(legacy_bucket, clip_id)
            uploaded_outputs = _clip_outputs("uploaded", clip_id)
            for key, legacy_path in legacy_outputs.items():
                target_path = uploaded_outputs[key]
                if legacy_path.exists() and not target_path.exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(legacy_path), str(target_path))


def _discover_bucket(bucket: str) -> Dict[str, Any]:
    sample_dir = CLIP_BUCKETS[bucket]["sample"]
    sample_dir.mkdir(parents=True, exist_ok=True)
    CLIP_BUCKETS[bucket]["data"].mkdir(parents=True, exist_ok=True)

    clips: List[Dict[str, Any]] = []
    for sample_file in sorted(sample_dir.glob("*.mp4")):
        clip_id = sample_file.stem
        outputs = _clip_outputs(bucket, clip_id)
        missing = _missing_stages(outputs)
        has_combined = _stage_ready(outputs, "combined")
        has_2d = _stage_ready(outputs, "pitch2d")
        has_heatmap = _stage_ready(outputs, "heatmap")
        has_ball = _stage_ready(outputs, "ball")
        has_stats = _stage_ready(outputs, "stats")
        clips.append(
            {
                "id": clip_id,
                "name": clip_id.replace("_", " "),
                "sampleVideo": sample_file.as_posix().replace(str(REPO_ROOT).replace("\\", "/") + "/", ""),
                "hasCombined": has_combined,
                "has2D": has_2d,
                "hasHeatmap": has_heatmap,
                "hasBall": has_ball,
                "hasStats": has_stats,
                "isComplete": len(missing) == 0,
                "missingOutputs": missing,
                "updatedAt": datetime.fromtimestamp(sample_file.stat().st_mtime).isoformat(),
            }
        )
    return {"category": bucket, "clips": clips}


def discover_samples() -> Dict[str, Any]:
    _migrate_legacy_uploaded_clips()
    return {
        "regular": _discover_bucket("regular")["clips"],
        "famous": _discover_bucket("famous")["clips"],
        "uploaded": _discover_bucket("uploaded")["clips"],
        "jobs": [asdict(job) for job in JOBS.values()],
    }


def _set_job(job_id: str, **kwargs: Any) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        for key, value in kwargs.items():
            setattr(job, key, value)


def _find_active_job_for_clip(category: str, clip_id: str) -> Optional[JobState]:
    with JOBS_LOCK:
        for job in JOBS.values():
            if job.category == category and job.clip_id == clip_id and job.status in {"queued", "running"}:
                return job
    return None


def _run_pipeline_job(job_id: str) -> None:
    try:
        from tools.convert_videos_for_browser import convert_video_to_browser_compatible
        from veo_project.batch_process_all import process_ball_tracking
        from veo_project.veo_scripts.combined_pitch_heatmap import process_video_combined
        from veo_project.veo_scripts.match_stats_collection import collect_match_stats
        from veo_project.veo_scripts.pitch_2d_visualization import process_video_2d_pitch
        from veo_project.veo_scripts.video_processing_combined import process_video

        with JOBS_LOCK:
            job = JOBS[job_id]
            source_path = job.source_video_path
            bucket = job.category
            clip_id = job.clip_id
            run_mode = job.run_mode

        outputs = _clip_outputs(bucket, clip_id)
        api_key = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
        _set_job(job_id, status="running", started_at=_now_iso(), stage="planning", progress=3, message="Planning pipeline stages")

        if run_mode == "stats":
            stages_to_run = ["stats"]
        elif run_mode == "pitch2d":
            stages_to_run = ["pitch2d"]
        elif run_mode == "heatmap":
            stages_to_run = ["heatmap"]
        elif run_mode == "ball":
            stages_to_run = ["ball"]
        elif run_mode == "missing":
            stages_to_run = _missing_stages(outputs)
        else:
            stages_to_run = ["combined", "pitch2d", "heatmap", "ball", "stats"]

        if not stages_to_run:
            _set_job(
                job_id,
                status="done",
                stage="done",
                progress=100,
                ended_at=_now_iso(),
                message="Already complete. Nothing missing.",
                outputs={k: str(v.relative_to(REPO_ROOT)).replace("\\", "/") for k, v in outputs.items() if v.exists()},
            )
            return

        stage_progress = {
            "combined": 10,
            "pitch2d": 30,
            "heatmap": 50,
            "ball": 70,
            "stats": 85,
        }

        for stage in stages_to_run:
            if stage == "combined":
                _set_job(job_id, stage="combined", progress=stage_progress[stage], message="Running combined detection")
                process_video(source_video_path=source_path, target_video_path=str(outputs["combined"]), roboflow_api_key=api_key)
                convert_video_to_browser_compatible(outputs["combined"], outputs["combined_browser"])
            elif stage == "pitch2d":
                _set_job(job_id, stage="pitch2d", progress=stage_progress[stage], message="Running 2D tactical view")
                process_video_2d_pitch(source_video_path=source_path, target_video_path=str(outputs["pitch2d"]), roboflow_api_key=api_key)
                convert_video_to_browser_compatible(outputs["pitch2d"], outputs["pitch2d_browser"])
            elif stage == "heatmap":
                _set_job(job_id, stage="heatmap", progress=stage_progress[stage], message="Running combined heatmap")
                process_video_combined(source_video_path=source_path, target_video_path=str(outputs["heatmap"]), roboflow_api_key=api_key)
                convert_video_to_browser_compatible(outputs["heatmap"], outputs["heatmap_browser"])
            elif stage == "ball":
                _set_job(job_id, stage="ball", progress=stage_progress[stage], message="Running ball tracking")
                process_ball_tracking(source_path=source_path, target_path=str(outputs["ball"]), roboflow_api_key=api_key)
                convert_video_to_browser_compatible(outputs["ball"], outputs["ball_browser"])
            elif stage == "stats":
                _set_job(job_id, stage="stats", progress=stage_progress[stage], message="Collecting match stats")
                collect_match_stats(
                    source_video_path=source_path,
                    output_json_path=str(outputs["stats_json"]),
                    output_csv_path=str(outputs["stats_csv"]),
                    roboflow_api_key=api_key,
                )

        # In missing mode, generate browser versions from existing outputs if needed.
        if run_mode == "missing":
            _ensure_browser_version(outputs["combined"], outputs["combined_browser"], convert_video_to_browser_compatible)
            _ensure_browser_version(outputs["pitch2d"], outputs["pitch2d_browser"], convert_video_to_browser_compatible)
            _ensure_browser_version(outputs["heatmap"], outputs["heatmap_browser"], convert_video_to_browser_compatible)
            _ensure_browser_version(outputs["ball"], outputs["ball_browser"], convert_video_to_browser_compatible)

        _set_job(
            job_id,
            status="done",
            stage="done",
            progress=100,
            ended_at=_now_iso(),
            message="Completed",
            outputs={k: str(v.relative_to(REPO_ROOT)).replace("\\", "/") for k, v in outputs.items() if v.exists()},
        )
    except Exception as exc:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            ended_at=_now_iso(),
            error=f"{exc}\n{traceback.format_exc()}",
            message="Pipeline failed",
        )


def start_processing_job(
    category: str,
    clip_id: str,
    source_path: Path,
    run_mode: str = "full",
) -> JobState:
    job_id = uuid.uuid4().hex[:12]
    job = JobState(
        id=job_id,
        category=category,
        clip_id=clip_id,
        source_video_path=str(source_path),
        status="queued",
        stage="queued",
        progress=0,
        message="Queued",
        run_mode=run_mode,
    )
    with JOBS_LOCK:
        JOBS[job_id] = job

    thread = threading.Thread(target=_run_pipeline_job, args=(job_id,), daemon=True)
    thread.start()
    return job


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with range support and JSON APIs."""

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _stream_jobs_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            while True:
                with JOBS_LOCK:
                    jobs = [asdict(job) for job in JOBS.values()]
                payload = json.dumps({"jobs": jobs})
                self.wfile.write(f"event: jobs\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                threading.Event().wait(1.5)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self):
        parsed = urlparse(self.path)
        self.range_from = None
        self.range_to = None

        if parsed.path == "/api/samples":
            self._send_json(200, discover_samples())
            return
        if parsed.path == "/api/jobs/stream":
            self._stream_jobs_sse()
            return
        if parsed.path.startswith("/api/jobs"):
            with JOBS_LOCK:
                jobs = [asdict(job) for job in JOBS.values()]
            self._send_json(200, {"jobs": jobs})
            return

        if "Range" in self.headers:
            try:
                range_header = self.headers["Range"]
                range_match = range_header.replace("bytes=", "").split("-")
                self.range_from = int(range_match[0])
                self.range_to = int(range_match[1]) if range_match[1] else None
            except Exception:
                self.range_from = None
                self.range_to = None

        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path in {
            "/api/run",
            "/api/run_missing",
            "/api/run_stats",
            "/api/run_pitch2d",
            "/api/run_heatmap",
            "/api/run_ball",
        }:
            try:
                data = self._read_json_body()
                category = data.get("category", "regular")
                clip_id = data.get("id")
                if category not in CLIP_BUCKETS:
                    self._send_json(400, {"error": "Invalid category"})
                    return
                if not clip_id:
                    self._send_json(400, {"error": "Missing id"})
                    return
                source = CLIP_BUCKETS[category]["sample"] / f"{clip_id}.mp4"
                if not source.exists():
                    self._send_json(404, {"error": "Sample video not found"})
                    return
                active = _find_active_job_for_clip(category=category, clip_id=clip_id)
                if active is not None:
                    self._send_json(
                        409,
                        {
                            "error": "A processing job for this clip is already queued or running.",
                            "job": asdict(active),
                        },
                    )
                    return
                run_mode = "full"
                if parsed.path == "/api/run_missing":
                    run_mode = "missing"
                elif parsed.path == "/api/run_stats":
                    run_mode = "stats"
                elif parsed.path == "/api/run_pitch2d":
                    run_mode = "pitch2d"
                elif parsed.path == "/api/run_heatmap":
                    run_mode = "heatmap"
                elif parsed.path == "/api/run_ball":
                    run_mode = "ball"
                job = start_processing_job(
                    category=category,
                    clip_id=clip_id,
                    source_path=source,
                    run_mode=run_mode,
                )
                self._send_json(202, {"job": asdict(job)})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if parsed.path == "/api/upload":
            try:
                content_type = self.headers.get("Content-Type", "")
                if not content_type.startswith("multipart/form-data"):
                    self._send_json(400, {"error": "Expected multipart/form-data"})
                    return

                fs = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
                )
                # All user uploads go to dedicated uploaded bucket.
                category = "uploaded"

                if "video" not in fs:
                    self._send_json(400, {"error": "Missing video file"})
                    return

                file_item = fs["video"]
                if not getattr(file_item, "filename", None):
                    self._send_json(400, {"error": "Invalid file"})
                    return

                original_name = _safe_name(Path(file_item.filename).name)
                stem = _safe_name(Path(original_name).stem)
                clip_id = f"{stem}_uploaded_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                output_path = CLIP_BUCKETS[category]["sample"] / f"{clip_id}.mp4"
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "wb") as out:
                    out.write(file_item.file.read())

                job = start_processing_job(category=category, clip_id=clip_id, source_path=output_path)
                self._send_json(
                    202,
                    {
                        "job": asdict(job),
                        "clip": {"id": clip_id, "category": category, "sampleVideo": str(output_path.relative_to(REPO_ROOT)).replace("\\", "/")},
                    },
                )
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        self._send_json(404, {"error": "Not found"})

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return http.server.SimpleHTTPRequestHandler.send_head(self)
        try:
            f = open(path, "rb")
        except OSError:
            return http.server.SimpleHTTPRequestHandler.send_head(self)

        fs = os.fstat(f.fileno())
        file_len = fs.st_size

        if self.range_from is not None:
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            if self.range_to is None or self.range_to >= file_len:
                self.range_to = file_len - 1
            self.send_header("Content-Range", f"bytes {self.range_from}-{self.range_to}/{file_len}")
            self.send_header("Content-Length", str(self.range_to - self.range_from + 1))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            f.seek(self.range_from)
            return f

        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(file_len))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        try:
            shutil.copyfileobj(source, outputfile)
        except (ConnectionResetError, BrokenPipeError):
            # Browser cancelled/closed the stream early; expected in scrubbing/seek flows.
            return


def run_server(port: int = 5600) -> None:
    handler = RangeRequestHandler
    with ThreadingTCPServer(("", port), handler) as httpd:
        print("========================================")
        print("  VeoVision Dashboard Server")
        print("========================================")
        print(f"Server running at: http://localhost:{port}")
        print(f"Dashboard: http://localhost:{port}/veo_frontend/")
        print(
            "API endpoints: /api/samples, /api/run, /api/run_missing, /api/run_stats, "
            "/api/run_pitch2d, /api/run_heatmap, /api/run_ball, /api/upload, /api/jobs, /api/jobs/stream"
        )
        print("Press Ctrl+C to stop")
        print("========================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    if not os.path.exists("veo_frontend"):
        print("ERROR: Please run this script from the VeoVision repository (veo_frontend missing).")
        print("Current directory:", os.getcwd())
        raise SystemExit(1)
    run_server(5600)
