"Tests for the config module."

from pathlib import Path

import pytest # type: ignore

from mvcs.config import Config, Prefs, Replace, Subcommand
from mvcs.error import Error

@pytest.mark.parametrize("prefs,expected", [
    # The default preferences are used when none is provided
    (None, Prefs()),
    # The default config respects user preferences when provided
    (
        Prefs(
            filename_replace=Replace.from_dict({" ": "_"}),
            job_path=Path("/dev/null"),
            output_dir=Path("/dev/null"),
            video_dir=Path("/dev/null"),
            video_ext="rm",
            video_filename_format="%s",
        ),
        Prefs(
            filename_replace=Replace.from_dict({" ": "_"}),
            job_path=Path("/dev/null"),
            output_dir=Path("/dev/null"),
            video_dir=Path("/dev/null"),
            video_ext="rm",
            video_filename_format="%s",
        ),
    ),
])
def test_config_from_argv_defaults(prefs, expected):
    "A default config is returned when no command-line arguments are given."
    config = Config.from_argv([], prefs=prefs)
    assert config.job_path == expected.job_path
    assert config.filename_replace == expected.filename_replace
    assert config.output_dir == expected.output_dir
    assert config.subcommand == Subcommand.HELP
    assert config.video_dir == expected.video_dir
    assert config.video_ext == expected.video_ext
    assert config.video_filename_format == expected.video_filename_format

@pytest.mark.parametrize("opt", ["-j", "--job-path"])
def test_config_from_argv_job_path(opt):
    "The default path to the job file can be changed."
    path = Path("/dev/null")
    config = Config.from_argv(["", opt, str(path)])
    assert config.job_path == path

@pytest.mark.parametrize("path", [""])
def test_config_from_argv_job_path_invalid(path):
    "Invalid paths are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", "--job-path", path])

@pytest.mark.parametrize("optargs,expected", [
    # Simple key=value arguments work
    ((" =_",), Replace.from_dict({" ": "_"})),
    (
        (" =...", "+=", "equals=="),
        Replace.from_dict({" ": "...", "+": "", "equals": "="}),
    ),
    # "=" can be replaced with ==value
    (("==equals",), Replace.from_dict({"=": "equals"})),
    # An empty argument clears the replacement map
    ((" =_", "+=", ""), Replace()),
])
def test_config_from_argv_filename_replace(optargs, expected):
    "The filename replacement mapping can be changed."
    for opt in ("-r", "--filename-replace"):
        argv = ["test"]
        for optarg in optargs:
            argv.extend([opt, optarg])
        config = Config.from_argv(argv)
        assert config.filename_replace == expected

@pytest.mark.parametrize("opt", ["-o", "--output-dir"])
def test_config_from_argv_output_dir(opt):
    "The default path to the output clips directory can be changed."
    path = Path("/dev/null")
    config = Config.from_argv(["", opt, str(path)])
    assert config.output_dir == path

@pytest.mark.parametrize("path", [""])
def test_config_from_argv_output_dir_invalid(path):
    "Invalid paths are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", "--output-dir", path])

@pytest.mark.parametrize("opt", ["--output-ext"])
def test_config_from_argv_output_ext(opt):
    "The default output clip file extension can be changed."
    ext = "rm"
    config = Config.from_argv(["", opt, ext])
    assert config.output_ext == ext

@pytest.mark.parametrize("ext", [""])
def test_config_from_argv_output_ext_invalid(ext):
    "Invalid file extensions are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", "--output-ext", ext])

@pytest.mark.parametrize("optarg", [
    # Left side cannot be empty
    "=",
    "=anything",
    # Mapping requires "="
    "not-a-mapping",
])
def test_config_from_argv_filename_replace_invalid(optarg):
    "Invalid filename replacement arguments are rejected."
    for opt in ("-r", "--filename-replace"):
        with pytest.raises(Error):
            Config.from_argv(["", opt, optarg])

@pytest.mark.parametrize("subcommand_str,expected", [
    ("clip", Subcommand.CLIP),
    ("help", Subcommand.HELP),
    ("run", Subcommand.RUN),
])
def test_config_from_argv_subcommand(subcommand_str, expected):
    "The subcommand is set from the first non-option argument."
    config = Config.from_argv(["", subcommand_str])
    assert config.subcommand == expected

@pytest.mark.parametrize("subcommand_str", [""])
def test_config_from_argv_subcommand_invalid(subcommand_str):
    "Invalid subcommands are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", subcommand_str])

@pytest.mark.parametrize("opt", ["-i", "--video-dir"])
def test_config_from_argv_video_dir(opt):
    "The default path to the input video directory can be changed."
    path = Path("/dev/null")
    config = Config.from_argv(["", opt, str(path)])
    assert config.video_dir == path

@pytest.mark.parametrize("path", [""])
def test_config_from_argv_video_dir_invalid(path):
    "Invalid paths are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", "--video-dir", path])

@pytest.mark.parametrize("opt", ["--video-ext"])
def test_config_from_argv_video_ext(opt):
    "The default input video file extension can be changed."
    ext = "rm"
    config = Config.from_argv(["", opt, ext])
    assert config.video_ext == ext

@pytest.mark.parametrize("ext", [""])
def test_config_from_argv_video_ext_invalid(ext):
    "Invalid file extensions are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", "--video-ext", ext])

@pytest.mark.parametrize("opt", ["--video-filename-format"])
def test_config_from_argv_video_filename_format(opt):
    "The default input video filename format can be changed."
    fmt = "%s"
    config = Config.from_argv(["", opt, fmt])
    assert config.video_filename_format == fmt

@pytest.mark.parametrize("fmt", [""])
def test_config_from_argv_video_filename_format_invalid(fmt):
    "Invalid filename formats are rejected."
    with pytest.raises(Error):
        Config.from_argv(["", "--video-filename-format", fmt])

@pytest.mark.parametrize("data,expected", [
    # Default preferences from an empty dict
    ({}, Prefs()),
    # Valid values override defaults
    (
        {
            "filename-replace": {" ": "_"},
            "job-path": "/dev/null",
            "output-dir": "/dev/null",
            "output-ext": "rm",
            "video-dir": "/dev/null",
            "video-ext": "rm",
            "video-filename-format": "%s",
        },
        Prefs(
            job_path=Path("/dev/null"),
            filename_replace=Replace.from_dict({" ": "_"}),
            output_dir=Path("/dev/null"),
            output_ext="rm",
            video_dir=Path("/dev/null"),
            video_ext="rm",
            video_filename_format="%s",
        ),
    ),
])
def test_prefs_from_dict(data, expected):
    "User preferences are deserialized from dicts correctly."
    prefs = Prefs.from_dict(data)
    assert prefs == expected

@pytest.mark.parametrize("data", [
    # Unknown preferences are invalid
    {"not-a-real-pref": "test"},
])
def test_prefs_from_dict_invalid(data):
    "Invalid user preferences are rejected."
    with pytest.raises(Error):
        Prefs.from_dict(data)
