# Streamlink (Modified Fork)

This is a custom fork of [Streamlink](https://github.com/streamlink/streamlink) based on version 8.4.0, featuring extended FFmpeg options for decryption and video transcoding.

---

## 🌟 New Features

### 1. Multiple or Single Decryption Keys (`--ffmpeg-dkey`)
Set one or multiple decryption keys directly using `--ffmpeg-dkey`:

```sh
# Single key
streamlink --ffmpeg-dkey KID1=KEY1 <url> best

# Multiple keys
streamlink --ffmpeg-dkey KID1=KEY1:KID2=KEY2 <url> best
```



### 2. Custom Video Frame Rate (--ffmpeg-framerate)

Change the video framerate on the fly. By default, it uses libx264 for software encoding, which can be CPU intensive.

You can combine it with --ffmpeg-video-transcode to enable hardware acceleration (GPU):

NVIDIA: h264_nvenc or hevc_nvenc

Intel: h264_qsv or hevc_qsv

AMD: h264_amf or hevc_amf

Example: Change video framerate from 50fps to 25fps:

```sh
# Software encoding (CPU)
streamlink --ffmpeg-framerate 25 <url> best

# Hardware encoding (NVIDIA GPU)
streamlink --ffmpeg-video-transcode h264_nvenc --ffmpeg-framerate 25 <url> best
  ```

  


# 📦 Installation
  
  ### Windows ![windows](https://www.readmecodegen.com/api/social-icon?name=windows&size=24)
  
  Download the latest Windows binary release from
  https://github.com/imrsaleh/streamlink/releases/latest

  ---
    
  ### Linux ![linux](https://www.readmecodegen.com/api/social-icon?name=linux&size=24) 
   Install a compatible build of FFmpeg (e.g., BtbN builds):

  ```sh
  $ curl -L \
    https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
    -o /tmp/ffmpeg.tar.xz \
    && mkdir -p /tmp/ffmpeg \
    && tar -xJf /tmp/ffmpeg.tar.xz --strip-components=1 -C /tmp/ffmpeg \
    && cp /tmp/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg \
    && rm -rf /tmp/ffmpeg /tmp/ffmpeg.tar.xz
  ```
  
  Install this modified Streamlink version via pip:

  ```sh
  $ pip install --no-cache-dir git+https://github.com/imrsaleh/streamlink.git
  ```



  STREAMLINK TEAM: https://github.com/streamlink/streamlink


# ![coins](https://www.readmecodegen.com/api/social-icon?name=coins&size=24) Credits
- Original project by [Streamlink](https://github.com/streamlink/streamlink)