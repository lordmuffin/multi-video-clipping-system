"Job execution module."

import datetime
import subprocess
from itertools import chain
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Type, TypeVar

import yaml

from mvcs.config import Config
from mvcs.error import Error
from mvcs.time import datetime_from_str, timedelta_from_str, timedelta_to_path_str

ClipType = TypeVar("ClipType", bound="Clip")
class Clip(NamedTuple):
    "Data about a single video clip that should be created."

    # Source video timestamp for the end of the clip.
    end: datetime.timedelta
    # Source video timestamp for the start of the clip.
    start: datetime.timedelta
    # Clip title.
    title: str

    @classmethod
    def from_dict(cls: Type[ClipType], data: Dict[str, Any]) -> ClipType:
        "Create a `Clip` from an untyped `dict` (YAML deserialization result)."

        try:
            clip: Dict[str, Any] = {
                "title": str(data["title"]),
            }
            time = [timedelta_from_str(t.strip()) for t in str(data["time"]).split("-", maxsplit=1)]
            (clip["start"], clip["end"]) = time
        except (KeyError, ValueError) as ex:
            raise Error(f"bad clip data: {ex}: {data}")

        if clip["end"] <= clip["start"]:
            raise Error(f"bad clip start/end: {data}")

        if not clip["title"]:
            raise Error(f"bad clip title: {data}")

        return cls(**clip) # type: ignore

    def path_str(
            self,
            config: Config,
            date: datetime.datetime,
            epoch: datetime.timedelta,
            title: str,
    ) -> str:
        "Get the file name for a clip."

        path_str = " - ".join((
            (date + epoch).strftime("%Y-%m-%d %H:%M:%S"),
            f"T+{timedelta_to_path_str(self.start - epoch)}",
            title,
            f"{self.title}",
        )).casefold()

        for (old, new) in chain(
                ((bad, "-") for bad in "\"*/:?\\|<>"),
                config.filename_replace.items(),
        ):
            path_str = path_str.replace(old, new)

        return ".".join((path_str, config.output_ext))

    def write(self, src: Path, dst: Path):
        "Use ffmpeg to write the lossless video clip file."

        if dst.exists():
            print(f"skipping existing clip: {dst}")
            return

        cmd = (
            "ffmpeg",
            "-ss", str(self.start.total_seconds()),
            "-i", str(src),
            "-c:a", "copy",
            "-c:v", "copy",
            "-map", "0:v",
            "-map", "0:a",
            "-t", str((self.end - self.start).total_seconds()),
            str(dst),
        )
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as ex:
            raise Error(ex)

VideoType = TypeVar("VideoType", bound="Video")
class Video(NamedTuple):
    "Data about an OBS capture video and clips to create from it."

    # Video timestamp (recording start time)
    date: datetime.datetime
    # Base title used for all clips from this video.
    title: str
    # List of clips to create from the video.
    clips: List[Clip] = []
    # Virtual "start" time in the source video (for output filename)
    epoch: datetime.timedelta = datetime.timedelta()

    @classmethod
    def from_dict(cls: Type[VideoType], data: Dict[str, Any]) -> VideoType:
        "Create a `Video` from an untyped `dict` (YAML deserialization result)."

        try:
            video: Dict[str, Any] = {
                "date": datetime_from_str(str(data["date"])),
                "title": str(data["title"])
            }
        except KeyError as ex:
            raise Error(f"bad video data: {ex}: {data}")

        for (key, validate_fn, value_fn) in (
                (
                    "clips",
                    lambda xs: isinstance(xs, list) \
                            and not [x for x in xs if not isinstance(x, dict)],
                    lambda xs: [Clip.from_dict(x) for x in xs],
                ),
                (
                    "epoch",
                    lambda x: True,
                    lambda x: timedelta_from_str(str(x)),
                ),
        ):
            if key in data:
                value = data[key]
                if not validate_fn(value):
                    raise Error(f"bad video data: {key}: {value}")
                video[key] = value_fn(value)

        return cls(**video) # type: ignore

    @classmethod
    def from_path(cls: Type[VideoType], config: Config, path: Path) -> VideoType:
        "Create a default `Video` from a filesystem path."

        if path.suffix != f".{config.video_ext}":
            raise Error(f"{path} has invalid file extension")

        fmt = config.filename_replace.apply(config.video_filename_format)
        try:
            date = datetime.datetime.strptime(path.stem, fmt)
        except ValueError:
            raise Error(f"{path} does not match format {fmt}")
        return cls(date=date, title="video")

    def write_clips(self, config: Config, src_dir: Path, dst_dir: Path):
        "Create all requested clips from the video."

        src_name = config.filename_replace.apply(self.date.strftime(config.video_filename_format))
        src = (src_dir / src_name).with_suffix(f".{config.video_ext}")
        if not src.is_file():
            raise Error(f"missing video file: {src}")

        for clip in self.clips:
            dst = dst_dir / clip.path_str(
                config,
                self.date,
                self.epoch,
                self.title,
            )
            clip.write(src, dst)

JobType = TypeVar("JobType", bound="Job")
class Job(NamedTuple):
    "Data about the full set of videos and clips to produce from them."

    # Directory where the clips should be written to.
    output_dir: Path
    # Directory where the source videos can be found.
    video_dir: Path
    # List of videos to create clips from.
    videos: List[Video] = []

    @classmethod
    def from_dict(cls: Type[JobType], config: Config, data: Dict[str, Any]) -> JobType:
        "Create a `Job` from an untyped `dict` (YAML deserialization result)."

        videos = data.get("videos", [])
        if not isinstance(videos, list):
            raise Error(f"invalid videos: {videos}")

        for video in videos:
            if not isinstance(video, dict):
                raise Error(f"invalid video entry: {video}")

        output_dir = Path(str(data.get("output-dir", config.output_dir)))
        video_dir = Path(str(data.get("video-dir", config.video_dir)))

        return cls(
            output_dir=output_dir,
            video_dir=video_dir,
            videos=[Video.from_dict(video) for video in videos],
        )

    @classmethod
    def from_yaml_file(cls: Type[JobType], config: Config) -> JobType:
        "Create a `Job` from a YAML file."

        with config.job_path.open(encoding="utf-8") as file:
            return cls.from_dict(config, yaml.safe_load(file))

    def run(self, config: Config):
        "Run the batch job and create all requested clips."

        for video in self.videos:
            video.write_clips(config, self.video_dir, self.output_dir)
