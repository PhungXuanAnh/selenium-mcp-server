"""Typed input models shared by the experimental compact tool profile."""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class XPathSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["xpath"]
    value: str
    frame: Optional[str] = None


class CssSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["css"]
    value: str
    frame: Optional[str] = None


class FieldsSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["fields"]
    value: dict[str, str]
    frame: Optional[str] = None


class RefSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["ref"]
    value: str


Selector = Annotated[
    Union[XPathSelector, CssSelector, FieldsSelector, RefSelector],
    Field(discriminator="type"),
]
