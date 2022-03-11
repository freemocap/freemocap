# FreeMoCap Version History
__________________________

# Version - v0.0.43
 ```
  Date - 2021-11-28
  Status - Pre-Alpha
```
## Summary

v0.0.43 is probably the last major update we'll make to the `pre-alpha` version of FreeMoCap. There will almost certainly be many bugfixes and usability tweaks, but no new major "deep level" development is intended on *this* iteration of this codebase.

A notable exception to the previous statement is the [Blender](https://blender.org) related functionality introduced in this release! These features are all still experimental and will be getting a lot of attention and upgrades in the coming weeks/months. Keep an eye out for updates!

The current `pre-alpha` version is a reasonably stable, reliable piece of code that performs its intended purposes fairly well. However, it still not particularly well-built for easy use by people outside of my lab (i.e. outside of the group that originally built it). We have learned a tremendous amount from this process of development, and will be taking those lessons into the next development phase. 

The next iteration (v0.1.0 - `freemocap-alpha`) will be a massive, near-complete overhaul that carries over very little of the current codebase. 

~✨💀✨~

----
## Significant Changes
- Updated ReadMe!

- Labels and print statements overhauled to make things prettier and (hopefully) more intuitive and user-friendly (with heavy use of the [Rich](https://github.com/willmcgugan/rich) Python package)




- Setting Calibration default settings to use the first half of the recording rather than the full recording. We've found this makes AniPose more likely to complete successfully. We also added some tweaks and `try/except` block to make the Anipose calibration more reliable


- Tweaks to make it easier to run freemocap on a folder of synced video from another source (e.g GoPros!)! Just place the synced videos (each of which has **exactly** the same number of frames)  in a folder called `SyncedVideos`, place this folder in a folder called named whatever you want the `SessionID` to be, place THAT folder in the `FreeMoCap_Data` folder, and run freemocap on that session folder starting at stage 3 (so if the  `sessionID` is `test-session`, run - `freemocap.RunMe(sessionID='test-session', stage=3)`)



- Clean up unnecessary output folders (from MediaPipe, etc)
 
- OpenPose no longer saves images for each frame of each camera, which makes session folders MUCH smaller and easier to move around -  ()It still saves a one JSON per frame per camera though)

 - Option to plot a (MUCH LOWER ACCURACY) MediaPipe skeleton overlaid on SetUp video feed from each camera. Useful for helping set up cameras to provide good data. 

 - Added 'frame number' to animation output
  

 - Animation output method will first attempt to use an `ffmpeg-enabled` exporter, and if that fails it will try a much slower `pillow based` method (and print instructions on how the user can install `ffmpeg`)

- (EXPERIMENTAL, but exciting!) Output MediaPipe skeletonto `.blend`, `.fbx`, `.usd`, .`gltf` formats (requires [Blender](https://blender.org) installed). This will be getting a lot of attention in the coming weeks, so keep an eye out for future updates!

- (EXPERIMENTAL) Minimally functional Blender addon added in `/freemocap_blender_addon`














## Major Changes

- Full overhaul of labels and terminal output (including heavy use the the [Rich](https://github.com/willmcgugan/rich) python package)to improve usability and provide better feedback and support 
  
- Support reconstruction of externally recorded videos (e.g. GoPros)
- (EXPERIMENTAL) Output data to `.blend`, `.fbx`, `.usd`, .`gltf` formats (requires [Blender](https://blender.org) installed) 
- (EXPERIMENTAL) Minimally functional Blender addon added in `/freemocap_blender_addon`


 - Multitudinous bug fixes

____________________________
