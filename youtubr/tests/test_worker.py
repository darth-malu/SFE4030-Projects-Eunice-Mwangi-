import os
import shutil
import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest
from ghost_workers.worker import Worker, WorkerSignals


# --- FIXME: Add the project root to sys.path for module discovery ---
# This ensures that 'ghost_workers' can be imported regardless of where the pytest command is executed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# --- Fixtures ---
@pytest.fixture
def url_input():
    """Provides a valid, mock YouTube URL."""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def folder_path_input():
    """Provides a custom output folder path for testing."""
    # Using an absolute path that will be expanded by os.path.expanduser if needed
    return "/home/malu/Videos/ytbr/tests/kfjkfj"


@pytest.fixture
def worker_instance(url_input, folder_path_input):
    """Provides a fresh Worker instance for each test."""
    return Worker(url_input, folder_path_input)


# Mock the WorkerSignals class itself to ensure a clean, isolated mock is created every time the Worker constructor is called.
# We use autouse=True to ensure the patch is applied to all tests.
@pytest.fixture(autouse=True)
def mock_signals_class(mocker):
    """Patches WorkerSignals class to use a MagicMock for every test."""
    # Create a mock instance with mocked .emit method for error signal checks
    mock_error_emit = mocker.MagicMock()
    mock_signals_instance = mocker.MagicMock(
        finished=mocker.MagicMock(emit=mocker.MagicMock()),
        message=mocker.MagicMock(emit=mocker.MagicMock()),
        progress=mocker.MagicMock(emit=mocker.MagicMock()),
        error=mocker.MagicMock(emit=mock_error_emit),  # Focus on the emit method
    )

    # Patch the *class* itself in the module where Worker is defined
    mocker.patch(
        "ghost_workers.worker.WorkerSignals", return_value=mock_signals_instance
    )

    # Return the mock instance's error.emit for easy assertion
    return mock_signals_instance.error.emit


# Test Initialization
def test_worker_initialization(worker_instance, url_input, folder_path_input):
    """Test if Worker is initialized correctly."""
    assert worker_instance.url == url_input
    # os.path.expanduser is used in __init__
    assert worker_instance.folder_path == os.path.expanduser(folder_path_input)
    assert worker_instance.temp_yt_folder == "/tmp/ytbr"


# Test Empty URL Error
def test_download_video_empty_url(worker_instance, mock_signals_class):
    """Test that an error signal is emitted for an empty URL within download_video."""
    worker_instance.url = ""
    worker_instance.download_video()

    mock_signals_class.assert_called_once_with("Kua Serious Buda ‼️")


# FFmpeg Merge Success
@patch("subprocess.run")
def test_ffmpeg_merge_success(mock_run, worker_instance):
    """Test successful FFmpeg merge command execution."""
    mock_run.return_value = MagicMock(returncode=0)

    video_path = "/tmp/ytbr/video.mp4"
    audio_path = "/tmp/ytbr/audio.mp4"
    output_file = "/home/user/Videos/ytbr/output.mp4"  # Dummy path

    worker_instance.ffmpeg_merge(video_path, audio_path, output_file)

    expected_cmd = [
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
    mock_run.assert_called_once_with(
        expected_cmd, check=True, capture_output=True, text=True
    )


# Test FFmpeg Merge Failure (CalledProcessError)
@patch("subprocess.run")
def test_ffmpeg_merge_failure(mock_run, worker_instance, mock_signals_class):
    """Test handling of subprocess.CalledProcessError during FFmpeg merge."""
    error_output = "FFmpeg failed to process stream."
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="ffmpeg", stderr=error_output
    )

    # Assert that the CalledProcessError is re-raised
    with pytest.raises(subprocess.CalledProcessError):
        worker_instance.ffmpeg_merge("v", "a", "o")

    error_call = mock_signals_class.call_args[0][0]
    assert error_call.startswith("FFmpeg merge failed. Command: ")
    assert error_call.endswith(f". Stderr: {error_output}")


# Test FFmpeg Not Found (FileNotFoundError)
@patch("subprocess.run")
def test_ffmpeg_not_found(mock_run, worker_instance, mock_signals_class):
    """Test handling of FileNotFoundError (FFmpeg not in $PATH)."""
    mock_run.side_effect = FileNotFoundError()

    # Assert that the FileNotFoundError is re-raised
    with pytest.raises(FileNotFoundError):
        worker_instance.ffmpeg_merge("v", "a", "o")

    mock_signals_class.assert_called_once_with("FFmpeg not found in $PATH.")


# Test Progress Callback
def test_on_progress_callback(worker_instance):
    """Test that progress signal is correctly emitted with the right percentage."""
    mock_stream = MagicMock()
    mock_stream.filesize = 1000  # Total bytes
    bytes_remaining = 500

    worker_instance.on_progress_callback(mock_stream, b"chunk", bytes_remaining)

    worker_instance.worker_signals.progress.emit.assert_called_once_with(50)


# --- Test Cleanup in run() ---


@patch("os.path.exists", return_value=True)
@patch("shutil.rmtree")
@patch("ghost_workers.worker.Worker.download_video")
def test_run_cleanup_on_success(
    mock_download, mock_rmtree, mock_exists, worker_instance
):
    """Test cleanup (rmtree) is called when run() succeeds."""
    mock_download.return_value = None

    worker_instance.run()

    worker_instance.worker_signals.finished.emit.assert_called_once()
    mock_rmtree.assert_called_once_with(worker_instance.temp_yt_folder)


@patch("os.path.exists", return_value=True)
@patch("shutil.rmtree")
@patch(
    "ghost_workers.worker.Worker.download_video",
    side_effect=ValueError("Test Download Error"),
)
def test_run_cleanup_on_failure(
    mock_download, mock_rmtree, mock_exists, worker_instance, mock_signals_class
):
    """Test cleanup (rmtree) is called when run() fails."""

    worker_instance.run()

    mock_signals_class.assert_called_once_with("Test Download Error")
    mock_rmtree.assert_called_once_with(worker_instance.temp_yt_folder)


# --- Mock PyTubeFix stream selection ---


# Decorators (order 1-5, top to bottom)
@patch("ghost_workers.worker.YouTube")  # 1
@patch("ghost_workers.worker.makedirs")  # 2
@patch("ghost_workers.worker.Worker.ffmpeg_merge")  # 3
@patch("os.path.join", side_effect=lambda *args: "/".join(args))  # 4
@patch("ghost_workers.worker.Worker.on_progress_callback")  # 5
def test_download_video_logic(
    mock_callback,  # Corresponds to 5 (on_progress_callback)
    mock_path_join,  # Corresponds to 4 (os.path.join)
    mock_merge,  # Corresponds to 3 (Worker.ffmpeg_merge)
    mock_makedirs,  # Corresponds to 2 (os.makedirs)
    mock_youtube,  # Corresponds to 1 (YouTube)
    worker_instance,  # The fixture (no patch)
):
    """Test the stream selection, file system calls, and merge preparation."""
    # 1. Setup Mock Streams
    mock_stream_video = MagicMock(filesize=1000000)
    mock_stream_audio = MagicMock(filesize=10000)

    # 2. Setup YouTube mock object
    mock_yt_instance = mock_youtube.return_value
    mock_yt_instance.title = "TestYtTitle"

    # 3. Setup the stream filtering and ordering chain
    mock_streams = MagicMock()
    # Mocking the chain: .filter().order_by().desc()
    mock_yt_instance.streams.filter.return_value.order_by.return_value.desc.return_value = (
        mock_streams
    )

    # The first() call is made twice: once for video, once for audio
    mock_streams.first.side_effect = [mock_stream_video, mock_stream_audio]

    # 4. Execute the method
    worker_instance.download_video()

    # 5. Assertions

    # Assert file system calls
    mock_makedirs.assert_called_once_with(worker_instance.temp_yt_folder, exist_ok=True)

    # Assert download calls
    mock_stream_video.download.assert_called_once_with(
        output_path=worker_instance.temp_yt_folder,
        filename="video.mp4",
        skip_existing=True,
    )
    mock_stream_audio.download.assert_called_once_with(
        output_path=worker_instance.temp_yt_folder,
        filename="audio.mp4",
        skip_existing=True,
    )

    # Assert merge call (safe_title removes spaces and special chars)
    safe_title = "TestYtTitle"
    expected_output = f"{worker_instance.folder_path}/{safe_title}.mp4"
    mock_merge.assert_called_once_with(
        f"{worker_instance.temp_yt_folder}/video.mp4",
        f"{worker_instance.temp_yt_folder}/audio.mp4",
        expected_output,
    )
