"""Semantic regressions for static API extraction and Markdown conversion."""

import json
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

from generate_api import (
    DOCS,
    create_environment,
    load_package,
    public_members,
    render_object,
)


class ApiGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "sample.py").write_text(
            '''"""A module with `Widget` and `{origin}/mcp`."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from dataclasses import dataclass
from enum import Enum

__all__ = ["Widget", "Model", "Choice", "Base"]
Choice = Literal["a", "b"]
"""Available choices."""

class Base:
    def inherited(self):
        """An inherited operation."""

class Widget(Base):
    """A widget.

    Attributes:
        label: Visible label stored on the widget.
        timeout: Maximum wait in seconds for this widget.
    """
    label: str
    """Visible label stored on the widget."""
    def __init__(self, name: str, /, *, count: int = 2):
        """Construct a widget.

        Args:
            name: Visible name.
            count: Number of widgets.
        """
        self.name: str = str(name)
        self.hidden = 1
        self.timeout: float = 5.0
        self.note: str = name
        """An ordinary instance field with its own documentation."""

    @property
    def value(self) -> str:
        """The current value."""
        return self.name

    async def run(self, item: str, /, *values: int, flag: bool = False, **options: str) -> str:
        """Run once.

        Args:
            item: Input.
            values: Values.
            flag: A flag.
            options: Options.

        Returns:
            Output.

        Raises:
            ValueError: Invalid input.

        Examples:
            Preserve literal code:

            ```python
            payload = {"path": "{origin}/mcp"}
            ```
        """

    def mixed(self, typed: int, untyped=None):
        """Accept mixed annotations."""

    def long(self, first: list[dict[str, list[int]]], second: dict[str, list[int]], *, count: int = 2) -> list[int]:
        """Accept nested annotated values."""

    def positional(self, value: int, /):
        """Accept only positional input."""

class Model(BaseModel):
    """Input data."""
    name: str = Field(min_length=1, description="Visible name.")
    values: list[str] = Field(default_factory=list)
    enabled: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return value

@dataclass
class Record:
    """A record."""
    name: str
    count: int = 2

class Color(Enum):
    RED = "red"

class Settings(BaseSettings):
    port: int = Field(default=8000, ge=1)

    @field_validator("port")
    @classmethod
    def validate_port(cls, value):
        return value

raise RuntimeError("Documentation must never execute this module")
''',
            encoding="utf-8",
        )
        cls.module = load_package(root, "sample").modules_collection["sample"]
        cls.env = create_environment()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_constructor_and_call_shapes(self):
        widget = self.module["Widget"]
        text = render_object(self.env, widget)
        self.assertIn("name: str, /, *, count: int = 2", text)
        self.assertIn("Number of widgets", text)
        self.assertNotIn("inherited()", text)
        text = render_object(self.env, widget["run"])
        self.assertIn("*values: int, flag: bool = False, **options: str", text)
        heading = re.search(r"^### `run`\s*$", text, re.M)
        self.assertIsNotNone(heading)
        self.assertNotIn("`run` `async`", text)
        after = text[heading.end() :]
        meta = re.search(r'<p className="ac-symbol-meta">async</p>', after)
        self.assertIsNotNone(meta)
        self.assertIsNone(re.search(r"^#+", after[: meta.start()], re.M))
        self.assertIsNone(re.search(r"^#+\s+`?async`?", text, re.M))
        self.assertIn("```python", text)
        self.assertNotIn("SdkSignature", text)
        for section in ("Parameters", "Returns", "Raises", "Examples"):
            self.assertIn(section, text)
        self.assertIn(
            "typed: int, untyped=None", render_object(self.env, widget["mixed"])
        )
        self.assertIn("value: int, /)", render_object(self.env, widget["positional"]))
        long = render_object(self.env, widget["long"])
        self.assertIn("long(\n", long)
        self.assertIn("    first: list[dict[str, list[int]]],\n", long)
        self.assertIn("    *,\n", long)
        self.assertIn(") -> list[int]", long)

    def test_properties_aliases_and_instance_attributes(self):
        self.assertEqual(
            {obj.name for obj in public_members(self.module)},
            {"Widget", "Model", "Choice", "Base"},
        )
        widget = self.module["Widget"]
        names = [obj.name for obj in public_members(widget)]
        self.assertIn("value", names)
        self.assertIn("label", names)
        self.assertIn("timeout", names)
        self.assertIn("note", names)
        self.assertNotIn("name", names)
        self.assertNotIn("hidden", names)
        timeout = render_object(self.env, widget["timeout"])
        self.assertIn("Maximum wait in seconds", timeout)
        self.assertIn("timeout: float", timeout)
        self.assertNotIn("= 5.0", timeout)
        self.assertIn(
            "An ordinary instance field", render_object(self.env, widget["note"])
        )
        self.assertNotIn(
            "Visible label stored on the widget.", render_object(self.env, widget)
        )
        self.assertIn(
            "Visible label stored on the widget.",
            render_object(self.env, widget["label"]),
        )
        text = render_object(self.env, widget["value"])
        self.assertIn("value: str", text)
        self.assertNotIn("value(", text)
        heading = re.search(r"^### `value`\s*$", text, re.M)
        self.assertIsNotNone(heading)
        self.assertNotIn("`value` `property`", text)
        after = text[heading.end() :]
        meta = re.search(r'<p className="ac-symbol-meta">property</p>', after)
        self.assertIsNotNone(meta)
        self.assertIsNone(re.search(r"^#+", after[: meta.start()], re.M))
        self.assertIsNone(re.search(r"^#+\s+`?property`?", text, re.M))
        self.assertNotIn("str(name)", render_object(self.env, widget["name"]))
        self.assertIn(
            "Literal['a', 'b']", render_object(self.env, self.module["Choice"])
        )

    def test_model_fields_and_validators(self):
        model = self.module["Model"]
        self.assertIn("name", [obj.name for obj in public_members(model)])
        self.assertNotIn("validate_name", [obj.name for obj in public_members(model)])
        text = render_object(self.env, model["name"])
        self.assertNotIn("Required.", text)
        self.assertIn("name: str", text)
        self.assertIn("Visible name.", text)
        self.assertIn("`min_length`: `1`", text)
        values = render_object(self.env, model["values"])
        self.assertIn("= []", values)
        self.assertNotIn("Default factory", values)
        self.assertNotIn("**Types:**", values)
        enabled = render_object(self.env, model["enabled"])
        self.assertIn("= False", enabled)
        self.assertNotIn("Default:", enabled)

    def test_dataclass_enum_and_settings(self):
        self.assertIn(
            "Record(name: str, count: int = 2)",
            render_object(self.env, self.module["Record"]),
        )
        members = list(public_members(self.module["Color"]))
        self.assertEqual([obj.name for obj in members], ["RED"])
        self.assertIn("'red'", render_object(self.env, members[0]))
        settings = self.module["Settings"]
        self.assertNotIn(
            "validate_port", [obj.name for obj in public_members(settings)]
        )
        text = render_object(self.env, settings["port"])
        self.assertIn("port: int = 8000", text)
        self.assertNotIn("Default:", text)
        self.assertIn("`ge`: `1`", text)

    def test_markdown_preserves_code_and_resolves_references(self):
        body = render_object(self.env, self.module["Widget"]["run"])
        body += (
            "\nLiteral {braces}. `{origin}/mcp` and `Widget`.\n\n"
            "See [`Widget`][sample.Widget].\n"
            "\n~~~python\n[Thing][agentconnect.missing.Thing]\n~~~\n"
            "\n``[Thing][agentconnect.missing.Thing]``\n"
        )
        process = subprocess.run(
            ["node", str(DOCS / "scripts/markdown.mjs")],
            input=json.dumps(
                {
                    "page": {
                        "body": body,
                        "refs": {
                            "sample.Widget": "/widget#widget",
                            "other.Widget": "/other#widget",
                        },
                    }
                }
            ),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        text = json.loads(process.stdout)["page"]
        self.assertIn('payload = {"path": "{origin}/mcp"}', text)
        self.assertIn('className="ac-symbol-meta"', text)
        self.assertIn("`{origin}/mcp`", text)
        self.assertIn("`Widget`", text)
        self.assertEqual(text.count("[`Widget`](/widget#widget)"), 1)
        self.assertIn(r"\{braces\}", text)
        self.assertIn("[`Widget`](/widget#widget)", text)
        failed = subprocess.run(
            ["node", str(DOCS / "scripts/markdown.mjs")],
            input=json.dumps(
                {
                    "page": {
                        "body": "See [`Thing`][agentconnect.missing.Thing].\n",
                        "refs": {},
                    }
                }
            ),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Unresolved reference", failed.stderr)


if __name__ == "__main__":
    unittest.main()
