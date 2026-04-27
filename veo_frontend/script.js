const GITHUB_PROJECT_URL = "https://github.com/MoLCFC/VeoVision2.0";
const CATEGORIES = ["regular", "famous", "uploaded"];

const state = {
    samples: { regular: [], famous: [], uploaded: [] },
    jobs: [],
    activeClip: null,
    syncLock: false,
    statsFinal: null,
    statsTimeline: null,
    events: [],
    statsPaths: null,
    jobsStreamConnected: false,
    lastSamplesRefreshMs: 0,
};

const refs = {
    regularGrid: document.getElementById("regularGrid"),
    famousGrid: document.getElementById("famousGrid"),
    uploadedGrid: document.getElementById("uploadedGrid"),
    activeClipLabel: document.getElementById("activeClipLabel"),
    jobsList: document.getElementById("jobsList"),
    eventsBody: document.getElementById("eventsBody"),
    uploadInput: document.getElementById("uploadInput"),
    playAllBtn: document.getElementById("playAllBtn"),
    pauseAllBtn: document.getElementById("pauseAllBtn"),
    restartAllBtn: document.getElementById("restartAllBtn"),
    runPipelineBtn: document.getElementById("runPipelineBtn"),
    runMissingBtn: document.getElementById("runMissingBtn"),
    runStatsOnlyBtn: document.getElementById("runStatsOnlyBtn"),
    run2dOnlyBtn: document.getElementById("run2dOnlyBtn"),
    runHeatmapOnlyBtn: document.getElementById("runHeatmapOnlyBtn"),
    runBallOnlyBtn: document.getElementById("runBallOnlyBtn"),
    githubLink: document.getElementById("githubLink"),
    mainVideo: document.getElementById("mainVideo"),
    mainFallback: document.getElementById("mainFallback"),
    pitch2dVideo: document.getElementById("pitch2dVideo"),
    heatmapVideo: document.getElementById("heatmapVideo"),
    ballVideo: document.getElementById("ballVideo"),
    pitch2dFallback: document.getElementById("pitch2dFallback"),
    heatmapFallback: document.getElementById("heatmapFallback"),
    ballFallback: document.getElementById("ballFallback"),
    possessionTeam0: document.getElementById("possessionTeam0"),
    possessionTeam1: document.getElementById("possessionTeam1"),
    passesTotal: document.getElementById("passesTotal"),
    shotsTotal: document.getElementById("shotsTotal"),
    shotsOnTargetTotal: document.getElementById("shotsOnTargetTotal"),
    turnoversTotal: document.getElementById("turnoversTotal"),
    interceptionsTotal: document.getElementById("interceptionsTotal"),
    team0Breakdown: document.getElementById("team0Breakdown"),
    team1Breakdown: document.getElementById("team1Breakdown"),
    team0Insights: document.getElementById("team0Insights"),
    team1Insights: document.getElementById("team1Insights"),
    exportJsonBtn: document.getElementById("exportJsonBtn"),
    exportCsvBtn: document.getElementById("exportCsvBtn"),
    exportReportBtn: document.getElementById("exportReportBtn"),
    mainFullscreenBtn: document.getElementById("mainFullscreenBtn"),
    pitch2dFullscreenBtn: document.getElementById("pitch2dFullscreenBtn"),
    heatmapFullscreenBtn: document.getElementById("heatmapFullscreenBtn"),
    ballFullscreenBtn: document.getElementById("ballFullscreenBtn"),
};

document.addEventListener("DOMContentLoaded", () => {
    refs.githubLink.href = GITHUB_PROJECT_URL;
    attachControls();
    attachSyncEvents();
    refreshSamples();
    connectJobsStream();
    pollJobs();
});

function attachControls() {
    refs.playAllBtn.addEventListener("click", playAll);
    refs.pauseAllBtn.addEventListener("click", pauseAll);
    refs.restartAllBtn.addEventListener("click", restartAll);
    refs.runPipelineBtn.addEventListener("click", runPipelineForActiveClip);
    refs.runMissingBtn.addEventListener("click", runMissingForActiveClip);
    refs.runStatsOnlyBtn.addEventListener("click", runStatsOnlyForActiveClip);
    refs.run2dOnlyBtn.addEventListener("click", run2dOnlyForActiveClip);
    refs.runHeatmapOnlyBtn.addEventListener("click", runHeatmapOnlyForActiveClip);
    refs.runBallOnlyBtn.addEventListener("click", runBallOnlyForActiveClip);
    refs.uploadInput.addEventListener("change", uploadAndRun);
    refs.exportJsonBtn.addEventListener("click", exportJson);
    refs.exportCsvBtn.addEventListener("click", exportCsv);
    refs.exportReportBtn.addEventListener("click", exportReport);
    refs.mainFullscreenBtn.addEventListener("click", () => openVideoFullscreen(refs.mainVideo));
    refs.pitch2dFullscreenBtn.addEventListener("click", () => openVideoFullscreen(refs.pitch2dVideo));
    refs.heatmapFullscreenBtn.addEventListener("click", () => openVideoFullscreen(refs.heatmapVideo));
    refs.ballFullscreenBtn.addEventListener("click", () => openVideoFullscreen(refs.ballVideo));
}

function attachSyncEvents() {
    const followerVideos = [refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo];

    refs.mainVideo.addEventListener("play", () => {
        if (state.syncLock) return;
        followerVideos.forEach((video) => {
            if (video.src) video.play().catch(() => {});
        });
    });

    refs.mainVideo.addEventListener("pause", () => {
        if (state.syncLock) return;
        followerVideos.forEach((video) => video.pause());
    });

    refs.mainVideo.addEventListener("ratechange", () => {
        followerVideos.forEach((video) => {
            video.playbackRate = refs.mainVideo.playbackRate;
        });
    });

    refs.mainVideo.addEventListener("timeupdate", () => {
        syncTimeFromMain();
        renderStatsAtCurrentTime();
    });
    refs.mainVideo.addEventListener("seeking", () => {
        syncTimeFromMain();
        renderStatsAtCurrentTime();
    });
    refs.mainVideo.addEventListener("loadedmetadata", () => {
        renderEvents();
        renderStatsAtCurrentTime();
    });
}

function syncTimeFromMain() {
    const target = refs.mainVideo.currentTime;
    [refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((video) => {
        if (!video.src) return;
        if (Math.abs(video.currentTime - target) > 0.3) {
            video.currentTime = target;
        }
    });
}

async function refreshSamples() {
    try {
        const response = await fetch("/api/samples");
        const data = await response.json();
        state.samples = {
            regular: data.regular || [],
            famous: data.famous || [],
            uploaded: data.uploaded || [],
        };
        state.jobs = data.jobs || [];
        renderClipLibraries();
        renderJobs();
    } catch (error) {
        console.error("Failed loading samples", error);
    }
}

function renderClipLibraries() {
    refs.regularGrid.innerHTML = "";
    refs.famousGrid.innerHTML = "";
    refs.uploadedGrid.innerHTML = "";

    CATEGORIES.forEach((category) => {
        const targetGrid =
            category === "regular"
                ? refs.regularGrid
                : category === "famous"
                    ? refs.famousGrid
                    : refs.uploadedGrid;
        const clips = state.samples[category] || [];

        clips.forEach((clip) => {
            const card = document.createElement("article");
            card.className = "clip-card";
            card.innerHTML = `
                <video preload="metadata" muted>
                    <source src="${resolveSamplePath(clip.sampleVideo)}" type="video/mp4">
                </video>
                <div class="clip-card-body">
                    <h4>${clip.name}</h4>
                    <p>${buildClipStatusText(clip)}</p>
                    <div class="clip-card-actions">
                        <button class="btn btn-secondary" data-action="open">Open Dashboard</button>
                        <button class="btn btn-accent" data-action="run">Run/Refresh Model</button>
                    </div>
                </div>
            `;

            card.querySelector('[data-action="open"]').addEventListener("click", () => openClip(category, clip.id));
            card.querySelector('[data-action="run"]').addEventListener("click", () => runFullPipelineWithWarning(category, clip.id));
            targetGrid.appendChild(card);
        });
    });
}

function buildClipStatusText(clip) {
    if (clip.isComplete) return "Complete set ready (Main, 2D, Heatmap, Ball, Stats)";
    if (Array.isArray(clip.missingOutputs) && clip.missingOutputs.length) {
        return `Missing: ${clip.missingOutputs.join(", ")}`;
    }
    const ready = [
        clip.hasCombined ? "Main" : null,
        clip.has2D ? "2D" : null,
        clip.hasHeatmap ? "Heatmap" : null,
        clip.hasBall ? "Ball" : null,
        clip.hasStats ? "Stats" : null,
    ].filter(Boolean);

    if (!ready.length) return "No processed outputs yet.";
    return `Available: ${ready.join(", ")}`;
}

function resolveVideoPath(category, clipId, suffix) {
    const base = `../${category}_clips/data_content/${clipId}_${suffix}`;
    if (suffix.endsWith(".mp4")) return base;
    return `${base}.mp4`;
}

function resolveSamplePath(sampleVideo) {
    return `../${sampleVideo}`;
}

function setVideoOrFallback(videoEl, fallbackEl, primaryPath, fallbackPath) {
    videoEl.src = primaryPath;
    videoEl.load();
    fallbackEl.style.display = "none";
    videoEl.style.display = "block";

    videoEl.onerror = () => {
        if (fallbackPath && videoEl.src.indexOf("_browser.mp4") !== -1) {
            videoEl.src = fallbackPath;
            videoEl.load();
            return;
        }
        videoEl.style.display = "none";
        fallbackEl.style.display = "block";
    };
}

async function openClip(category, clipId) {
    const clip = (state.samples[category] || []).find((entry) => entry.id === clipId);
    if (!clip) return;

    state.activeClip = { category, clipId, clipName: clip.name };
    state.statsPaths = {
        json: `../${category}_clips/data_content/${clipId}_match_stats.json`,
        csv: `../${category}_clips/data_content/${clipId}_match_stats.csv`,
    };
    refs.activeClipLabel.textContent = `${clip.name} (${category})`;

    setVideoOrFallback(
        refs.mainVideo,
        refs.mainFallback,
        resolveVideoPath(category, clipId, "combined_result_browser.mp4"),
        resolveVideoPath(category, clipId, "combined_result.mp4"),
    );
    refs.mainFallback.style.display = "none";
    refs.mainVideo.style.display = "block";

    setVideoOrFallback(
        refs.pitch2dVideo,
        refs.pitch2dFallback,
        resolveVideoPath(category, clipId, "2d_pitch_browser.mp4"),
        resolveVideoPath(category, clipId, "2d_pitch.mp4"),
    );
    setVideoOrFallback(
        refs.heatmapVideo,
        refs.heatmapFallback,
        resolveVideoPath(category, clipId, "combined_pitch_heatmap_browser.mp4"),
        resolveVideoPath(category, clipId, "combined_pitch_heatmap.mp4"),
    );
    setVideoOrFallback(
        refs.ballVideo,
        refs.ballFallback,
        resolveVideoPath(category, clipId, "ball_tracking_browser.mp4"),
        resolveVideoPath(category, clipId, "ball_tracking.mp4"),
    );

    await loadStats(category, clipId);
    restartAll();
}

function clipHasAllOutputs(clip) {
    return Boolean(clip.hasCombined && clip.has2D && clip.hasHeatmap && clip.hasBall && clip.hasStats);
}

function getClip(category, clipId) {
    return (state.samples[category] || []).find((entry) => entry.id === clipId) || null;
}

async function loadStats(category, clipId) {
    const statsPath = `../${category}_clips/data_content/${clipId}_match_stats.json`;
    try {
        const response = await fetch(statsPath);
        if (!response.ok) {
            state.statsFinal = null;
            state.statsTimeline = null;
            state.events = [];
            renderEmptyStats();
            return;
        }
        const stats = await response.json();
        state.statsFinal = stats;
        state.statsTimeline = Array.isArray(stats.timeline) ? stats.timeline : null;
        state.events = Array.isArray(stats.events) && stats.events.length ? stats.events : buildEventsFromStats(stats);
        renderEvents();
        renderStatsAtCurrentTime();
    } catch (error) {
        console.error("Failed loading stats", error);
        renderEmptyStats();
    }
}

function buildEventsFromStats(stats) {
    const events = [];
    const t0 = stats.team_0 || {};
    const t1 = stats.team_1 || {};

    if ((t0.completed_passes || 0) > 0) events.push({ event: "Pass", team: "Team 0", details: `${t0.completed_passes} completed passes` });
    if ((t1.completed_passes || 0) > 0) events.push({ event: "Pass", team: "Team 1", details: `${t1.completed_passes} completed passes` });
    if ((t0.estimated_shots || 0) > 0) events.push({ event: "Shot", team: "Team 0", details: `${t0.estimated_shots} shots` });
    if ((t1.estimated_shots || 0) > 0) events.push({ event: "Shot", team: "Team 1", details: `${t1.estimated_shots} shots` });
    if ((t0.estimated_goals || 0) > 0) events.push({ event: "Goal", team: "Team 0", details: `${t0.estimated_goals} goals` });
    if ((t1.estimated_goals || 0) > 0) events.push({ event: "Goal", team: "Team 1", details: `${t1.estimated_goals} goals` });

    if (!events.length) {
        events.push({ event: "Tracking", team: "System", details: "No major events tagged yet. Continue model tuning for richer event extraction." });
    }
    return events;
}

function renderEvents() {
    refs.eventsBody.innerHTML = "";
    state.events.forEach((entry) => {
        const time = entry.time_label || formatTime(Number(entry.time_sec || 0));
        const event = String(entry.event || "event").replace("_", " ");
        const team = entry.team === 0 ? "Team 0" : entry.team === 1 ? "Team 1" : (entry.team || "System");
        const details = buildEventDetails(entry);
        const row = document.createElement("tr");
        row.innerHTML = `<td>${time}</td><td>${event}</td><td>${team}</td><td>${details}</td>`;
        refs.eventsBody.appendChild(row);
    });
}

function buildEventDetails(entry) {
    if (entry.details) return entry.details;
    if (entry.event === "pass") {
        return `from #${entry.from_tracker ?? "-"} to #${entry.to_tracker ?? "-"}`;
    }
    if (entry.event === "turnover") {
        return `Team ${entry.team} -> Team ${entry.next_team}`;
    }
    if (entry.event === "shot") {
        const flags = [
            entry.on_target ? "on target" : "off target",
            entry.is_goal ? "goal" : null,
        ].filter(Boolean);
        return `by #${entry.tracker_id ?? "-"} (${flags.join(", ")})`;
    }
    return "-";
}

function renderEmptyStats() {
    refs.possessionTeam0.textContent = "0";
    refs.possessionTeam1.textContent = "0";
    refs.passesTotal.textContent = "0";
    refs.shotsTotal.textContent = "0";
    refs.shotsOnTargetTotal.textContent = "0";
    refs.turnoversTotal.textContent = "0";
    refs.interceptionsTotal.textContent = "0";
    refs.team0Breakdown.textContent = "-";
    refs.team1Breakdown.textContent = "-";
    refs.team0Insights.textContent = "No data";
    refs.team1Insights.textContent = "No data";
    refs.eventsBody.innerHTML = `<tr><td>--:--</td><td>Info</td><td>System</td><td>No stats file found for this clip.</td></tr>`;
}

function renderStatsAtCurrentTime() {
    if (!state.statsFinal) {
        renderEmptyStats();
        return;
    }

    const current = refs.mainVideo.currentTime || 0;
    const duration = refs.mainVideo.duration || 1;
    const t0 = state.statsFinal.team_0 || {};
    const t1 = state.statsFinal.team_1 || {};
    const values = getLiveValuesFromTime(current, duration, t0, t1);

    refs.possessionTeam0.textContent = values.t0Poss.toFixed(1);
    refs.possessionTeam1.textContent = values.t1Poss.toFixed(1);
    refs.passesTotal.textContent = String(values.t0Pass + values.t1Pass);
    refs.shotsTotal.textContent = String(values.t0Shot + values.t1Shot);
    refs.shotsOnTargetTotal.textContent = String(values.t0Sot + values.t1Sot);
    refs.turnoversTotal.textContent = String(values.t0Turn + values.t1Turn);
    refs.interceptionsTotal.textContent = String(values.t0Int + values.t1Int);
    refs.team0Breakdown.textContent = `Passes ${values.t0Pass} | Shots ${values.t0Shot} | Goals ${values.t0Goal}`;
    refs.team1Breakdown.textContent = `Passes ${values.t1Pass} | Shots ${values.t1Shot} | Goals ${values.t1Goal}`;
    renderPlayerInsights();
}

function getLiveValuesFromTime(current, duration, t0, t1) {
    if (state.statsTimeline && state.statsTimeline.length) {
        let snapshot = state.statsTimeline[0];
        for (const item of state.statsTimeline) {
            if (Number(item.time_sec || 0) <= current) {
                snapshot = item;
            } else {
                break;
            }
        }
        const possFrames0 = Number(snapshot.team_0?.possession_frames || 0);
        const possFrames1 = Number(snapshot.team_1?.possession_frames || 0);
        const possDen = possFrames0 + possFrames1;
        return {
            t0Poss: possDen ? (possFrames0 / possDen) * 100 : 0,
            t1Poss: possDen ? (possFrames1 / possDen) * 100 : 0,
            t0Pass: Number(snapshot.team_0?.completed_passes || 0),
            t1Pass: Number(snapshot.team_1?.completed_passes || 0),
            t0Shot: Number(snapshot.team_0?.estimated_shots || 0),
            t1Shot: Number(snapshot.team_1?.estimated_shots || 0),
            t0Sot: Number(snapshot.team_0?.estimated_shots_on_target || 0),
            t1Sot: Number(snapshot.team_1?.estimated_shots_on_target || 0),
            t0Turn: Number(snapshot.team_0?.turnovers || 0),
            t1Turn: Number(snapshot.team_1?.turnovers || 0),
            t0Int: Number(snapshot.team_0?.interceptions || 0),
            t1Int: Number(snapshot.team_1?.interceptions || 0),
            t0Goal: Number(snapshot.team_0?.estimated_goals || 0),
            t1Goal: Number(snapshot.team_1?.estimated_goals || 0),
        };
    }

    const ratio = Math.max(0, Math.min(1, current / Math.max(duration, 1)));
    return {
        t0Poss: ratio * Number(t0.possession_percent || 0),
        t1Poss: ratio * Number(t1.possession_percent || 0),
        t0Pass: Math.floor(ratio * Number(t0.completed_passes || 0)),
        t1Pass: Math.floor(ratio * Number(t1.completed_passes || 0)),
        t0Shot: Math.floor(ratio * Number(t0.estimated_shots || 0)),
        t1Shot: Math.floor(ratio * Number(t1.estimated_shots || 0)),
        t0Sot: Math.floor(ratio * Number(t0.estimated_shots_on_target || 0)),
        t1Sot: Math.floor(ratio * Number(t1.estimated_shots_on_target || 0)),
        t0Turn: Math.floor(ratio * Number(t0.turnovers || 0)),
        t1Turn: Math.floor(ratio * Number(t1.turnovers || 0)),
        t0Int: Math.floor(ratio * Number(t0.interceptions || 0)),
        t1Int: Math.floor(ratio * Number(t1.interceptions || 0)),
        t0Goal: Math.floor(ratio * Number(t0.estimated_goals || 0)),
        t1Goal: Math.floor(ratio * Number(t1.estimated_goals || 0)),
    };
}

function renderPlayerInsights() {
    const insights = state.statsFinal?.player_insights || {};
    refs.team0Insights.textContent = formatTeamInsights(insights.team_0);
    refs.team1Insights.textContent = formatTeamInsights(insights.team_1);
}

function formatTeamInsights(teamInsights) {
    if (!teamInsights) return "No player insights";
    const parts = [];
    if (teamInsights.top_passer) {
        parts.push(`Top passer #${teamInsights.top_passer.tracker_id} (${teamInsights.top_passer.completed_passes})`);
    }
    if (teamInsights.top_shooter) {
        parts.push(`Top shooter #${teamInsights.top_shooter.tracker_id} (${teamInsights.top_shooter.estimated_shots})`);
    }
    if (teamInsights.most_touches) {
        parts.push(`Most touches #${teamInsights.most_touches.tracker_id} (${teamInsights.most_touches.touches})`);
    }
    return parts.length ? parts.join(" | ") : "No player insights";
}

function playAll() {
    state.syncLock = true;
    refs.mainVideo.play().catch(() => {});
    [refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((v) => {
        if (v.src) {
            v.currentTime = refs.mainVideo.currentTime;
            v.play().catch(() => {});
        }
    });
    state.syncLock = false;
}

function pauseAll() {
    [refs.mainVideo, refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((v) => v.pause());
}

function restartAll() {
    pauseAll();
    [refs.mainVideo, refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((v) => {
        if (v.src) v.currentTime = 0;
    });
    renderStatsAtCurrentTime();
}

async function runPipeline(category, clipId, mode = "full") {
    if (hasActiveJobForClip(category, clipId)) {
        alert("This clip already has a queued/running job. Wait for it to finish before starting another run.");
        return;
    }
    try {
        let endpoint = "/api/run";
        if (mode === "missing") endpoint = "/api/run_missing";
        if (mode === "stats") endpoint = "/api/run_stats";
        if (mode === "pitch2d") endpoint = "/api/run_pitch2d";
        if (mode === "heatmap") endpoint = "/api/run_heatmap";
        if (mode === "ball") endpoint = "/api/run_ball";

        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category, id: clipId }),
        });
        const payload = await response.json();
        if (!response.ok) {
            const jobInfo = payload?.job?.id ? ` (job ${payload.job.id})` : "";
            alert((payload.error || "Failed to queue run.") + jobInfo);
            return;
        }
        refreshSamples();
        pollJobs(true);
    } catch (error) {
        console.error(error);
        alert("Could not queue pipeline job.");
    }
}

function hasActiveJobForClip(category, clipId) {
    return (state.jobs || []).some(
        (job) => job.category === category && job.clip_id === clipId && (job.status === "queued" || job.status === "running"),
    );
}

function runPipelineForActiveClip() {
    if (!state.activeClip) {
        alert("Choose a clip first.");
        return;
    }
    const clip = getClip(state.activeClip.category, state.activeClip.clipId);
    if (!clip) {
        alert("Clip not found. Refresh samples and try again.");
        return;
    }
    runFullPipelineWithWarning(state.activeClip.category, state.activeClip.clipId, clip);
}

function runMissingForActiveClip() {
    if (!state.activeClip) {
        alert("Choose a clip first.");
        return;
    }
    const clip = getClip(state.activeClip.category, state.activeClip.clipId);
    if (!clip) {
        alert("Clip not found. Refresh samples and try again.");
        return;
    }
    if (clipHasAllOutputs(clip)) {
        alert("This clip already has a full processed set. Nothing missing to complete.");
        return;
    }
    runPipeline(state.activeClip.category, state.activeClip.clipId, "missing");
}

function runStatsOnlyForActiveClip() {
    if (!state.activeClip) {
        alert("Choose a clip first.");
        return;
    }
    const confirmed = window.confirm(
        "This will rerun only match stats for the selected clip and overwrite existing stats output. Continue?",
    );
    if (!confirmed) return;
    runPipeline(state.activeClip.category, state.activeClip.clipId, "stats");
}

function run2dOnlyForActiveClip() {
    runSingleComponentForActiveClip(
        "2D tactical view",
        "pitch2d",
        "This will rerun only the 2D tactical output for this clip and overwrite the existing 2D file. Continue?",
    );
}

function runHeatmapOnlyForActiveClip() {
    runSingleComponentForActiveClip(
        "heatmap",
        "heatmap",
        "This will rerun only the heatmap output for this clip and overwrite the existing heatmap file. Continue?",
    );
}

function runBallOnlyForActiveClip() {
    runSingleComponentForActiveClip(
        "ball tracking",
        "ball",
        "This will rerun only the ball tracking output for this clip and overwrite the existing ball tracking file. Continue?",
    );
}

function runSingleComponentForActiveClip(_componentLabel, mode, confirmText) {
    if (!state.activeClip) {
        alert("Choose a clip first.");
        return;
    }
    const confirmed = window.confirm(confirmText);
    if (!confirmed) return;
    runPipeline(state.activeClip.category, state.activeClip.clipId, mode);
}

function runFullPipelineWithWarning(category, clipId, clipHint = null) {
    const clip = clipHint || getClip(category, clipId);
    if (!clip) {
        alert("Clip not found. Refresh samples and try again.");
        return;
    }
    if (clipHasAllOutputs(clip)) {
        const confirmed = window.confirm(
            "This sample already has a full processed set. Running full pipeline again will overwrite existing outputs. Continue?",
        );
        if (!confirmed) return;
    }
    runPipeline(category, clipId, "full");
}

async function uploadAndRun(event) {
    const file = event.target.files[0];
    if (!file) return;

    const form = new FormData();
    form.append("video", file);

    try {
        const response = await fetch("/api/upload", { method: "POST", body: form });
        const payload = await response.json();
        if (!response.ok) {
            alert(payload.error || "Upload failed.");
            return;
        }
        event.target.value = "";
        pollJobs(true);
        refreshSamples();
    } catch (error) {
        console.error(error);
        alert("Upload request failed.");
    }
}

async function pollJobs(immediate = false) {
    if (state.jobsStreamConnected) return;
    try {
        const response = await fetch("/api/jobs");
        const payload = await response.json();
        state.jobs = payload.jobs || [];
        renderJobs();
    } catch (error) {
        console.error("Failed polling jobs", error);
    }

    setTimeout(() => {
        pollJobs(false);
        if (immediate) refreshSamples();
    }, immediate ? 1000 : 4000);
}

function connectJobsStream() {
    if (!("EventSource" in window)) return;
    try {
        const stream = new EventSource("/api/jobs/stream");
        stream.addEventListener("jobs", (event) => {
            const payload = JSON.parse(event.data);
            state.jobs = payload.jobs || [];
            state.jobsStreamConnected = true;
            renderJobs();
            const now = Date.now();
            if (now - state.lastSamplesRefreshMs > 2500) {
                state.lastSamplesRefreshMs = now;
                refreshSamples();
            }
        });
        stream.onerror = () => {
            state.jobsStreamConnected = false;
        };
    } catch (_err) {
        state.jobsStreamConnected = false;
    }
}

function renderJobs() {
    refs.jobsList.innerHTML = "";
    if (!state.jobs.length) {
        refs.jobsList.innerHTML = `<div class="job-item">No processing jobs yet.</div>`;
        return;
    }

    const sortedJobs = [...state.jobs].sort((a, b) => (a.started_at || "").localeCompare(b.started_at || "")).reverse();
    sortedJobs.slice(0, 8).forEach((job) => {
        const item = document.createElement("div");
        item.className = `job-item ${job.status}`;
        item.innerHTML = `
            <div>
                <strong>${job.clip_id}</strong>
                <span>(${job.category})</span>
            </div>
            <div class="job-meta">${job.status.toUpperCase()} - ${job.stage} - ${job.progress}%</div>
            <div class="job-message">${job.message || ""}</div>
        `;
        refs.jobsList.appendChild(item);
    });
}

function formatTime(seconds) {
    const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
    const mins = Math.floor(safe / 60);
    const secs = Math.floor(safe % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function exportJson() {
    if (!state.statsFinal || !state.activeClip) {
        alert("Open a processed clip first.");
        return;
    }
    const blob = new Blob([JSON.stringify(state.statsFinal, null, 2)], { type: "application/json" });
    const name = `${state.activeClip.clipId}_match_stats_export.json`;
    triggerDownload(blob, name);
}

async function exportCsv() {
    if (!state.statsPaths?.csv || !state.activeClip) {
        alert("Open a processed clip first.");
        return;
    }
    try {
        const response = await fetch(state.statsPaths.csv);
        if (!response.ok) {
            alert("CSV file is not available for this clip yet.");
            return;
        }
        const text = await response.text();
        const blob = new Blob([text], { type: "text/csv" });
        const name = `${state.activeClip.clipId}_match_stats_export.csv`;
        triggerDownload(blob, name);
    } catch (_error) {
        alert("Unable to export CSV right now.");
    }
}

function exportReport() {
    if (!state.statsFinal || !state.activeClip) {
        alert("Open a processed clip first.");
        return;
    }
    const t0 = state.statsFinal.team_0 || {};
    const t1 = state.statsFinal.team_1 || {};
    const rows = (state.events || []).slice(0, 40).map((event) => `
        <tr>
            <td>${event.time_label || formatTime(event.time_sec || 0)}</td>
            <td>${String(event.event || "").replace("_", " ")}</td>
            <td>${event.team === 0 ? "Team 0" : event.team === 1 ? "Team 1" : "System"}</td>
            <td>${buildEventDetails(event)}</td>
        </tr>
    `).join("");

    const reportHtml = `
        <!DOCTYPE html>
        <html><head><title>VeoVision Report</title>
        <style>body{font-family:Arial,sans-serif;padding:20px}h1{margin-bottom:4px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #ddd;padding:8px}th{background:#f3f3f3}</style>
        </head><body>
        <h1>VeoVision Match Report</h1>
        <p>Clip: ${state.activeClip.clipId} (${state.activeClip.category})</p>
        <h2>Summary</h2>
        <ul>
            <li>Team 0 possession: ${t0.possession_percent || 0}%</li>
            <li>Team 1 possession: ${t1.possession_percent || 0}%</li>
            <li>Total passes: ${(t0.completed_passes || 0) + (t1.completed_passes || 0)}</li>
            <li>Total shots: ${(t0.estimated_shots || 0) + (t1.estimated_shots || 0)}</li>
        </ul>
        <h2>Events</h2>
        <table><thead><tr><th>Time</th><th>Event</th><th>Team</th><th>Details</th></tr></thead><tbody>${rows}</tbody></table>
        <p style="margin-top:16px">Created by Veo Vision</p>
        </body></html>
    `;

    const reportWindow = window.open("", "_blank");
    if (!reportWindow) {
        alert("Pop-up blocked. Allow pop-ups to export report.");
        return;
    }
    reportWindow.document.write(reportHtml);
    reportWindow.document.close();
    reportWindow.focus();
}

function triggerDownload(blob, fileName) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    document.body.removeChild(link);
}

function openVideoFullscreen(videoEl) {
    if (!videoEl || !videoEl.src) {
        alert("Load a clip first to use fullscreen.");
        return;
    }

    const requestFn = videoEl.requestFullscreen
        || videoEl.webkitRequestFullscreen
        || videoEl.mozRequestFullScreen
        || videoEl.msRequestFullscreen;

    if (!requestFn) {
        alert("Fullscreen is not supported in this browser.");
        return;
    }

    requestFn.call(videoEl);
}

