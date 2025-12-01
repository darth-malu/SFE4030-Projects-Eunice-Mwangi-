#!/usr/bin/env ipython
"""
youtubr - unified progress bar example (Option A)

Requirements:
- pytubefix (or pytube equivalent)
- PySide6
- ffmpeg available in PATH

This script:
- Downloads video and audio separately
- Uses a single progress bar:
    0 - 40%   -> video download
   40 - 80%   -> audio download
   80 - 100%  -> ffmpeg merging phase (simulated smooth progress while ffmpeg runs)
"""

from pytubefix import YouTube
from sys import argv as ARGV, exit as EXIT
from os import makedirs, path
import subprocess
import time
import uuid

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
    QProgressBar,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, QRunnable, Slot, QThreadPool, QObject, Signal, QTimer


# -------------------------
# Signals + Worker
# -------------------------
class WorkerSignals(QObject):
    finished = Signal()
    message = Signal(str)
    progress = Signal(int)  # unified percent 0..100
    error = Signal(str)


class Worker(QRunnable):
    """
    Worker downloads video and audio and merges using ffmpeg.
    Emits unified progress values via worker_signals.progress
    """

    def __init__(self, url: str, folder_path: str):
        super().__init__()
        self.url = url.strip()
        self.folder_path = path.expanduser(folder_path)
        self.worker_signals = WorkerSignals()

        # For progress tracking
        self.video_size = 0
        self.audio_size = 0
        self.video_done = 0
        self.audio_done = 0

        # stream holders (to identify in callback)
        self._video_itag = None
        self._audio_itag = None

        # Which stream is currently being downloaded (for debug)
        self._current_stream = None

        # weights
        self.W_VIDEO = 0.40  # 40%
        self.W_AUDIO = 0.40  # 40%
        self.W_MERGE = 0.20  # 20%

    def _get_stream_size(self, stream):
        # pytube sometimes uses 'filesize' or 'filesize_approx'
        return int(
            getattr(stream, "filesize", 0) or getattr(stream, "filesize_approx", 0) or 0
        )

    def _emit_unified_progress(self, merge_fraction=0.0):
        """
        Compute unified percent from video/audio bytes + merge fractional progress (0..1).
        merge_fraction applies only to the final W_MERGE.
        """
        # Avoid division by zero; if size is zero treat fraction as 0
        v_frac = (self.video_done / self.video_size) if self.video_size else 0.0
        a_frac = (self.audio_done / self.audio_size) if self.audio_size else 0.0

        unified = (
            v_frac * self.W_VIDEO
            + a_frac * self.W_AUDIO
            + merge_fraction * self.W_MERGE
        )
        # convert to 0..100 int
        percent = int(unified * 100)
        # clamp
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        self.worker_signals.progress.emit(percent)

    def on_progress_callback(self, stream, chunk, bytes_remaining):
        """
        Called by pytube/pytubefix for each chunk. We identify which stream by its itag.
        """
        try:
            total = self._get_stream_size(stream)
            done = total - bytes_remaining
            if stream.itag == self._video_itag:
                self.video_done = max(0, min(total, done))
            elif stream.itag == self._audio_itag:
                self.audio_done = max(0, min(total, done))
            # Emit unified progress (merge fraction is 0 while downloading)
            self._emit_unified_progress(merge_fraction=0.0)
        except Exception as e:
            # Ensure that any unexpected error during progress doesn't crash the worker thread silently.
            # Emit error and stop (caller will hide the bar).
            self.worker_signals.error.emit(f"Progress callback error: {e}")

    @Slot()
    def run(self):
        # Main worker logic
        try:
            if not self.url:
                self.worker_signals.error.emit("No URL provided")
                return

            # Prepare folder
            makedirs(self.folder_path, exist_ok=True)

            # Create isolated temp folder per job
            temp_yt_folder = path.join("/tmp", "ytbr_" + uuid.uuid4().hex)
            makedirs(temp_yt_folder, exist_ok=True)

            # Create YouTube object WITHOUT global on_progress (we'll pass on_progress via YouTube to pick up which stream)
            yt = YouTube(
                self.url,
                use_oauth=False,
                allow_oauth_cache=False,
                on_progress_callback=self.on_progress_callback,
            )

            # select streams
            # Prefer available resolutions; fall back gracefully
            video_streams = (
                yt.streams.filter(
                    file_extension="mp4", only_video=True, res=["1080p", "720p", "480p"]
                )
                .order_by("resolution")
                .desc()
            )
            video_stream = video_streams.first()
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

            # Save itags and sizes
            self._video_itag = video_stream.itag
            self._audio_itag = audio_stream.itag
            self.video_size = self._get_stream_size(video_stream)
            self.audio_size = self._get_stream_size(audio_stream)

            # If sizes are zero, try to set to 1 to avoid division by zero;
            # progress will be best-effort
            if self.video_size == 0:
                self.video_size = 1
            if self.audio_size == 0:
                self.audio_size = 1

            # Prepare temp filenames
            video_file = path.join(temp_yt_folder, "video.mp4")
            audio_file = path.join(temp_yt_folder, "audio.mp4")

            # Reset done counters
            self.video_done = 0
            self.audio_done = 0

            # Download video
            self._current_stream = "video"
            self.worker_signals.message.emit("Downloading video...")
            # stream.download will trigger on_progress_callback
            video_stream.download(
                output_path=temp_yt_folder, filename="video.mp4", skip_existing=False
            )

            # Ensure we mark video as fully done (some callbacks might have rounding)
            self.video_done = self.video_size
            self._emit_unified_progress(merge_fraction=0.0)

            # Download audio
            self._current_stream = "audio"
            self.worker_signals.message.emit("Downloading audio...")
            audio_stream.download(
                output_path=temp_yt_folder, filename="audio.mp4", skip_existing=False
            )

            # Mark audio done
            self.audio_done = self.audio_size
            self._emit_unified_progress(merge_fraction=0.0)

            # Prepare final output
            safe_title = (
                "".join(c for c in yt.title if c.isalnum() or c in " _-").rstrip()
                or "ytdl"
            )
            output_file = path.join(self.folder_path, f"{safe_title}.mp4")

            # Ensure output folder exists (again, in case)
            makedirs(path.dirname(output_file), exist_ok=True)

            # Start ffmpeg merge
            self.worker_signals.message.emit("Merging streams...")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                video_file,
                "-i",
                audio_file,
                "-c",
                "copy",
                output_file,
            ]

            # We'll run ffmpeg in a subprocess and simulate a smooth merge progress while it runs.
            # Start process and poll while alive. We'll measure elapsed time and linearly increase merge fraction
            # up to 99% while process is running, then set 100% on completion.
            proc = subprocess.Popen(
                ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            merge_start = time.time()
            last_emit = 0.0
            # simulate progressive merging progress while ffmpeg runs
            # We'll increase merge_fraction from 0.0 -> 0.99 over up to 12 seconds (arbitrary ramp).
            # If ffmpeg ends earlier, we'll jump to 1.0 immediately. This gives a smooth UX.
            ramp_seconds = 12.0

            while True:
                if proc.poll() is not None:
                    # finished
                    break
                elapsed = time.time() - merge_start
                # fractional progress capped at 0.99 while running
                frac = min(0.99, elapsed / ramp_seconds)
                # only emit when changed enough to avoid flooding
                if abs(frac - last_emit) >= 0.005:
                    self._emit_unified_progress(merge_fraction=frac)
                    last_emit = frac
                time.sleep(0.08)

            # Wait for process to finalize and capture returncode
            stdout, stderr = proc.communicate(timeout=5)
            if proc.returncode != 0:
                # Include ffmpeg stderr in reported error for debugging
                self.worker_signals.error.emit(f"ffmpeg failed: {stderr.strip()[:400]}")
                return

            # Finalize: mark merge done
            self._emit_unified_progress(merge_fraction=1.0)

            self.worker_signals.message.emit(" Download Complete ✔ ")
            self.worker_signals.finished.emit()

        except Exception as e:
            self.worker_signals.error.emit(str(e))


# -------------------------
# Main UI
# -------------------------
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.placeholder = "Enter YouTube Link       "
        self.default_dwn_location = self.default_download_path()
        self.threadpool = QThreadPool()
        self.main_ui()
        self.show()

    def main_ui(self):
        self.setWindowTitle("youtubr")
        self.setMinimumSize(420, 120)

        # URL input
        self.url_input = QLineEdit()
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setPlaceholderText(self.placeholder)
        self.url_input.returnPressed.connect(self.url_download_on_return)

        # file chooser button
        self.file_choose_btn = QPushButton("📂")
        self.file_choose_btn.clicked.connect(self.file_chooser)
        self.file_choose_btn.setMaximumWidth(60)

        # path label
        self.download_path_label = QLabel(f"{self.format_dwn_path()}")
        self.download_path_label.setAlignment(Qt.AlignRight)
        self.download_path_label.setContentsMargins(0, 7, 8, 0)

        # combined layout for URL + button
        button_url_combo_layout = QHBoxLayout()
        button_url_combo_layout.addWidget(self.url_input)
        button_url_combo_layout.addWidget(self.file_choose_btn)
        button_url_combo_widget = QWidget()
        button_url_combo_widget.setLayout(button_url_combo_layout)

        # progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()

        # layout
        layout = QVBoxLayout()
        layout.addWidget(button_url_combo_widget)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.download_path_label)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def default_download_path(self) -> str:
        return path.expanduser("~/Videos/ytbr")

    def format_dwn_path(self) -> str:
        # Show tilde for home
        display = self.default_dwn_location.replace(path.expanduser("~"), "~")
        return display

    def get_download_folder(self) -> str | None:
        dialog = QFileDialog(self, "Select Download Folder ...")
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec():
            return dialog.selectedFiles()[0]
        return None

    def worker_init(self, folder: str | None = None) -> None:
        # Use folder if provided, else use default
        folder_path = folder or self.default_dwn_location
        worker = Worker(self.url_input.text(), folder_path)

        # UI wiring
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        worker.worker_signals.finished.connect(self.on_worker_finished)
        worker.worker_signals.progress.connect(self.progress_bar.setValue)
        worker.worker_signals.message.connect(self.update_placeholder_message)
        worker.worker_signals.error.connect(self.on_worker_error)

        self.threadpool.start(worker)

    def on_worker_finished(self):
        # show complete in placeholder briefly
        self.url_input.clear()
        self.url_input.setPlaceholderText("Download Complete ✔")
        # hide bar after a short moment
        QTimer.singleShot(1200, self.progress_bar.hide)
        # reset placeholder after a bit
        QTimer.singleShot(
            2000, lambda: self.url_input.setPlaceholderText(self.placeholder)
        )

    def on_worker_error(self, err: str):
        self.progress_bar.hide()
        self.url_input.setPlaceholderText(f"❌ {err}")

    def update_placeholder_message(self, text: str):
        # Non-blocking UI updates from worker events
        self.url_input.setPlaceholderText(text)

    def url_download_on_return(self):
        folder_path = self.default_dwn_location
        try:
            makedirs(folder_path, exist_ok=True)
        except Exception as e:
            self.url_input.setPlaceholderText(
                f"❌ Failed to access folder {folder_path}: {e}"
            )
            return
        self.worker_init(folder_path)

    def file_chooser(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.default_dwn_location
        )
        if folder:
            self.default_dwn_location = folder  # update default location
            self.download_path_label.setText(
                f"{folder.replace(path.expanduser('~'), '~')}"
            )
            # Start worker using chosen folder
            self.worker_init(folder)
        else:
            self.url_input.setPlaceholderText(" No folder selected ❗❗")


def main():
    app = QApplication(ARGV)
    win = MainApp()
    EXIT(app.exec())


if __name__ == "__main__":
    main()
