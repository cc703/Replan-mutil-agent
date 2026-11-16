"""Load strictly validated scenario YAML."""

from pathlib import Path
import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from .scenarios import Scenario


def _check(node: Node) -> None:
    allowed = {
        "tag:yaml.org,2002:" + x for x in ("map", "seq", "str", "int", "float", "bool", "null")
    }
    if node.tag not in allowed:
        raise ValueError("custom YAML tag")
    if isinstance(node, MappingNode):
        keys: set[str] = set()
        for key, value in node.value:
            if (
                not isinstance(key, ScalarNode)
                or key.tag != "tag:yaml.org,2002:str"
                or key.value in keys
            ):
                raise ValueError("invalid or duplicate key")
            keys.add(key.value)
            _check(value)
    elif isinstance(node, SequenceNode):
        for child in node.value:
            _check(child)
    elif (
        isinstance(node, ScalarNode)
        and node.tag.endswith(":bool")
        and node.value not in ("true", "false")
    ):
        raise ValueError("booleans must be true or false")


def load_scenario(source: bytes | str | Path) -> Scenario:
    """Load UTF-8 YAML bytes, text, or a file path; reject ambiguous YAML."""
    data = (
        source.read_bytes()
        if isinstance(source, Path)
        else source.encode()
        if isinstance(source, str)
        else source
    )
    if len(data) > 65536 or data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("invalid size or BOM")
    try:
        text = data.decode("utf-8")
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
                raise ValueError("anchors and aliases forbidden")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if not isinstance(node, MappingNode):
            raise ValueError("root must be a mapping")
        _check(node)
        values = yaml.safe_load(text)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("invalid YAML") from exc
    if not isinstance(values, dict):
        raise ValueError("root must be a mapping")
    if isinstance(values.get("urgent_task_range"), list):
        values["urgent_task_range"] = tuple(values["urgent_task_range"])
    return Scenario.model_validate(values)
