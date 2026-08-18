# this is a fork version of streamlink 8.4.0
![key](https://www.readmecodegen.com/api/social-icon?name=key&size=24)
in this version you can set Multiple decryption keys using 

```sh
streamlink --ffmpeg-dkey KID1=KEY1:KID2=KEY2 <url> <best>
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


# ![coins](https://www.readmecodegen.com/api/social-icon?name=coins&size=24) Cridets
  STREAMLINK TEAM: https://github.com/streamlink/streamlink
