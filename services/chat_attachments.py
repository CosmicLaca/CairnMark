"""Media conversion rules for model and preview chat attachments."""

import base64
import io
import tempfile
from functools import partial
from pathlib import Path

from flask import current_app


MAX_IMAGE_PIXELS = 1_200_000


class AttachmentProcessingError(RuntimeError):
    """Raised when media cannot be converted into a safe model attachment."""


def resize_image_attachment(attachment):
    """Resize an image attachment above 1.2 megapixels when Pillow is available."""
    if not isinstance(attachment, dict) or attachment.get("type") != "image":
        return attachment
    try:
        from PIL import Image
    except ImportError:
        return attachment
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
        with Image.open(io.BytesIO(decoded)) as image:
            pixels = image.width * image.height
            if pixels <= MAX_IMAGE_PIXELS:
                return attachment
            scale = (MAX_IMAGE_PIXELS / pixels) ** 0.5
            size = (
                max(1, int(image.width * scale)),
                max(1, int(image.height * scale)),
            )
            resized = image.resize(size, Image.LANCZOS)
            if resized.mode in ("RGBA", "P"):
                resized = resized.convert("RGB")
            output = io.BytesIO()
            resized.save(output, format="JPEG", quality=90)
            return {
                "type": "image",
                "data": base64.b64encode(output.getvalue()).decode("ascii"),
                "mime_type": "image/jpeg",
            }
    except Exception:  # noqa: BLE001
        return attachment


def convert_video_attachment(attachment):
    """Re-encode video to silent MP4 with a 480px maximum side and 2 fps."""
    if not isinstance(attachment, dict) or attachment.get("type") != "video":
        return attachment
    try:
        import ffmpeg
    except ImportError as error:
        raise AttachmentProcessingError(
            "Video attachments require FFmpeg to remove the audio track."
        ) from error
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
    except Exception as error:  # noqa: BLE001
        raise AttachmentProcessingError("Video attachment data is invalid.") from error

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            input_path = workspace / "input"
            output_path = workspace / "output.mp4"
            input_path.write_bytes(decoded)
            probe = ffmpeg.probe(str(input_path))
            streams = probe.get("streams", []) if isinstance(probe, dict) else []
            video_stream = next(
                (stream for stream in streams if stream.get("codec_type") == "video"),
                None,
            )
            if video_stream is None:
                raise AttachmentProcessingError(
                    "The attachment does not contain a video track."
                )
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
            if width <= 0 or height <= 0:
                raise AttachmentProcessingError(
                    "The video dimensions could not be determined."
                )
            video = ffmpeg.input(str(input_path)).video
            if max(width, height) > 480:
                video = video.filter(
                    "scale",
                    480 if width >= height else -2,
                    -2 if width >= height else 480,
                )
            video = video.filter("fps", fps=2)
            ffmpeg.output(
                video,
                str(output_path),
                an=None,
                vcodec="libx264",
                crf=28,
                preset="fast",
                pix_fmt="yuv420p",
                movflags="+faststart",
            ).overwrite_output().run(quiet=True)
            converted = output_path.read_bytes()
            if not converted:
                raise AttachmentProcessingError("The converted video is empty.")
            return {
                "type": "video",
                "data": base64.b64encode(converted).decode("ascii"),
                "mime_type": "video/mp4",
                "preview_data": attachment.get("preview_data"),
            }
    except AttachmentProcessingError:
        raise
    except Exception as error:  # noqa: BLE001
        current_app.logger.exception("Video attachment could not be converted")
        raise AttachmentProcessingError(
            "Video attachment could not be converted without audio."
        ) from error


def convert_audio_attachment(attachment, *, fallback_to_original=True):
    """Extract an audio stream as 64 kbit/s MP3, with configurable fallback."""
    fallback = attachment if fallback_to_original else None
    if not isinstance(attachment, dict):
        return fallback
    try:
        import ffmpeg
    except ImportError:
        return fallback
    try:
        decoded = base64.b64decode(attachment["data"], validate=True)
    except Exception:  # noqa: BLE001
        return fallback

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            input_path = workspace / "input"
            output_path = workspace / "output.mp3"
            input_path.write_bytes(decoded)
            probe = ffmpeg.probe(str(input_path))
            streams = probe.get("streams", []) if isinstance(probe, dict) else []
            if not any(stream.get("codec_type") == "audio" for stream in streams):
                return fallback
            ffmpeg.output(
                ffmpeg.input(str(input_path)).audio,
                str(output_path),
                acodec="libmp3lame",
                audio_bitrate="64k",
            ).overwrite_output().run(quiet=True)
            converted = output_path.read_bytes()
            if not converted:
                return fallback
            return {
                "type": "audio",
                "data": base64.b64encode(converted).decode("ascii"),
                "mime_type": "audio/mpeg",
                "preview_data": attachment.get("preview_data"),
            }
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Audio attachment could not be converted")
        return fallback


def video_has_audio(data):
    """Return whether base64 media contains an audio stream."""
    try:
        import ffmpeg

        decoded = base64.b64decode(data, validate=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "input"
            input_path.write_bytes(decoded)
            probe = ffmpeg.probe(str(input_path))
            streams = probe.get("streams", []) if isinstance(probe, dict) else []
            return any(
                stream.get("codec_type") == "audio" for stream in streams
            )
    except Exception:  # noqa: BLE001
        return False


def merge_video_audio(video_data, audio_data):
    """Mux a converted silent video and separate audio track into one MP4."""
    if not video_data or not audio_data:
        return None
    try:
        import ffmpeg
    except ImportError:
        return None

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            video_path = workspace / "video.mp4"
            audio_path = workspace / "audio.mp3"
            output_path = workspace / "merged.mp4"
            video_path.write_bytes(base64.b64decode(video_data, validate=True))
            audio_path.write_bytes(base64.b64decode(audio_data, validate=True))
            ffmpeg.output(
                ffmpeg.input(str(video_path)).video,
                ffmpeg.input(str(audio_path)).audio,
                str(output_path),
                vcodec="copy",
                acodec="aac",
                audio_bitrate="64k",
                movflags="+faststart",
            ).overwrite_output().run(quiet=True)
            merged = output_path.read_bytes()
            return base64.b64encode(merged).decode("ascii") if merged else None
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Video and audio could not be merged")
        return None


extract_video_audio_attachment = partial(
    convert_audio_attachment,
    fallback_to_original=False,
)
