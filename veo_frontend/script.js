const GITHUB_PROJECT_URL = "https://github.com/MoLCFC/VeoVision2.0";
const CATEGORIES = ["regular", "famous", "uploaded"];

/** UI labels for model team_0 / team_1 (possession colors follow name: blue / red). */
const TEAM_DISPLAY_NAME = { 0: "Team blue", 1: "Team red" };

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
}

function formatTeamDisplayName(team) {
    if (team === 0 || team === "0") return TEAM_DISPLAY_NAME[0];
    if (team === 1 || team === "1") return TEAM_DISPLAY_NAME[1];
    if (typeof team === "string") {
        const t = team.trim().toLowerCase();
        if (t === "team 0") return TEAM_DISPLAY_NAME[0];
        if (t === "team 1") return TEAM_DISPLAY_NAME[1];
    }
    return team == null || team === "" ? "System" : String(team);
}

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
    lastAutoReloadJobId: null,
    /** Main player: "analysis" = combined output when available; "original" = uploaded sample only. */
    mainDisplayMode: "analysis",
};

const refs = {
    regularGrid: document.getElementById("regularGrid"),
    famousGrid: document.getElementById("famousGrid"),
    uploadedGrid: document.getElementById("uploadedGrid"),
    activeClipLabel: document.getElementById("activeClipLabel"),
    renameActiveClipBtn: document.getElementById("renameActiveClipBtn"),
    jobsList: document.getElementById("jobsList"),
    eventsBody: document.getElementById("eventsBody"),
    uploadInput: document.getElementById("uploadInput"),
    playAllBtn: document.getElementById("playAllBtn"),
    pauseAllBtn: document.getElementById("pauseAllBtn"),
    restartAllBtn: document.getElementById("restartAllBtn"),
    runPipelineBtn: document.getElementById("runPipelineBtn"),
    run3dOnlyBtn: document.getElementById("run3dOnlyBtn"),
    runMissingBtn: document.getElementById("runMissingBtn"),
    runStatsOnlyBtn: document.getElementById("runStatsOnlyBtn"),
    run2dOnlyBtn: document.getElementById("run2dOnlyBtn"),
    runHeatmapOnlyBtn: document.getElementById("runHeatmapOnlyBtn"),
    runBallOnlyBtn: document.getElementById("runBallOnlyBtn"),
    loadAiOutputsBtn: document.getElementById("loadAiOutputsBtn"),
    githubLink: document.getElementById("githubLink"),
    mainVideo: document.getElementById("mainVideo"),
    mainFallback: document.getElementById("mainFallback"),
    mainSourceToggle: document.getElementById("mainSourceToggle"),
    mainShowAnalysisBtn: document.getElementById("mainShowAnalysisBtn"),
    mainShowOriginalBtn: document.getElementById("mainShowOriginalBtn"),
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
    attachJobsListDelegation();
    attachSyncEvents();
    refreshSamples();
    connectJobsStream();
    pollJobs();
});

function attachJobsListDelegation() {
    if (!refs.jobsList || refs.jobsList.dataset.delegationBound === "1") return;
    refs.jobsList.dataset.delegationBound = "1";
    refs.jobsList.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-job-id]");
        if (!btn || btn.disabled) return;
        ev.preventDefault();
        ev.stopPropagation();
        const jobId = btn.getAttribute("data-job-id");
        void deleteProcessingJob(jobId);
    });
}

function attachControls() {
    refs.playAllBtn.addEventListener("click", playAll);
    refs.pauseAllBtn.addEventListener("click", pauseAll);
    refs.restartAllBtn.addEventListener("click", restartAll);
    refs.runPipelineBtn.addEventListener("click", runPipelineForActiveClip);
    refs.run3dOnlyBtn.addEventListener("click", run3dOnlyForActiveClip);
    refs.runMissingBtn.addEventListener("click", runMissingForActiveClip);
    refs.runStatsOnlyBtn.addEventListener("click", runStatsOnlyForActiveClip);
    refs.run2dOnlyBtn.addEventListener("click", run2dOnlyForActiveClip);
    refs.runHeatmapOnlyBtn.addEventListener("click", runHeatmapOnlyForActiveClip);
    refs.runBallOnlyBtn.addEventListener("click", runBallOnlyForActiveClip);
    refs.loadAiOutputsBtn.addEventListener("click", loadAiOutputsForActiveClip);
    refs.uploadInput.addEventListener("change", uploadAndRun);
    refs.exportJsonBtn.addEventListener("click", exportJson);
    refs.exportCsvBtn.addEventListener("click", exportCsv);
    refs.exportReportBtn.addEventListener("click", exportReport);
    if (refs.renameActiveClipBtn) {
        refs.renameActiveClipBtn.addEventListener("click", renameActiveClip);
    }
    refs.mainFullscreenBtn.addEventListener("click", () => openVideoFullscreen(refs.mainVideo));
    if (refs.mainShowAnalysisBtn) {
        refs.mainShowAnalysisBtn.addEventListener("click", () => setMainDisplayMode("analysis"));
    }
    if (refs.mainShowOriginalBtn) {
        refs.mainShowOriginalBtn.addEventListener("click", () => setMainDisplayMode("original"));
    }
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
            const deleteAction = category === "uploaded"
                ? `<button class="btn btn-danger" data-action="delete">Delete</button>`
                : "";
            card.innerHTML = `
                <video preload="metadata" muted playsinline>
                    ${clipPreviewSourceTags(category, clip)}
                </video>
                <div class="clip-card-body">
                    <h4>${escapeHtml(clip.name)}</h4>
                    <p>${escapeHtml(buildClipStatusText(clip))}</p>
                    <div class="clip-card-actions">
                        <button class="btn btn-secondary" data-action="open">Open Dashboard</button>
                        <button class="btn btn-secondary btn-rename" data-action="rename" type="button">Rename</button>
                        <button class="btn btn-accent" data-action="run">Run/Refresh Model</button>
                        ${deleteAction}
                    </div>
                </div>
            `;

            card.querySelector('[data-action="open"]').addEventListener("click", () => openClip(category, clip.id));
            card.querySelector('[data-action="rename"]').addEventListener("click", () => renameClip(category, clip.id, clip.name));
            card.querySelector('[data-action="run"]').addEventListener("click", () => runFullPipelineWithWarning(category, clip.id));
            const deleteBtn = card.querySelector('[data-action="delete"]');
            if (deleteBtn) {
                deleteBtn.addEventListener("click", () => deleteUploadedClip(clip.id));
            }
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

/** Prefer H.264 *_browser outputs for grid previews; raw uploads are often HEVC/non-web MP4. */
function clipPreviewSourceTags(category, clip) {
    const paths = [];
    if (clip.hasCombined) {
        paths.push(resolveVideoPath(category, clip.id, "combined_result_browser.mp4"));
        paths.push(resolveVideoPath(category, clip.id, "combined_result.mp4"));
    }
    paths.push(resolveSamplePath(clip.sampleVideo));
    return paths.map((src) => `<source src="${src}" type="video/mp4">`).join("");
}

function setVideoOrFallback(videoEl, fallbackEl, ...paths) {
    const list = paths.filter((p) => typeof p === "string" && p.trim());
    fallbackEl.style.display = "none";
    videoEl.style.display = "block";

    const finishError = () => {
        videoEl.onerror = null;
        videoEl.removeAttribute("src");
        videoEl.load();
        videoEl.style.display = "none";
        fallbackEl.style.display = "block";
    };

    let index = 0;
    const tryNext = () => {
        videoEl.onerror = null;
        if (index >= list.length) {
            finishError();
            return;
        }
        const path = list[index];
        index += 1;
        videoEl.onerror = tryNext;
        videoEl.src = path;
        videoEl.load();
    };
    tryNext();
}

const SECONDARY_PENDING_MSG =
    'AI output not loaded yet. Run a model job below, then click "Load AI video outputs" (or wait for the job to finish).';

function updateMainSourceToggleUI() {
    if (!refs.mainSourceToggle || !refs.mainShowAnalysisBtn || !refs.mainShowOriginalBtn) return;
    const clip = state.activeClip ? getClip(state.activeClip.category, state.activeClip.clipId) : null;
    const show = Boolean(clip && clip.hasCombined);
    refs.mainSourceToggle.hidden = !show;
    refs.mainShowAnalysisBtn.classList.toggle("is-active", show && state.mainDisplayMode === "analysis");
    refs.mainShowOriginalBtn.classList.toggle("is-active", show && state.mainDisplayMode === "original");
}

function applyMainVideoForCategoryClip(category, clipId, clip) {
    const sampleSrc = resolveSamplePath(clip.sampleVideo);
    if (!clip.hasCombined || state.mainDisplayMode === "original") {
        setVideoOrFallback(refs.mainVideo, refs.mainFallback, sampleSrc);
    } else {
        setVideoOrFallback(
            refs.mainVideo,
            refs.mainFallback,
            resolveVideoPath(category, clipId, "combined_result_browser.mp4"),
            resolveVideoPath(category, clipId, "combined_result.mp4"),
            sampleSrc,
        );
    }
    updateMainSourceToggleUI();
}

function setMainDisplayMode(mode) {
    if (!state.activeClip) return;
    if (mode !== "analysis" && mode !== "original") return;
    const clip = getClip(state.activeClip.category, state.activeClip.clipId);
    if (!clip || !clip.hasCombined) return;
    state.mainDisplayMode = mode;
    applyMainVideoForCategoryClip(state.activeClip.category, state.activeClip.clipId, clip);
}

function showSecondaryPlaceholders() {
    [refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((v) => {
        v.onerror = null;
        v.removeAttribute("src");
        v.load();
        v.style.display = "none";
    });
    refs.pitch2dFallback.textContent = SECONDARY_PENDING_MSG;
    refs.heatmapFallback.textContent = SECONDARY_PENDING_MSG;
    refs.ballFallback.textContent = SECONDARY_PENDING_MSG;
    refs.pitch2dFallback.style.display = "block";
    refs.heatmapFallback.style.display = "block";
    refs.ballFallback.style.display = "block";
}

function attachProcessedVideoPanels(category, clipId, clip) {
    applyMainVideoForCategoryClip(category, clipId, clip);

    setVideoOrFallback(
        refs.pitch2dVideo,
        refs.pitch2dFallback,
        ...(clip.has2D
            ? [
                  resolveVideoPath(category, clipId, "2d_pitch_browser.mp4"),
                  resolveVideoPath(category, clipId, "2d_pitch.mp4"),
              ]
            : []),
    );
    setVideoOrFallback(
        refs.heatmapVideo,
        refs.heatmapFallback,
        ...(clip.hasHeatmap
            ? [
                  resolveVideoPath(category, clipId, "combined_pitch_heatmap_browser.mp4"),
                  resolveVideoPath(category, clipId, "combined_pitch_heatmap.mp4"),
              ]
            : []),
    );
    setVideoOrFallback(
        refs.ballVideo,
        refs.ballFallback,
        ...(clip.hasBall
            ? [
                  resolveVideoPath(category, clipId, "ball_tracking_browser.mp4"),
                  resolveVideoPath(category, clipId, "ball_tracking.mp4"),
              ]
            : []),
    );
}

async function openClip(category, clipId, opts = {}) {
    await refreshSamples();
    const clip = (state.samples[category] || []).find((entry) => entry.id === clipId);
    if (!clip) return;

    let attachProcessedVideos;
    if (opts.attachProcessedVideos === true) {
        attachProcessedVideos = true;
    } else if (opts.attachProcessedVideos === false) {
        attachProcessedVideos = false;
    } else {
        attachProcessedVideos = Boolean(
            clip.hasCombined || clip.has2D || clip.hasHeatmap || clip.hasBall,
        );
    }

    state.activeClip = { category, clipId, clipName: clip.name };
    state.statsPaths = {
        json: `../${category}_clips/data_content/${clipId}_match_stats.json`,
        csv: `../${category}_clips/data_content/${clipId}_match_stats.csv`,
    };
    updateActiveClipLabel();

    if (attachProcessedVideos) {
        state.mainDisplayMode = clip.hasCombined ? "analysis" : "original";
        attachProcessedVideoPanels(category, clipId, clip);
    } else {
        if (refs.mainSourceToggle) refs.mainSourceToggle.hidden = true;
        state.mainDisplayMode = "original";
        setVideoOrFallback(refs.mainVideo, refs.mainFallback, resolveSamplePath(clip.sampleVideo));
        showSecondaryPlaceholders();
    }

    await loadStats(category, clipId);
    restartAll();
}

function clipHasAllOutputs(clip) {
    return Boolean(clip.hasCombined && clip.has2D && clip.hasHeatmap && clip.hasBall && clip.hasStats);
}

function getClip(category, clipId) {
    return (state.samples[category] || []).find((entry) => entry.id === clipId) || null;
}

function updateActiveClipLabel() {
    if (!refs.activeClipLabel) return;
    if (!state.activeClip) {
        refs.activeClipLabel.textContent = "Pick a clip from Regular, Famous, or Uploaded sections";
        if (refs.renameActiveClipBtn) refs.renameActiveClipBtn.hidden = true;
        return;
    }
    const clip = getClip(state.activeClip.category, state.activeClip.clipId);
    const name = clip?.name || state.activeClip.clipName || state.activeClip.clipId.replace(/_/g, " ");
    state.activeClip.clipName = name;
    refs.activeClipLabel.textContent = `${name} (${state.activeClip.category})`;
    if (refs.renameActiveClipBtn) refs.renameActiveClipBtn.hidden = false;
}

function renameActiveClip() {
    if (!state.activeClip) return;
    renameClip(state.activeClip.category, state.activeClip.clipId, state.activeClip.clipName);
}

async function renameClip(category, clipId, currentName) {
    const fallback = (currentName || clipId).replace(/_/g, " ");
    const next = window.prompt("Display name for this clip:", fallback);
    if (next === null) return;

    const trimmed = next.trim();
    if (!trimmed) {
        alert("Name cannot be empty.");
        return;
    }
    if (trimmed.length > 120) {
        alert("Name must be 120 characters or fewer.");
        return;
    }

    try {
        const response = await fetch("/api/clip", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category, id: clipId, name: trimmed }),
        });
        const payload = await response.json();
        if (!response.ok) {
            alert(payload.error || "Failed to rename clip.");
            return;
        }
        if (state.activeClip && state.activeClip.category === category && state.activeClip.clipId === clipId) {
            state.activeClip.clipName = trimmed;
            updateActiveClipLabel();
        }
        await refreshSamples();
    } catch (error) {
        console.error(error);
        alert("Rename request failed.");
    }
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

    if ((t0.completed_passes || 0) > 0) events.push({ event: "Pass", team: 0, details: `${t0.completed_passes} completed passes` });
    if ((t1.completed_passes || 0) > 0) events.push({ event: "Pass", team: 1, details: `${t1.completed_passes} completed passes` });
    if ((t0.estimated_shots || 0) > 0) events.push({ event: "Shot", team: 0, details: `${t0.estimated_shots} shots` });
    if ((t1.estimated_shots || 0) > 0) events.push({ event: "Shot", team: 1, details: `${t1.estimated_shots} shots` });
    if ((t0.estimated_goals || 0) > 0) events.push({ event: "Goal", team: 0, details: `${t0.estimated_goals} goals` });
    if ((t1.estimated_goals || 0) > 0) events.push({ event: "Goal", team: 1, details: `${t1.estimated_goals} goals` });

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
        const team = formatTeamDisplayName(entry.team);
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
        return `${formatTeamDisplayName(entry.team)} → ${formatTeamDisplayName(entry.next_team)}`;
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
    refs.possessionTeam0.textContent = "0.0%";
    refs.possessionTeam1.textContent = "0.0%";
    refs.passesTotal.textContent = "0";
    refs.shotsTotal.textContent = "0";
    refs.shotsOnTargetTotal.textContent = "0";
    refs.turnoversTotal.textContent = "0";
    refs.interceptionsTotal.textContent = "0";
    refs.team0Breakdown.textContent = "-";
    refs.team1Breakdown.textContent = "-";
    refs.team0Insights.textContent = "No data";
    refs.team1Insights.textContent = "No data";
    updatePossessionVisualState(0, 0);
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

    refs.possessionTeam0.textContent = `${values.t0Poss.toFixed(1)}%`;
    refs.possessionTeam1.textContent = `${values.t1Poss.toFixed(1)}%`;
    refs.passesTotal.textContent = String(values.t0Pass + values.t1Pass);
    refs.shotsTotal.textContent = String(values.t0Shot + values.t1Shot);
    refs.shotsOnTargetTotal.textContent = String(values.t0Sot + values.t1Sot);
    refs.turnoversTotal.textContent = String(values.t0Turn + values.t1Turn);
    refs.interceptionsTotal.textContent = String(values.t0Int + values.t1Int);
    refs.team0Breakdown.textContent = `Passes ${values.t0Pass} | Shots ${values.t0Shot} | Goals ${values.t0Goal}`;
    refs.team1Breakdown.textContent = `Passes ${values.t1Pass} | Shots ${values.t1Shot} | Goals ${values.t1Goal}`;
    updatePossessionVisualState(values.t0Poss, values.t1Poss);
    renderPlayerInsights();
}

function updatePossessionVisualState(team0Poss, team1Poss) {
    refs.possessionTeam0.classList.remove("leading");
    refs.possessionTeam1.classList.remove("leading");
    if (team0Poss > team1Poss) {
        refs.possessionTeam0.classList.add("leading");
    } else if (team1Poss > team0Poss) {
        refs.possessionTeam1.classList.add("leading");
    }
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
    [refs.mainVideo, refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((v) => {
        if (v) v.pause();
    });
}

function restartAll() {
    pauseAll();
    [refs.mainVideo, refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((v) => {
        if (v && v.src) v.currentTime = 0;
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
        const body = { category, id: clipId };
        if (mode === "missing") endpoint = "/api/run_missing";
        else if (mode === "stats") endpoint = "/api/run_stats";
        else if (mode === "combined") body.mode = "combined";
        else if (mode === "pitch2d") endpoint = "/api/run_pitch2d";
        else if (mode === "heatmap") endpoint = "/api/run_heatmap";
        else if (mode === "ball") endpoint = "/api/run_ball";

        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const payload = await response.json();
        if (!response.ok) {
            const jobInfo = payload?.job && (payload.job.job_id || payload.job.id)
                ? ` (job ${payload.job.job_id || payload.job.id})`
                : "";
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

function run3dOnlyForActiveClip() {
    runSingleComponentForActiveClip(
        "3D analysis",
        "combined",
        "This will rerun only the main 3D analysis video for this clip and overwrite the existing main analysis output. Continue?",
    );
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

async function loadAiOutputsForActiveClip() {
    if (!state.activeClip) {
        alert("Choose a clip first.");
        return;
    }
    await openClip(state.activeClip.category, state.activeClip.clipId, { attachProcessedVideos: true });
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

async function deleteUploadedClip(clipId) {
    const hasActive = hasActiveJobForClip("uploaded", clipId);
    if (hasActive) {
        alert("This uploaded clip is currently processing. Wait for completion before deleting.");
        return;
    }
    const confirmed = window.confirm(
        "Delete this uploaded clip and all its generated outputs (main, 2D, heatmap, ball, stats)? This cannot be undone.",
    );
    if (!confirmed) return;

    try {
        const response = await fetch(`/api/clip?category=uploaded&id=${encodeURIComponent(clipId)}`, {
            method: "DELETE",
        });
        const payload = await response.json();
        if (!response.ok) {
            alert(payload.error || "Failed to delete uploaded clip.");
            return;
        }
        if (
            state.activeClip
            && state.activeClip.category === "uploaded"
            && state.activeClip.clipId === clipId
        ) {
            state.activeClip = null;
            state.statsFinal = null;
            state.statsTimeline = null;
            state.events = [];
            updateActiveClipLabel();
            if (refs.mainSourceToggle) refs.mainSourceToggle.hidden = true;
            [refs.mainVideo, refs.pitch2dVideo, refs.heatmapVideo, refs.ballVideo].forEach((videoEl) => {
                videoEl.pause();
                videoEl.removeAttribute("src");
                videoEl.load();
            });
            refs.mainFallback.style.display = "block";
            refs.pitch2dFallback.style.display = "block";
            refs.heatmapFallback.style.display = "block";
            refs.ballFallback.style.display = "block";
            renderEmptyStats();
        }
        refreshSamples();
    } catch (error) {
        console.error(error);
        alert("Delete request failed.");
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
            void maybeAutoReloadActiveClipAfterJobDone();
            const now = Date.now();
            if (now - state.lastSamplesRefreshMs > 2500) {
                state.lastSamplesRefreshMs = now;
                void refreshSamples();
            }
        });
        stream.onerror = () => {
            state.jobsStreamConnected = false;
        };
    } catch (_err) {
        state.jobsStreamConnected = false;
    }
}

async function maybeAutoReloadActiveClipAfterJobDone() {
    if (!state.activeClip) return;
    const relatedJobs = (state.jobs || [])
        .filter((job) => job.category === state.activeClip.category && job.clip_id === state.activeClip.clipId)
        .sort((a, b) => (a.ended_at || "").localeCompare(b.ended_at || ""));
    if (!relatedJobs.length) return;
    const latest = relatedJobs[relatedJobs.length - 1];
    if (latest.status !== "done") return;
    if (state.lastAutoReloadJobId === latest.job_id || state.lastAutoReloadJobId === latest.id) return;
    state.lastAutoReloadJobId = latest.job_id || latest.id;
    await openClip(state.activeClip.category, state.activeClip.clipId, { attachProcessedVideos: true });
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
        const header = document.createElement("div");
        header.className = "job-item-header";
        const title = document.createElement("div");
        const strong = document.createElement("strong");
        strong.textContent = job.clip_id;
        const span = document.createElement("span");
        span.textContent = ` (${job.category})`;
        title.appendChild(strong);
        title.appendChild(span);
        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "btn btn-danger btn-compact";
        removeBtn.textContent = "Remove";
        removeBtn.disabled = job.status === "running";
        removeBtn.title =
            job.status === "running"
                ? "Cannot remove while a job is running"
                : "Remove this job from the list (does not delete clip files)";
        const jobKey = job.job_id || job.id;
        removeBtn.setAttribute("data-job-id", jobKey != null && jobKey !== "" ? String(jobKey) : "");
        header.appendChild(title);
        header.appendChild(removeBtn);
        item.appendChild(header);
        const meta = document.createElement("div");
        meta.className = "job-meta";
        meta.textContent = `${String(job.status || "").toUpperCase()} - ${job.stage} - ${job.progress}% - mode: ${job.run_mode || "full"}`;
        item.appendChild(meta);
        const msg = document.createElement("div");
        msg.className = "job-message";
        msg.textContent = job.message || "";
        item.appendChild(msg);
        refs.jobsList.appendChild(item);
    });
}

async function deleteProcessingJob(jobId) {
    if (!jobId || jobId === "undefined" || jobId === "null") {
        alert("Missing job id. Refresh the page (Ctrl+F5) and try again.");
        return;
    }
    const confirmed = window.confirm(
        "Remove this job from the list? Running jobs cannot be removed. Clip files are not deleted.",
    );
    if (!confirmed) return;
    try {
        const apiRoot = `${window.location.protocol}//${window.location.host}`;
        const response = await fetch(`${apiRoot}/api/jobs?id=${encodeURIComponent(jobId)}`, { method: "DELETE" });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            alert(payload.error || "Could not remove job.");
            return;
        }
        if (state.lastAutoReloadJobId === jobId) {
            state.lastAutoReloadJobId = null;
        }
        await refreshSamples();
    } catch (error) {
        console.error(error);
        alert("Remove job request failed.");
    }
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
            <td>${formatTeamDisplayName(event.team)}</td>
            <td>${buildEventDetails(event)}</td>
        </tr>
    `).join("");

    const reportHtml = `
        <!DOCTYPE html>
        <html><head><title>VeoVision Report</title>
        <style>body{font-family:Arial,sans-serif;padding:20px}h1{margin-bottom:4px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #ddd;padding:8px}th{background:#f3f3f3}</style>
        </head><body>
        <h1>VeoVision Match Report</h1>
        <p>Clip: ${escapeHtml(state.activeClip.clipName || state.activeClip.clipId)} (${state.activeClip.category})</p>
        <h2>Summary</h2>
        <ul>
            <li>${TEAM_DISPLAY_NAME[0]} possession: ${t0.possession_percent || 0}%</li>
            <li>${TEAM_DISPLAY_NAME[1]} possession: ${t1.possession_percent || 0}%</li>
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

