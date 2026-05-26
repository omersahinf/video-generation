from dataclasses import dataclass, field


@dataclass
class BackgroundConfig:
    color: str = "#FFFFFF"
    texture: str = "none"  # "none" | "chalk" | "paper" | "dark_paper"


@dataclass
class StyleConfig:
    name: str
    category: str  # "canvas" | "sketch"
    background: BackgroundConfig
    palette: list[str]
    title_font_size: int
    body_font_size: int
    text_color: str
    accent_color: str
    drawing_effect: str  # "pen" | "chalk" | "marker" | "crayon" | "none"
    reveal_speed: float  # 0.3–1.0 (fraction of scene revealed per second)
    transition: str  # "fade" | "wipe_left" | "wipe_right"
    image_prompt_suffix: str  # appended to AI image generation prompt
    font_style: str = "sans"  # "sans" | "chalk" | "marker" | "mono"
