## OpenCV 4.12.0 + GTK 3.24.51

### Notes about OpenCV 4.x recipe
* GTK is disabled by default
* Wayland is enabled
* OpenVC
* FFMpeg results in: ERROR: Version conflict: Conflict between freetype/2.13.2 and freetype/2.14.1 in the graph.

### Notes about GTK-3
* Wayland is disabled by default
* and X11 is enabled by default

#### Logs

Build Log: ![opencv-4.12.0-linux-amd64-gcc13-release-shared-gtk3.log](opencv-4.12.0-linux-amd64-gcc13-release-shared-gtk3.log)
Test GTK LDD: ![opencv-4.12.0-test-gtk-ldd.log](opencv-4.12.0-test-gtk-ldd.log)

## OpenCV 4.12.0 + GTK 3.24.51

### Notes about OpenCV 3.x recipe
* GTK is enabled by default


#### Logs

Build Log: ![opencv-3.4.20-linux-amd64-gcc13-release-shared-gtk3.log](opencv-3.4.20-linux-amd64-gcc13-release-shared-gtk3.log)
Test GTK LDD:


## OpenCV 2.4.13.7 + GTK 3.24.51

* OpenCV 2.x only supports GTK-2: https://github.com/opencv/opencv/blob/2.4/CMakeLists.txt#L150
