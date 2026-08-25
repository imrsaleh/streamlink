# this is a fork version of streamlink 8.4.0
![key](https://www.readmecodegen.com/api/social-icon?name=key&size=24)
**New features in this version**

**set Multiple or single decryption keys using** `-ffmpeg-dkey`

```sh
streamlink --ffmpeg-dkey KID1=KEY1 <url> <best>
or
streamlink --ffmpeg-dkey KID1=KEY1:KID2=KEY2 <url> <best>
```

**set custom video fps using** `--ffmpeg-framerate`

it uses libx264 for transcoding by default 
but that could hurt your cpu performance so it can be combined with option `--ffmpeg-video-transcode` to use GPU instead

Nvidia: `h264_nvenc` or `hevc_nvenc`

intel: `h264_qsv` or `hevc_qsv`

AMD: `h264_amf` or `hevc_amf`
*example: change video from (original 50fps) to 25fps*
  ```sh
  streamlink --ffmpeg-framerate 25 <url> <best>
  or
  streamlink --ffmpeg-video-transcode h264_nvenc --ffmpeg-framerate 25 <url> <best>
  ```

  


# 📦 Installation
  ![windows](https://www.readmecodegen.com/api/social-icon?name=windows&size=24) https://github.com/imrsaleh/streamlink/releases/latest


    
  ![linux](https://www.readmecodegen.com/api/social-icon?name=linux&size=24) for linux First u need a custom version of FFMPEG by BtbN

  ```sh
  $ curl -L \
    https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
    -o /tmp/ffmpeg.tar.xz \
    && mkdir -p /tmp/ffmpeg \
    && tar -xJf /tmp/ffmpeg.tar.xz --strip-components=1 -C /tmp/ffmpeg \
    && cp /tmp/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg \
    && rm -rf /tmp/ffmpeg /tmp/ffmpeg.tar.xz
  ```
  
  then..

  ```sh
  $ pip install --no-cache-dir git+https://github.com/imrsaleh/streamlink.git
  ```


# ![coins](https://www.readmecodegen.com/api/social-icon?name=coins&size=24) Credits
  STREAMLINK TEAM: https://github.com/streamlink/streamlink
