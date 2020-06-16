"Job execution module."

import datetime
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Type, TypeVar

import yaml

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
            time = str(data["time"])
            title = str(data["title"])
            time_parts = [timedelta_from_str(t.strip()) for t in time.split("-", maxsplit=1)]
            (start, end) = time_parts
        except (KeyError, ValueError) as ex:
            raise Error(f"bad clip data: {ex}: {data}")

        if end <= start:
            raise Error(f"bad clip start/end: {data}")

        if not title:
            raise Error(f"bad clip title: {data}")

        return cls(end=end, start=start, title=title)

    def path_str(self, date: datetime.datetime, epoch: datetime.timedelta, title: str) -> str:
        "Get the file name for a clip."

        date_str = (date + epoch).strftime("%Y-%m-%d %H:%M:%S")
        start_str = timedelta_to_path_str(self.start - epoch)
        path_str = f"{date_str} - T+{start_str} - {title} - {self.title}.mkv"
        return re.sub(r"[/\:]", "-", path_str.casefold())

    def write(self, src: Path, dst: Path):
        "Use ffmpeg to write the lossless video clip file."

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

    # List of clips to create from the video.
    clips: List[Clip]
    # Video timestamp (recording start time)
    date: datetime.datetime
    # Virtual "start" time in the source video (for output filename)
    epoch: datetime.timedelta
    # Base title used for all clips from this video.
    title: str

    @classmethod
    def from_dict(cls: Type[VideoType], data: Dict[str, Any]) -> VideoType:
        "Create a `Video` from an untyped `dict` (YAML deserialization result)."

        clips = data.get("clips", [])
        if not isinstance(clips, list):
            raise Error(f"invalid clips: {clips}")

        for clip in clips:
            if not isinstance(clip, dict):
                raise Error(f"invalid clips entry: {clip}")

        try:
            date = datetime_from_str(str(data["date"]))
            title = str(data["title"])
        except KeyError as ex:
            raise Error(f"bad video data: {ex}: {data}")

        return cls(
            clips=[Clip.from_dict(clip) for clip in clips],
            date=date,
            epoch=timedelta_from_str(str(data.get("epoch", 0))),
            title=title,
        )

    def write_clips(self, src_dir: Path, dst_dir: Path):
        "Create all requested clips from the video."

        src = src_dir / self.date.strftime("%Y-%m-%d %H-%M-%S.mkv")
        if not src.is_file():
            raise Error(f"missing video file: {src}")

        for clip in self.clips:
            dst = dst_dir / clip.path_str(self.date, self.epoch, self.title)
            clip.write(src, dst)

JobType = TypeVar("JobType", bound="Job")
class Job(NamedTuple):
    "Data about the full set of videos and clips to produce from them."

    # Directory where the clips should be written to.
    output_dir: Path
    # Directory where the source videos can be found.
    video_dir: Path
    # List of videos to create clips from.
    videos: List[Video]

    @classmethod
    def from_dict(cls: Type[JobType], data: Dict[str, Any]) -> JobType:
        "Create a `Job` from an untyped `dict` (YAML deserialization result)."

        videos = data.get("videos", [])
        if not isinstance(videos, list):
            raise Error(f"invalid videos: {videos}")

        for video in videos:
            if not isinstance(video, dict):
                raise Error(f"invalid video entry: {video}")

        return cls(
            output_dir=Path(str(data.get("output-dir", "."))),
            video_dir=Path(str(data.get("video-dir", "."))),
            videos=[Video.from_dict(video) for video in videos],
        )

    @classmethod
    def from_yaml_file(cls: Type[JobType], path: Path) -> JobType:
        "Create a `Job` from a YAML file."

        with path.open(encoding="utf-8") as file:
            return cls.from_dict(yaml.safe_load(file))

    def run(self):
        "Run the batch job and create all requested clips."

        for video in self.videos:
            video.write_clips(self.video_dir, self.output_dir)