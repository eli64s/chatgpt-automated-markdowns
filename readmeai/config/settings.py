"""Data models and functions for configuring the readme-ai CLI tool."""

import os
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlsplit

import pkg_resources
from pydantic import BaseModel, validator

from readmeai.core import factory, logger

logger = logger.Logger(__name__)


class GitService(str, Enum):
    """
    Enum class for Git service details.
    """

    LOCAL = ("local", None, "{file_path}")
    GITHUB = (
        "github.com",
        "https://api.github.com/repos/",
        "https://github.com/{full_name}/blob/main/{file_path}",
    )
    GITLAB = (
        "gitlab.com",
        "https://api.gitlab.com/v4/projects/",
        "https://gitlab.com/{full_name}/-/blob/master/{file_path}",
    )
    BITBUCKET = (
        "bitbucket.org",
        "https://api.bitbucket.org/2.0/repositories/",
        "https://bitbucket.org/{full_name}/src/master/{file_path}",
    )

    def __new__(cls, host, api_url, file_url) -> object:
        """Create a new instance of the GitService enum."""
        obj = str.__new__(cls, host)
        obj._value_ = host
        obj.host = host
        obj.api_url = api_url
        obj.file_url = file_url
        return obj

    def get_clean_hostname(host: str) -> str:
        """Return the hostname without periods."""
        return host.split(".")[0]


class BadgeOptions(str, Enum):
    """
    Enum for CLI options for README file badge icons.
    """

    FLAT = "flat"
    FLAT_SQUARE = "flat-square"
    FOR_THE_BADGE = "for-the-badge"
    PLASTIC = "plastic"
    SKILLS = "skills"
    SKILLS_LIGHT = "skills-light"
    SOCIAL = "social"


class ImageOptions(str, Enum):
    """
    Enum for CLI options for README file header images.
    """

    CUSTOM = "CUSTOM"
    BLACK = "https://img.icons8.com/external-tal-revivo-regular-tal-revivo/96/external-readme-is-a-easy-to-build-a-developer-hub-that-adapts-to-the-user-logo-regular-tal-revivo.png"
    BLUE = "https://raw.githubusercontent.com/PKief/vscode-material-icon-theme/ec559a9f6bfd399b82bb44393651661b08aaf7ba/icons/folder-markdown-open.svg"
    GRADIENT = "https://img.icons8.com/nolan/96/markdown.png"
    PURPLE = "https://img.icons8.com/external-tal-revivo-duo-tal-revivo/100/external-markdown-a-lightweight-markup-language-with-plain-text-formatting-syntax-logo-duo-tal-revivo.png"
    YELLOW = "https://img.icons8.com/pulsar-color/96/markdown.png"


class CliSettings(BaseModel):
    """CLI options for the readme-ai application."""

    emojis: bool = True
    offline: bool = False


class FileSettings(BaseModel):
    """Pydantic model for configuration file paths."""

    dependency_files: str
    identifiers: str
    ignore_files: str
    language_names: str
    language_setup: str
    output: str
    shieldsio_icons: str
    skill_icons: str


class GitSettings(BaseModel):
    """Pydantic model for Git repository details."""

    repository: str
    source: Optional[str]
    name: Optional[str]

    @validator("repository", pre=True, always=True)
    def validate_repository(cls, value: str) -> str:
        """Validate the repository URL or path."""
        path = Path(value)
        if path.is_dir():
            return value
        try:
            parsed_url = urlparse(value)
        except ValueError:
            raise ValueError(f"Invalid repository URL or path: {value}")

        if parsed_url.scheme != "https" or not any(
            service.host in parsed_url.netloc for service in GitService
        ):
            raise ValueError(f"Invalid repository URL or path: {value}")

        return value

    @validator("source", pre=True, always=True)
    def set_source(cls, value: str, values: dict) -> str:
        """Sets the Git service source from the repository provided."""
        repo = values.get("repository")

        if Path(repo).is_dir():
            return GitService.LOCAL.host

        parsed_url = urlparse(repo)
        for service in GitService:
            if service.host in parsed_url.netloc:
                return service.host

        raise ValueError("Unsupported Git service.")

    @validator("name", pre=True, always=True)
    def set_name(cls, value: str, values: dict) -> str:
        """Sets the repository name from the repository provided."""
        repo = values.get("repository")
        parsed_url = urlsplit(repo)
        for service in GitService:
            if service.host in parsed_url.netloc:
                path = parsed_url.path
                name = path.rsplit("/", 1)[-1] if "/" in path else path
                if name.endswith(".git"):
                    name = name[:-4]
                return name

        return Path(repo).name


class LlmApiSettings(BaseModel):
    """Pydantic model for OpenAI LLM API details."""

    endpoint: str
    encoding: str
    model: str
    rate_limit: int
    temperature: float
    tokens: int
    tokens_max: int


class MarkdownSettings(BaseModel):
    """Pydantic model for Markdown code block templates."""

    align: str
    badges_offline: str
    badges_shieldsio: str
    badges_skills: str
    badges_style: str
    contribute: str
    default: str
    dropdown: str
    getting_started: str
    header: str
    header_left: str
    image: str
    modules: str
    overview: str
    tables: str
    toc: str
    tree: str


class PromptSettings(BaseModel):
    """Pydantic model for OpenAI prompts."""

    features: str
    overview: str
    slogan: str
    summaries: str


class AppConfig(BaseModel):
    """Nested Pydantic model for the entire configuration."""

    cli: CliSettings
    files: FileSettings
    git: GitSettings
    llm: LlmApiSettings
    md: MarkdownSettings
    prompts: PromptSettings


class AppConfigModel(BaseModel):
    """Pydantic model for the entire configuration."""

    app: AppConfig

    class Config:
        """Pydantic model configuration."""

        validate_assignment = True


class ConfigHelper(BaseModel):
    """Helper class to load additional configuration files."""

    conf: AppConfigModel
    dependency_files: List[str] = []
    ignore_files: Dict[str, List[str]] = {}
    language_names: Dict[str, str] = {}
    language_setup: Dict[str, List[str]] = {}

    class Config:
        allow_mutation = True

    def __init__(self, conf: AppConfigModel, **data):
        super().__init__(conf=conf, **data)
        self.load_helper_files()

    def load_helper_files(self):
        """Load helper configuration files."""
        handler = factory.FileHandler()
        conf_path_list = [
            self.conf.app.files.dependency_files,
            self.conf.app.files.ignore_files,
            self.conf.app.files.language_names,
            self.conf.app.files.language_setup,
        ]

        for path in conf_path_list:
            conf_dict = _get_config_dict(handler, path)

            if "dependency_files" in conf_dict:
                self.dependency_files.extend(
                    conf_dict.get("dependency_files", [])
                )
            if "ignore_files" in conf_dict:
                self.ignore_files.update(conf_dict["ignore_files"])
            if "language_names" in conf_dict:
                self.language_names.update(conf_dict["language_names"])
            if "language_setup" in conf_dict:
                self.language_setup.update(conf_dict["language_setup"])


def _get_config_dict(handler: factory.FileHandler, file_path: str) -> dict:
    """Get configuration dictionary from TOML file."""
    try:
        resource_path = resources.files("readmeai.settings") / file_path
        logger.info(f"Resource path using importlib: {resource_path}")
    except TypeError as exc_info:
        logger.debug(f"Error with importlib.resources: {exc_info}")
        try:
            resource_path = Path(
                pkg_resources.resource_filename(
                    "readmeai", f"settings/{file_path}"
                )
            ).resolve()
            logger.info(f"Resource path using pkg_resources: {resource_path}")
        except FileNotFoundError as exc_info:
            logger.debug(f"Error with pkg_resources: {exc_info}")
            raise

    if not os.path.exists(resource_path):
        raise FileNotFoundError(f"Config file not found: {resource_path}")

    return handler.read(resource_path)


def load_config(path: str = "config.toml") -> AppConfig:
    """Load configuration constants from TOML file."""
    handler = factory.FileHandler()
    conf_dict = _get_config_dict(handler, path)
    return AppConfigModel.parse_obj({"app": conf_dict}).app


def load_config_helper(conf: AppConfigModel) -> ConfigHelper:
    """Load multiple configuration helper TOML files."""
    return ConfigHelper(conf=conf)
