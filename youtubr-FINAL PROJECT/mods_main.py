# using qthread
from PySide6.QtCore import QThread


def start_download(self):
    youtube_url = self.url_input.text()
    if not youtube_url:
        self.url_input.setPlaceholderText("⚠ Please enter a YouTube URL.")
        return

    folder_path = self.get_download_folder()
    if not folder_path:
        self.url_input.setPlaceholderText("🫠 User cancelled")
        return

    # show progress bar
    self.progress_bar.show()
    self.progress_bar.setValue(0)

    # create thread + worker
    self.thread = QThread()
    self.worker = Downloader(youtube_url, folder_path)
    self.worker.moveToThread(self.thread)

    # connect signals
    self.worker.progress.connect(self.progress_bar.setValue)
    self.worker.finished.connect(self.on_download_finished)
    self.worker.finished.connect(self.thread.quit)
    self.worker.finished.connect(self.worker.deleteLater)
    self.thread.finished.connect(self.thread.deleteLater)

    # start thread
    self.thread.started.connect(self.worker.run)
    self.thread.start()


# using signals
from PySide6.QtCore import QObject, Signal, Slot


class Downloader(QObject):
    progress = Signal(int)
    finished = Signal(str)

    def __init__(self, url, folder):
        super().__init__()
        self.url = url
        self.folder = folder

    @Slot()
    def run(self):
        from pytubefix import YouTube

        def on_progress(stream, chunk, bytes_remaining):
            total_size = stream.filesize
            bytes_downloaded = total_size - bytes_remaining
            percent = int((bytes_downloaded / total_size) * 100)
            self.progress.emit(percent)

        yt = YouTube(self.url, on_progress_callback=on_progress)
        stream = yt.streams.get_highest_resolution()
        stream.download(output_path=self.folder)
        self.finished.emit(yt.title)

        # https://chatgpt.com/s/t_68847763b04081918df524838eb523ca
