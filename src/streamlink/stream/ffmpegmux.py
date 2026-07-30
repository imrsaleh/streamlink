from __future__ import annotations

import concurrent.futures
import re
import subprocess
import sys
import threading
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TextIO, TypeVar

from streamlink import StreamError
from streamlink.logger import getLogger
from streamlink.stream.stream import Stream, StreamIO
from streamlink.utils.named_pipe import NamedPipe
from streamlink.utils.processoutput import ProcessOutput


if TYPE_CHECKING:
    from collections.abc import Sequence

    from streamlink.utils.named_pipe import NamedPipeBase


log = getLogger(__name__)

_lock_resolve_command = threading.Lock()


TSubstreams_co = TypeVar("TSubstreams_co", bound=Stream, covariant=True)


class MuxedStream(Stream, Generic[TSubstreams_co]):
    """
    Muxes multiple streams into one output stream.
    """

    __shortname__ = "muxed-stream"

    def __init__(
        self,
        session,
        *substreams: TSubstreams_co,
        **options,
    ):
        """
        :param streamlink.Streamlink session: Streamlink session instance
        :param substreams: Video and/or audio streams
        :param options: Additional keyword arguments passed to :class:`ffmpegmux.FFMPEGMuxer`.
                        Subtitle streams need to be set via the ``subtitles`` keyword.
        """

        super().__init__(session)
        self.substreams: Sequence[TSubstreams_co] = substreams
        self.subtitles: dict[str, Stream] = options.pop("subtitles", {})
        self.options: dict[str, Any] = options

    def open(self):
        fds = []
        metadata = self.options.get("metadata", {})
        maps = self.options.get("maps", [])
        # only update the maps values if they haven't been set
        update_maps = not maps
        for substream in self.substreams:
            log.debug("Opening %s substream", substream.shortname())
            if update_maps:
                maps.append(len(fds))
            fds.append(substream and substream.open())

        for i, subtitle in enumerate(self.subtitles.items()):
            language, substream = subtitle
            log.debug("Opening %s subtitle stream", substream.shortname())
            if update_maps:
                maps.append(len(fds))
            fds.append(substream and substream.open())
            metadata[f"s:s:{i}"] = [f"language={language}"]

        self.options["metadata"] = metadata
        self.options["maps"] = maps

        return FFMPEGMuxer(self.session, *fds, **self.options).open()

    @classmethod
    def is_usable(cls, session):
        return FFMPEGMuxer.is_usable(session)

class FFMPEGMuxer(StreamIO):
    __commands__: ClassVar[list[str]] = ["ffmpeg"]
    __decrypt_commands__: ClassVar[list[str]] = ["mp4decrypt"]
 
    DEFAULT_LOGLEVEL = "info"
    DEFAULT_OUTPUT_FORMAT = "matroska"
    DEFAULT_VIDEO_CODEC = "copy"
    DEFAULT_AUDIO_CODEC = "copy"
 
    FFMPEG_VERSION: str | None = None
    FFMPEG_VERSION_TIMEOUT = 4.0
 
    errorlog: int | TextIO
 
    process: subprocess.Popen | None
 
    @classmethod
    def is_usable(cls, session):
        return cls.command(session) is not None
 
    @classmethod
    def command(cls, session):
        with _lock_resolve_command:
            timeout = session.options.get("ffmpeg-validation-timeout") or cls.FFMPEG_VERSION_TIMEOUT
            return cls._resolve_command(
                session.options.get("ffmpeg-ffmpeg"),
                not session.options.get("ffmpeg-no-validation"),
                timeout,
            )
 
    @classmethod
    @lru_cache(maxsize=128)
    def _resolve_command(
        cls,
        command: str | None = None,
        validate: bool = True,
        timeout: float = FFMPEG_VERSION_TIMEOUT,
    ) -> str | None:
        if command:
            resolved = which(command)
        else:
            resolved = None
            for cmd in cls.__commands__:
                resolved = which(cmd)
                if resolved:
                    break
 
        if resolved and validate:
            log.trace("Querying FFmpeg version: %r", [resolved, "-version"])
            versionoutput = FFmpegVersionOutput([resolved, "-version"], timeout=timeout)
            if not versionoutput.run():
                log.error("Could not validate FFmpeg!")
                log.error("Unexpected FFmpeg version output while running %r", [resolved, "-version"])
                resolved = None
            else:
                cls.FFMPEG_VERSION = versionoutput.version
                for i, line in enumerate(versionoutput.output):
                    log.debug(f" {line}" if i > 0 else line)
 
        if not resolved:
            log.warning("No valid FFmpeg binary was found. See the --ffmpeg-ffmpeg option.")
            log.warning("Muxing streams is unsupported! Only a subset of the available streams can be returned!")
 
        return resolved
 
    @classmethod
    def decrypt_command(cls, session) -> str | None:
        cmd = session.options.get("ffmpeg-mp4decrypt") or None
        return which(cmd) if cmd else which(cls.__decrypt_commands__[0])
 
    @staticmethod
    def copy_to_pipe(muxer: FFMPEGMuxer, stream: StreamIO, pipe: NamedPipeBase):
        log.debug(f"Starting copy to pipe: {pipe.path}")
        # TODO: catch OSError when creating/opening pipe fails and close entire output stream
        pipe.open()
 
        data = b""
        while True:
            try:
                data = stream.read(8192)
            except (OSError, ValueError) as err:
                log.error(f"Error while reading from substream: {err}")
                break
 
            if data == b"":
                log.debug(f"Pipe copy complete: {pipe.path}")
                break
 
            try:
                pipe.write(data)
            except OSError as err:
                if stream.closed or not muxer.process or not muxer.process.poll():
                    log.debug(f"Pipe copy complete: {pipe.path}")
                    break
                log.error(f"Error while writing to pipe {pipe.path}: {err}")
                break
 
        with suppress(OSError):
            pipe.close()
 
    def __init__(self, session, *streams, **options):
        self.session = session
        self.process = None
        self.decrypt_processes: list[subprocess.Popen] = []
        self.decrypt_relay_threads: list[threading.Thread] = []
        self.errorlog = subprocess.DEVNULL
 
        if not self.is_usable(session):
            raise StreamError("Cannot use FFmpeg")
 
        self.streams = streams
 
        # raw pipes: written to by copy_to_pipe() threads (may hold encrypted data)
        self.input_pipes = [NamedPipe() for _ in self.streams]
        self.pipe_threads = [
            threading.Thread(
                target=self.copy_to_pipe,
                args=(self, stream, np),
            )
            for stream, np in zip(self.streams, self.input_pipes, strict=True)
        ]
 
        loglevel = session.options.get("ffmpeg-loglevel") or options.pop("loglevel", self.DEFAULT_LOGLEVEL)
        ofmt = session.options.get("ffmpeg-fout") or options.pop("format", self.DEFAULT_OUTPUT_FORMAT)
        outpath = options.pop("outpath", "pipe:1")
        videocodec = session.options.get("ffmpeg-video-transcode") or options.pop("vcodec", self.DEFAULT_VIDEO_CODEC)
        audiocodec = session.options.get("ffmpeg-audio-transcode") or options.pop("acodec", self.DEFAULT_AUDIO_CODEC)
        metadata = options.pop("metadata", {})
        maps = options.pop("maps", [])
        copyts = session.options.get("ffmpeg-copyts") or options.pop("copyts", False)
        start_at_zero = session.options.get("ffmpeg-start-at-zero") or options.pop("start_at_zero", False)
 
        # --- decryption keys -------------------------------------------------
        # Accepted forms:
        #   "KID:KEY"                      -> applied to every stream
        #   {0: "KID:KEY", 2: "KID:KEY"}   -> per-stream index -> key
        #   ["KID:KEY", None, "KID:KEY"]   -> per-stream list, aligned with `streams`
        dkey = session.options.get("ffmpeg-dkey") or options.pop("dkey", None)
        self.decrypt_keys = self._normalize_keys(dkey, len(self.streams))
 
        if any(self.decrypt_keys) and not self.decrypt_command(session):
            raise StreamError("Cannot use mp4decrypt: binary not found. See the --ffmpeg-mp4decrypt option.")
 
        # ffmpeg reads from `ffmpeg_input_pipes`: either the raw pipe (no key)
        # or a second pipe that sits downstream of an mp4decrypt process.
        self.ffmpeg_input_pipes: list[NamedPipeBase] = []
        for idx, ip in enumerate(self.input_pipes):
            if self.decrypt_keys[idx]:
                self.ffmpeg_input_pipes.append(NamedPipe())
            else:
                self.ffmpeg_input_pipes.append(ip)
 
        # --- build the ffmpeg command (always a real ffmpeg invocation) -----
        self._cmd = [
            self.command(session),
            "-y",
            "-nostats",
            "-loglevel",
            loglevel,
        ]
 
        for p in self.ffmpeg_input_pipes:
            self._cmd.extend(["-i", str(p.path)])
 
        self._cmd.extend(["-c:v", videocodec])
        self._cmd.extend(["-c:a", audiocodec])
 
        for m in maps:
            self._cmd.extend(["-map", str(m)])
 
        if copyts:
            self._cmd.extend(["-copyts"])
            if start_at_zero:
                self._cmd.extend(["-start_at_zero"])
 
        for stream, data in metadata.items():
            for datum in data:
                stream_id = f":{stream}" if stream else ""
                self._cmd.extend([f"-metadata{stream_id}", datum])
 
        self._cmd.extend(["-f", ofmt, outpath])
 
        log.debug("ffmpeg command: %r", self._cmd)
 
        if session.options.get("ffmpeg-verbose-path"):
            self.errorlog = Path(session.options.get("ffmpeg-verbose-path")).expanduser().open("w")
        elif session.options.get("ffmpeg-verbose"):
            self.errorlog = sys.stderr
 
    @staticmethod
    def _normalize_keys(dkey, count: int) -> list[str | None]:
        if not dkey:
            return [None] * count
        if isinstance(dkey, dict):
            return [dkey.get(i) for i in range(count)]
        if isinstance(dkey, (list, tuple)):
            keys = list(dkey) + [None] * (count - len(dkey))
            return keys[:count]
        # single string -> apply to every stream
        return [str(dkey)] * count
 
    def open(self):
        # 1. writers for the raw (possibly encrypted) pipes
        for t in self.pipe_threads:
            t.daemon = True
            t.start()
 
        # 2. one mp4decrypt process per stream that has a key.
        #
        #    IMPORTANT (Windows): a Windows named pipe is a server/single-client
        #    construct, not a kernel FIFO. Two independent external processes
        #    (mp4decrypt and ffmpeg) cannot rendezvous through a pipe path that
        #    neither of them created -- only whichever process called
        #    CreateNamedPipe (here: streamlink/Python) can be an actual
        #    endpoint. So mp4decrypt must NOT write directly to the pipe ffmpeg
        #    reads from; it writes to its own stdout instead ("-stdout#", a
        #    Bento4 special filename), and Python relays those bytes into the
        #    ffmpeg-facing named pipe -- exactly the same pattern already used
        #    for the raw substreams via copy_to_pipe(). Python stays the one
        #    real endpoint of every named pipe, on both Windows and POSIX.
        decrypt_cmd = self.decrypt_command(self.session)
        for idx, key in enumerate(self.decrypt_keys):
            if not key:
                continue
            src = self.input_pipes[idx]
            cmd = [decrypt_cmd, "--key", key, str(src.path), "-stdout#"]
            log.debug("mp4decrypt command: %r", cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=self.errorlog)
            self.decrypt_processes.append(proc)
 
            # relay thread: proc.stdout (decrypted bytes) -> ffmpeg_input_pipes[idx]
            relay = threading.Thread(
                target=self.copy_to_pipe,
                args=(self, proc.stdout, self.ffmpeg_input_pipes[idx]),
            )
            relay.daemon = True
            self.decrypt_relay_threads.append(relay)
 
        for t in self.decrypt_relay_threads:
            t.start()
 
        # 3. ffmpeg reads from ffmpeg_input_pipes and muxes into outpath.
        #    This must come last: it's what unblocks the relay threads'
        #    pipe.open() calls above (and, transitively, mp4decrypt's writes).
        self.process = subprocess.Popen(self._cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=self.errorlog)
 
        return self
 
    def read(self, size=-1):
        return self.process.stdout.read(size)  # type: ignore[attr-defined, ty:unresolved-attribute]
 
    def close(self):
        if self.closed:
            return
 
        log.debug("Closing ffmpeg thread")
        if self.process:
            # kill ffmpeg
            self.process.kill()
            self.process.stdout.close()  # type: ignore[attr-defined, ty:unresolved-attribute]
 
            # kill any mp4decrypt processes still running and close their stdout
            for p in self.decrypt_processes:
                with suppress(Exception):
                    p.kill()
                with suppress(Exception):
                    p.stdout.close()  # type: ignore[union-attr]
 
            executor = concurrent.futures.ThreadPoolExecutor()
 
            # close the substreams
            futures = [
                executor.submit(stream.close)
                for stream in self.streams
                if hasattr(stream, "close") and callable(stream.close)
            ]  # fmt: skip
            concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)
            log.debug("Closed all the substreams")
 
            # wait for substream copy-to-pipe threads to terminate and clean up the opened pipes
            timeout = self.session.options.get("stream-timeout")
            futures = [
                executor.submit(thread.join, timeout=timeout)
                for thread in self.pipe_threads
            ]  # fmt: skip
            concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)
 
            # wait for decrypt-relay threads (mp4decrypt stdout -> ffmpeg pipe) to terminate
            futures = [
                executor.submit(thread.join, timeout=timeout)
                for thread in self.decrypt_relay_threads
            ]  # fmt: skip
            concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)
 
            # wait for mp4decrypt processes to exit
            futures = [
                executor.submit(p.wait, timeout=timeout)
                for p in self.decrypt_processes
            ]  # fmt: skip
            concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)
 
        if self.errorlog is not sys.stderr and not isinstance(self.errorlog, int):
            with suppress(OSError):
                self.errorlog.close()
 
        super().close()

class FFmpegVersionOutput(ProcessOutput):
    # The version output format of the fftools hasn't been changed since n0.7.1 (2011-04-23):
    # https://github.com/FFmpeg/FFmpeg/blame/n5.1.1/fftools/ffmpeg.c#L110
    # https://github.com/FFmpeg/FFmpeg/blame/n5.1.1/fftools/opt_common.c#L201
    # https://github.com/FFmpeg/FFmpeg/blame/c99b93c5d53d8f4a4f1fafc90f3dfc51467ee02e/fftools/cmdutils.c#L1156
    # https://github.com/FFmpeg/FFmpeg/commit/89b503b55f2b2713f1c3cc8981102c1a7b663281
    _re_version = re.compile(r"ffmpeg version (?P<version>\S+)")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.version: str | None = None
        self.output: list[str] = []

    def onexit(self, code: int) -> bool:
        return code == 0 and self.version is not None

    def onstdout(self, idx: int, line: str) -> bool | None:
        # only validate the very first line of the stdout stream
        if idx == 0:
            match = self._re_version.match(line)
            # abort if the very first line of stdout doesn't match the expected format
            if not match:
                return False
            self.version = match["version"]

        self.output.append(line)
