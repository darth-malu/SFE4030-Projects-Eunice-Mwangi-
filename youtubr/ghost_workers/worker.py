import subprocess
import shutil
from pytubefix import YouTube, AsyncYouTube
from pytubefix.exceptions import RegexMatchError, VideoUnavailable
from os import makedirs, path

from PySide6.QtCore import QRunnable, Slot, QObject, Signal


class WorkerSignals(QObject):
    finished = Signal()
    message = Signal(str)
    progress = Signal(int)
    error = Signal(str)


class Worker(QRunnable):
    """Async Download Youtube Video + FFMPEG merger
    Intake:
    + self.url_input.text()
    + folder_path

    ---output: download video to output_file (ffmpeg)
    """

    def __init__(self, url: str, folder_path: str = "~/Videos/ytbr") -> None:
        super().__init__()
        # self.url = url.strip()
        self.url = url  # HACK !null
        self.folder_path = path.expanduser(folder_path)
        self.worker_signals = WorkerSignals()
        # self.temp_yt_folder = path.join("/tmp", "ytbr_" + uuid.uuid4().hex)
        self.temp_yt_folder = "/tmp/ytbr"

    def on_progress_callback(self, stream, chunk, bytes_remaining):
        """NOTE Async process (filtering, metadata) so progress-bar hovers at 0 for a while"""
        try:
            total = stream.filesize
            done = total - bytes_remaining
            # percent = int(done * 65 / total)  # HACK only video
            percent = int(done * 100 / total)  # HACK only video
            self.worker_signals.progress.emit(percent)
        except Exception as e:
            self.worker_signals.error.emit(f"Progress callback error: {e}")

    def ffmpeg_merge(self, video_path, audio_path, output_file):
        merge_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c",
            "copy",
            output_file,
        ]

        try:
            # check=True will raise CalledProcessError if FFmpeg fails
            subprocess.run(merge_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # Detailed reporting on FFmpeg failure
            error_message = f"FFmpeg merge failed. Command: {' '.join(merge_cmd)}. Stderr: {e.stderr.strip()}"
            self.worker_signals.error.emit(error_message)
            print(e)
            raise  # Re-raise to trigger the finally block cleanup
        except FileNotFoundError as e:
            self.worker_signals.error.emit("FFmpeg not found in $PATH.")
            print(e)
            raise
        except Exception as e:
            self.worker_signals.error.emit(f"Ffmpeg merger failed:")
            print(e)
            raise

    @Slot()
    def run(self):
        try:
            self.download_video()
        except Exception as e:
            self.worker_signals.error.emit(str(e))
            print(f"@run {e}")
        finally:
            self.worker_signals.finished.emit()  # <--- CRITICAL CHANGE
            if path.exists(self.temp_yt_folder):
                try:  # HACK: CLEANUP temporary files
                    shutil.rmtree(self.temp_yt_folder)
                except Exception as e:
                    self.worker_signals.error.emit(f"Failed to clean up tempFiles:")
                    print(f"@finally {e}")

    def download_video(self):
        # if not self.url:
        #     self.worker_signals.error.emit("Kua Serious Buda ‼️")
        #     return

        makedirs(self.temp_yt_folder, exist_ok=True)
        # HACK TEST
        """Test Cases:
        + RET with empty
        + empty link > if !self.url
        + Invalid Links
        ++ Provide type of error"""

        try:
            yt = YouTube(
                self.url,
                on_progress_callback=self.on_progress_callback,
                # use_oauth=False,
                # allow_oauth_cache=False,
            )

            # Video Stream
            video_streams = (
                yt.streams.filter(
                    file_extension="mp4",
                    only_video=True,
                    res=["1080p", "720p", "480p"],
                )
                .order_by("resolution")
                .desc()
            )

            video_stream = video_streams.first()

            # Audio Stream
            audio_stream = (
                yt.streams.filter(adaptive=True, file_extension="mp4", only_audio=True)
                .order_by("abr")
                .desc()
                .first()
            )

            if not video_stream or not audio_stream:
                self.worker_signals.error.emit(
                    "No suitable video or audio streams found"
                )
                return

        except RegexMatchError:
            self.worker_signals.error.emit("Invalid YouTube URL structure.")
            return

        except VideoUnavailable as e:
            self.worker_signals.error.emit(f"Video unavailable: {e}")
            return

        except Exception as e:
            self.worker_signals.error.emit(f"Error: {e}")
            print(f"exeption download_video() {e}")

        video_file = path.join(self.temp_yt_folder, "video.mp4")
        audio_file = path.join(self.temp_yt_folder, "audio.mp4")

        self.worker_signals.message.emit("Downloading video (1/2) ..")

        # Attach the progress callback ONLY to the video stream object
        # video_stream.on_progress = self.on_progress_callback

        video_stream.download(
            output_path=self.temp_yt_folder,
            filename="video.mp4",
            skip_existing=True,
        )

        self.worker_signals.progress.emit(80)

        # NOTE not tracking audio download
        self.worker_signals.message.emit("Downloading audio (2/2)")
        audio_stream.download(
            output_path=self.temp_yt_folder,
            filename="audio.mp4",
            skip_existing=True,
        )
        self.worker_signals.progress.emit(90)  # HACK. signal merfer start

        # prep output
        safe_title = "".join(c for c in yt.title if c.isalnum() or c in " _-").rstrip()
        output_file = path.join(self.folder_path, f"{safe_title}.mp4")

        # HACK merge - report ffmpeg errors
        try:
            self.worker_signals.message.emit("Merging…😃")
            self.ffmpeg_merge(video_file, audio_file, output_file)
            self.worker_signals.progress.emit(100)
        except Exception as e:
            self.worker_signals.error.emit(str(e))
        else:
            self.worker_signals.message.emit(
                f"Downloaded ↘ {path.basename(output_file)}"
            )
