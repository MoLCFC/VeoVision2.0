# VeoVision Frontend Quick Start

## 🚨 IMPORTANT: Why Videos Won't Play

Browsers block local file access for security reasons. You **MUST** run a web server to view videos.

## ✅ Solution: Start the Local Server

### Windows:
1. Double-click `start_server.bat` in the `veo_frontend` folder
2. OR open PowerShell in the `veo_frontend` folder and run:
   ```powershell
   python -m http.server 8000
   ```

### Mac/Linux:
```bash
cd veo_frontend
python3 -m http.server 8000
```

### Then:
Open your browser to: **http://localhost:8000**

## 🔍 Testing Videos

1. First, test that videos can be found:
   - Open: **http://localhost:8000/debug.html**
   - This will show which videos exist and can be loaded
   - All should show ✓ green checkmarks

2. Then use the main interface:
   - Open: **http://localhost:8000**
   - Click "Show Results" on any video

## 📝 Troubleshooting

### Problem: "Video not found" error
**Solution:** Make sure videos have been processed with the batch script:
```bash
python veo_project/batch_process_all.py --input "regular_clips/sample_content" --output "regular_clips/data_content"
```

### Problem: Videos still won't play
**Check:**
1. Are you using http://localhost:8000 (not file:/// URL)?
2. Run debug.html to verify all videos are found
3. Check browser console (F12) for errors

### Problem: Server won't start
**Try:**
- Different port: `python -m http.server 8080`
- Check if Python is installed: `python --version`

## 🎬 Expected Behavior

### Regular Clips:
Click "Show Results" → Opens modal with:
- Top: Player Detection video
- Bottom Left: 2D Tactical View
- Bottom Right: Heatmap
- Control buttons: Play All, Pause All, Restart All

### Famous Clips:
Click "Show Results" → Opens modal with:
- Single video: Player Detection only

## ✨ Quick Check

Run this in PowerShell from the VeoVision folder:
```powershell
cd veo_frontend
python -m http.server 8000
```

You should see:
```
Serving HTTP on :: port 8000 (http://[::]:8000/) ...
```

Now open: http://localhost:8000

That's it! 🎉

