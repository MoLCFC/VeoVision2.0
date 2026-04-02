# 🚀 VeoVision Frontend - Live Server Setup

## Quick Start with Live Server (Port 5000)

### ✅ **RECOMMENDED: Use VS Code Live Server Extension**

1. **Install Live Server extension in VS Code** (if not already installed)
2. **Right-click on `index.html`** in VS Code
3. **Select "Open with Live Server"**
4. It will open at: `http://localhost:5500` or `http://127.0.0.1:5500`
5. Done! Videos should work now.

## 🧪 Testing Videos

### Step 1: Test Simple Video Loading
1. Open `test_simple.html` with Live Server
2. You should see 3 videos load with green ✅ checkmarks
3. Try the "Play All" button
4. If this works, your paths are correct!

### Step 2: Test Main Interface
1. Open `index.html` with Live Server  
2. Scroll to "Regular Clips" section
3. Click "Show Results" on any video (e.g., "08fd33_0")
4. Modal should open with 3 videos
5. Press F12 and check Console tab for debugging info

## 🔍 Debugging Steps

### If videos show but don't play:

**Check Console (F12 → Console tab):**
- Look for messages like: "✓ Main video loaded successfully"
- Or errors like: "FAILED to load main video"

**Console should show:**
```
=== LOADING REGULAR RESULTS ===
Video ID: 08fd33_0
Base path: ../regular_clips/data_content/
Main video path: ../regular_clips/data_content/08fd33_0_combined_result.mp4
✓ Main video loaded successfully
✓ Left video loaded successfully
✓ Right video loaded successfully
```

### If you see "Video not found" errors:

1. **Verify files exist:**
   ```powershell
   dir ..\regular_clips\data_content\
   ```
   Should show:
   - `08fd33_0_combined_result.mp4`
   - `08fd33_0_2d_pitch.mp4`
   - `08fd33_0_combined_pitch_heatmap.mp4`

2. **Check you're in the right folder:**
   - Live Server must be opened from `veo_frontend` folder
   - Or paths must be correct relative to where Live Server starts

## 📁 Folder Structure

```
VeoVision/
├── veo_frontend/              ← Open Live Server HERE
│   ├── index.html             ← Main interface
│   ├── test_simple.html       ← Simple test page
│   ├── debug.html             ← Full debugging page
│   └── ...
├── regular_clips/
│   └── data_content/          ← Videos are here
│       ├── 08fd33_0_combined_result.mp4
│       ├── 08fd33_0_2d_pitch.mp4
│       └── ...
```

## 🎯 Expected Behavior

### Regular Clips:
1. Click "Show Results"
2. Modal opens with 3 videos:
   - **Top**: Player Detection
   - **Bottom Left**: 2D Tactical View  
   - **Bottom Right**: Heatmap
3. Videos load automatically
4. Click "Play All" to start all 3 simultaneously

### Famous Clips:
1. Click "Show Results"
2. Modal opens with 1 video:
   - **Center**: Player Detection only
3. Video loads and can be played with built-in controls

## 🐛 Common Issues

### Issue: "Cross-origin request blocked"
**Fix:** Use Live Server, don't open HTML files directly

### Issue: Videos load but don't play
**Try:** 
- Click the video directly to play it
- Check browser console for errors
- Try "Play All" button multiple times

### Issue: Modal opens but videos are black
**Means:** Videos are loading but haven't started yet
**Fix:** Click "Play All" button or click on each video

### Issue: Wrong video plays
**Check:** Console logs show which video paths are being loaded
**Verify:** File names match exactly (case-sensitive on some servers)

## ✨ Tips

- Use **test_simple.html** first to verify basic video loading works
- Check **Console (F12)** for detailed logging  
- All video operations are logged to console
- Green checkmarks = video loaded successfully
- Red errors = video failed to load

## 🎉 Success Checklist

- [ ] Live Server is running
- [ ] test_simple.html shows 3 green ✅ checkmarks
- [ ] "Play All" button on test page works
- [ ] index.html opens without errors
- [ ] Clicking "Show Results" opens modal
- [ ] 3 videos appear in modal
- [ ] "Play All" button makes videos play

If all checks pass, you're good to go! 🚀

