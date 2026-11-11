"""Strict YAML loader for explicit generation parameters."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from scheduler_core.generation.params import GeneratorParams


@dataclass(frozen=True)
class LoadedGeneratorConfig:
    """Validated params, SHA-256 of original YAML bytes, and config version.

    The byte hash identifies the source, not its semantic parameter hash and
    not an authenticated origin. The returned record is frozen.
    """

    params: GeneratorParams
    sha256: str
    config_version: str


def _check_node(node: Node) -> None:
    allowed = {
        "tag:yaml.org,2002:" + suffix
        for suffix in ("map", "seq", "str", "int", "float", "bool", "null")
    }
    if node.tag not in allowed:
        raise ValueError("custom YAML tag")
    if isinstance(node, MappingNode):
        seen: set[str] = set()
        for key, value in node.value:
            if not isinstance(key, ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                raise ValueError("mapping keys must be strings")
            if key.value in seen:
                raise ValueError("duplicate YAML key")
            seen.add(key.value)
            _check_node(value)
    elif isinstance(node, SequenceNode):
        for child in node.value:
            _check_node(child)


def load_generator_config(source: bytes | str | Path) -> LoadedGeneratorConfig:
    """Load explicit generation parameters and return their source-byte hash.

    Bytes are YAML data, str is YAML text, and Path is read as bytes. The input
    must be UTF-8 without BOM and at most 64 KiB; no input is modified or written.
    Requires schema version 1, config version c2-1, and every parameter field.
    Duplicate keys, aliases, anchors, custom tags, multiple documents, invalid
    values or structure raise ValueError (including Pydantic validation errors).
    File-read failures propagate as OSError. Generated instance times use
    integer slots, defaulting to five minutes, not timestamps in this config.
    """
    data = (
        source.read_bytes()
        if isinstance(source, Path)
        else source.encode("utf-8")
        if isinstance(source, str)
        else source
    )
    if len(data) > 65536 or data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("invalid configuration size or BOM")
    try:
        text = data.decode("utf-8")
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
                raise ValueError("anchors and aliases are forbidden")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if not isinstance(node, MappingNode):
            raise ValueError("configuration root must be a mapping")
        _check_node(node)
        parsed: object = yaml.safe_load(text)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("invalid YAML") from exc
    if not isinstance(parsed, dict):
        raise ValueError("configuration root must be a mapping")
    if (
        set(parsed) != {"schema_version", "config_version", "params"}
        or type(parsed["schema_version"]) is not int
        or parsed["schema_version"] != 1
        or parsed["config_version"] != "c2-1"
    ):
        raise ValueError("invalid configuration header")
    values = parsed["params"]
    if not isinstance(values, dict) or set(values) != set(GeneratorParams.model_fields):
        raise ValueError("parameter keys do not match schema")
    params = GeneratorParams.model_validate(values)
    return LoadedGeneratorConfig(params, hashlib.sha256(data).hexdigest(), parsed["config_version"])
