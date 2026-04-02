// VeoVision Frontend JavaScript
// Handles video loading, modal display, and synchronization

// Video configuration
const videoData = {
    regular: [
        { id: '08fd33_0', name: '08fd33_0' },
        { id: '0bfacc_0', name: '0bfacc_0' },
        { id: '121364_0', name: '121364_0' },
        { id: '2e57b9_0', name: '2e57b9_0' },
        { id: '573e61_0', name: '573e61_0' }
    ],
    famous: [
        { id: 'jamie_vardy_having_a_party_1', name: 'Jamie Vardy Party' },
        { id: 'yamal_goal_vs_madrid_1', name: 'Yamal vs Madrid' }
    ]
};

// Paths configuration
const paths = {
    regular: {
        sample: '../regular_clips/sample_content/',
        data: '../regular_clips/data_content/'
    },
    famous: {
        sample: '../famous_clips/sample_content/',
        data: '../famous_clips/data_content/'
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('=== VeoVision Frontend Loaded ===');
    console.log('Protocol:', window.location.protocol);
    console.log('URL:', window.location.href);
    console.log('Current paths:', paths);
    
    loadRegularClips();
    loadFamousClips();
});

// Load Regular Clips
function loadRegularClips() {
    const grid = document.getElementById('regular-grid');
    
    videoData.regular.forEach(video => {
        const card = createVideoCard(
            video.id,
            video.name,
            paths.regular.sample + video.id + '.mp4',
            'regular'
        );
        grid.appendChild(card);
    });
}

// Load Famous Clips
function loadFamousClips() {
    const grid = document.getElementById('famous-grid');
    
    videoData.famous.forEach(video => {
        const card = createVideoCard(
            video.id,
            video.name,
            paths.famous.sample + video.id + '.mp4',
            'famous'
        );
        grid.appendChild(card);
    });
}

// Create video card element
function createVideoCard(id, name, videoPath, type) {
    const card = document.createElement('div');
    card.className = 'video-card';
    
    card.innerHTML = `
        <video preload="metadata">
            <source src="${videoPath}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
        <div class="video-card-info">
            <h3 class="video-card-title">${name}</h3>
            <p class="video-card-description">
                ${type === 'regular' 
                    ? 'Full match analysis with AI detection and tactical visualization' 
                    : 'Iconic moment with player detection and team classification'}
            </p>
            <button class="btn btn-results" onclick="showResults('${id}', '${type}')">
                Show Results
            </button>
        </div>
    `;
    
    return card;
}

// Show results modal
function showResults(videoId, type) {
    const modal = document.getElementById('videoModal');
    const modalTitle = document.getElementById('modalTitle');
    
    // Set title
    const videoInfo = videoData[type].find(v => v.id === videoId);
    modalTitle.textContent = videoInfo.name + ' - AI Analysis Results';
    
    if (type === 'regular') {
        showRegularResults(videoId);
    } else if (type === 'famous') {
        showFamousResults(videoId);
    }
    
    // Show modal
    modal.style.display = 'block';
    
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
}

// Show regular clips results (3 videos)
function showRegularResults(videoId) {
    console.log('=== LOADING REGULAR RESULTS ===');
    console.log('Video ID:', videoId);
    
    const regularResults = document.getElementById('regularResults');
    const famousResults = document.getElementById('famousResults');
    const syncControls = document.getElementById('syncControls');
    
    // Show regular layout, hide famous layout
    regularResults.style.display = 'block';
    famousResults.style.display = 'none';
    syncControls.style.display = 'flex';
    
    // Set video sources
    const basePath = paths.regular.data;
    console.log('Base path:', basePath);
    
    const mainVideo = document.getElementById('mainVideo');
    const leftVideo = document.getElementById('leftVideo');
    const rightVideo = document.getElementById('rightVideo');
    
    const mainPath = basePath + videoId + '_combined_result_browser.mp4';
    const leftPath = basePath + videoId + '_2d_pitch_browser.mp4';
    const rightPath = basePath + videoId + '_combined_pitch_heatmap_browser.mp4';
    
    console.log('Main video path:', mainPath);
    console.log('Left video path:', leftPath);
    console.log('Right video path:', rightPath);
    
    // Set src directly on video element (better for compatibility)
    mainVideo.src = mainPath;
    leftVideo.src = leftPath;
    rightVideo.src = rightPath;
    
    // Force reload
    mainVideo.load();
    leftVideo.load();
    rightVideo.load();
    
    // Add error handling for each video
    mainVideo.onerror = function() {
        console.error('FAILED to load main video:', mainVideo.src);
        // Don't show alert, just log error
    };
    
    leftVideo.onerror = function() {
        console.error('FAILED to load left video:', leftVideo.src);
        // Don't show alert, just log error
    };
    
    rightVideo.onerror = function() {
        console.error('FAILED to load right video:', rightVideo.src);
        // Don't show alert, just log error
    };
    
    // Add success handlers
    mainVideo.onloadedmetadata = function() {
        console.log('✓ Main video loaded successfully');
    };
    
    leftVideo.onloadedmetadata = function() {
        console.log('✓ Left video loaded successfully');
    };
    
    rightVideo.onloadedmetadata = function() {
        console.log('✓ Right video loaded successfully');
    };
    
    // Reset and load all videos
    resetAllVideos();
    
    // Try to play automatically after a short delay
    setTimeout(() => {
        console.log('Attempting to play videos...');
        syncPlay();
    }, 500);
}

// Show famous clips results (1 video only)
function showFamousResults(videoId) {
    const regularResults = document.getElementById('regularResults');
    const famousResults = document.getElementById('famousResults');
    const syncControls = document.getElementById('syncControls');
    
    // Show famous layout, hide regular layout
    regularResults.style.display = 'none';
    famousResults.style.display = 'block';
    syncControls.style.display = 'none'; // No sync needed for single video
    
    // Set video source
    const basePath = paths.famous.data;
    const video = document.getElementById('singleVideo');
    video.src = basePath + videoId + '_combined_result_browser.mp4';
    
    // Add error handling
    video.onerror = function() {
        console.error('Failed to load video:', video.src);
        alert('Video not found: ' + video.src.split('/').pop() + '\n\nPlease ensure the video has been processed first.');
    };
    
    // Reset and load video
    video.load();
    video.currentTime = 0;
    
    // Try to play automatically after a short delay
    setTimeout(() => {
        video.play().catch(e => {
            console.log('Autoplay prevented, user needs to click play button');
        });
    }, 500);
}

// Close modal
function closeModal() {
    const modal = document.getElementById('videoModal');
    modal.style.display = 'none';
    
    // Pause all videos
    const videos = document.querySelectorAll('#videoModal video');
    videos.forEach(video => {
        video.pause();
    });
    
    // Restore body scroll
    document.body.style.overflow = 'auto';
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('videoModal');
    if (event.target === modal) {
        closeModal();
    }
}

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeModal();
    }
});

// ==========================================
// Video Synchronization Functions
// ==========================================

function resetAllVideos() {
    const videos = [
        document.getElementById('mainVideo'),
        document.getElementById('leftVideo'),
        document.getElementById('rightVideo')
    ];
    
    videos.forEach(video => {
        if (video && video.src) {
            video.load();
            video.currentTime = 0;
            console.log('Reset video:', video.id);
        }
    });
}

function syncPlay() {
    const videos = [
        document.getElementById('mainVideo'),
        document.getElementById('leftVideo'),
        document.getElementById('rightVideo')
    ];
    
    console.log('Playing all videos...');
    
    // Play all videos simultaneously
    const playPromises = videos.map(video => {
        if (video && video.src) {
            console.log('Playing:', video.id, 'from', video.src);
            return video.play().catch(e => {
                console.error('Play error for', video.id, ':', e);
                return null;
            });
        }
        return Promise.resolve();
    });
    
    Promise.all(playPromises).then(() => {
        console.log('All videos playing (or attempted)');
    });
}

function syncPause() {
    const videos = [
        document.getElementById('mainVideo'),
        document.getElementById('leftVideo'),
        document.getElementById('rightVideo')
    ];
    
    console.log('Pausing all videos...');
    
    videos.forEach(video => {
        if (video && video.src) {
            video.pause();
            console.log('Paused:', video.id);
        }
    });
}

function syncRestart() {
    const videos = [
        document.getElementById('mainVideo'),
        document.getElementById('leftVideo'),
        document.getElementById('rightVideo')
    ];
    
    console.log('Restarting all videos...');
    
    videos.forEach(video => {
        if (video && video.src) {
            video.currentTime = 0;
            video.pause();
            console.log('Restarted:', video.id);
        }
    });
}

// ==========================================
// Video Loading Status
// ==========================================

// Add loading indicators for videos
document.addEventListener('DOMContentLoaded', function() {
    const allVideos = document.querySelectorAll('video');
    
    allVideos.forEach(video => {
        video.addEventListener('loadstart', function() {
            console.log('Loading video...');
        });
        
        video.addEventListener('canplay', function() {
            console.log('Video ready to play');
        });
        
        video.addEventListener('error', function() {
            console.error('Error loading video:', video.src);
        });
    });
});

