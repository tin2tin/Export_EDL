# Export EDL
Export Video Sequencer Editor material in EDL files from Blender.

![edl](https://github.com/tin2tin/ExportEDL/blob/master/edl.png "Blender EDL Export")

# Tutorial Video
[![YouTube EDL](https://github.com/tin2tin/ExportEDL/blob/master/yt_edl.png)](https://www.youtube.com/watch?v=WdyMN9tQ21k)
https://www.youtube.com/watch?v=WdyMN9tQ21k

# Location
File > Export > Timeline(.edl)

# Before Exporting
The script will export one .edl file pr. track, so before exporting, merge channels into as few as possible. The Edl format has very limited opportunities to indicate tracks separation(actually only one video and 4 audio).

# Import an EDL in Davinci Resolve
- Set the project framerate to the framerate of the EDL(the edl files do not carry this information)
- Select in project settings "Use time code from source clip frame count", "Assist using reel names from source clip filenames" and "Extract reel names from EDL comments"
- Import all your raw video assets into the Media bins.
- In the Timeline Management pane, click load to import your EDL

# Using the import EDL addon in Blender
( https://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/EDL_Import )
- Open Blender.
- File > User preferences > Addons > Categories > Import – Export > Import – Export Import EDL > Check it.
- Click button > Save user settings (so that setting will be used each time you start Blender).
- Close the user preferences window.
- Change the combo box in the top bar saying Default to Video Editing.
- To the right of the time line you’ll see EDL import
- Click the open folder button under the offset line and select your edl file.
- Click ‘Refresh Reels’.
- Add paths to the missing reels using the open folder buttons.
- When all is set click ‘Import video sequence (.edl)
- The timeline should now show your EDL project.

# Limitations
- No dropframe fps supported.
- Only video, audio clips and dissolves(on same channel) are supported.
- File embedded timecodes and reelnames are not supported. 
