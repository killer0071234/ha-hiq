from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocationsConfig:
    @classmethod
    def create(cls, app_dir_str, log_dir_str, alc_dir_str, data_logger_config_file_str):
        app_dir = cls._to_path(app_dir_str, Path.cwd())
        log_dir = cls._to_path(log_dir_str, app_dir)
        alc_dir = cls._to_path(alc_dir_str, app_dir)
        data_logger_config_file = cls._to_path(data_logger_config_file_str, app_dir)

        return cls(app_dir, log_dir, alc_dir, data_logger_config_file)

    app_dir: Path
    log_dir: Path
    alc_dir: Path
    data_logger_config_file: Path

    def props(self):
        return (
            self.app_dir.as_posix(),
            self.log_dir.as_posix(),
            self.alc_dir.as_posix(),
            self.data_logger_config_file.as_posix(),
        )

    @classmethod
    def load(cls, cp, default):
        section = "LOCATIONS"

        (
            app_dir,
            log_dir,
            alc_dir,
            data_logger_config_file,
        ) = default.props()

        return cls.create(
            app_dir,
            cp.get(section, "log_dir", fallback=log_dir),
            cp.get(section, "alc_dir", fallback=alc_dir),
            data_logger_config_file,
        )

    @classmethod
    def _to_path(cls, path_str, base):
        result = Path(path_str)
        return result if result.is_absolute() else base.joinpath(result).resolve()
