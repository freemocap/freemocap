"""Which pixels receive the selected annotation layers."""

from enum import StrEnum


class AnnotationInput(StrEnum):
    RAW = "raw"
    ANNOTATED = "annotated"
