from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

class StyleToken(BaseModel):
    font_size: Optional[float] = None
    color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    strikethrough: Optional[bool] = None
    align: Optional[str] = None
    font_name: Optional[str] = None

class DocumentStyleProfile(BaseModel):
    page_width: float = 1280.0
    page_height: float = 720.0
    title_left_ratio: float = 0.05
    title_top_ratio: float = 0.08
    content_left_ratio: float = 0.05
    content_top_ratio: float = 0.18
    content_right_ratio: float = 0.95
    content_bottom_ratio: float = 0.92
    primary_color: str = "#203040"
    secondary_color: str = "#787878"
    accent_color: str = "#0F3A78"
    title_style: StyleToken = Field(default_factory=lambda: StyleToken(font_size=24.0, color="#203040", bold=True, align="left"))
    subtitle_style: StyleToken = Field(default_factory=lambda: StyleToken(font_size=18.0, color="#787878", bold=False, align="left"))
    body_style: StyleToken = Field(default_factory=lambda: StyleToken(font_size=16.0, color="#203040", bold=False, align="left"))
    caption_style: StyleToken = Field(default_factory=lambda: StyleToken(font_size=12.0, color="#787878", bold=False, align="left"))

class Element(BaseModel):
    type: str # text, image, table, formula
    content: str
    bbox: Optional[List[float]] = None
    page_id: int = 0  # 0-based page index from PDF

class TextElement(Element):
    type: str = "text"
    font_size: Optional[float] = None
    color: Optional[str] = None
    text_level: Optional[int] = None
    semantic_role: Optional[str] = None
    align: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    strikethrough: Optional[bool] = None
    font_name: Optional[str] = None
    bbox_fs: Optional[List[float]] = None
    line_texts: Optional[List[str]] = None
    line_bboxes: Optional[List[List[float]]] = None
    line_font_sizes: Optional[List[float]] = None

class ImageElement(Element):
    type: str = "image"
    path: str # local path to image file

class TableElement(Element):
    type: str = "table"
    html: str # extracted HTML representation

class Slide(BaseModel):
    page_id: int
    elements: List[Union[TextElement, ImageElement, TableElement, Element]] = Field(default_factory=list)
    width: float = 1280.0
    height: float = 720.0
    archetype: str = "single_visual_explainer"
    style_profile: Optional[DocumentStyleProfile] = None
    render_mode: Optional[str] = None
    
    def add_element(self, element: Element):
        self.elements.append(element)

class Presentation(BaseModel):
    slides: List[Slide] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    style_profile: Optional[DocumentStyleProfile] = None
