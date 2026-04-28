from pathlib import Path
import json
from app.services.parser_service import parse_mineru_output

def test_parser_reads_sample_output_folder(tmp_path):
    artifact_dir = tmp_path / "TheLastLeaf" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "TheLastLeaf_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "title",
                                "bbox": [100.0, 80.0, 600.0, 160.0],
                                "lines": [
                                    {
                                        "bbox": [100.0, 80.0, 600.0, 160.0],
                                        "spans": [{"content": "Sample Title"}],
                                    }
                                ],
                            },
                            {
                                "type": "text",
                                "bbox": [100.0, 200.0, 600.0, 300.0],
                                "lines": [
                                    {
                                        "bbox": [100.0, 200.0, 600.0, 250.0],
                                        "spans": [{"content": "Sample body text line 1"}],
                                    },
                                    {
                                        "bbox": [100.0, 250.0, 600.0, 300.0],
                                        "spans": [{"content": "Sample body text line 2"}],
                                    },
                                ],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "TheLastLeaf"))

    assert presentation.slides
    assert any(element.type == "text" for slide in presentation.slides for element in slide.elements)


def test_parser_extracts_span_style_metadata(tmp_path):
    artifact_dir = tmp_path / "StyledDoc" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "StyledDoc_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "title",
                                "bbox": [100.0, 80.0, 600.0, 160.0],
                                "lines": [
                                    {
                                        "bbox": [100.0, 80.0, 600.0, 160.0],
                                        "spans": [
                                            {
                                                "content": "Styled Title",
                                                "font_name": "Aptos",
                                                "color": "#112233",
                                                "bold": True,
                                                "italic": True,
                                                "underline": True,
                                                "strikethrough": True,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "StyledDoc"))

    assert presentation.style_profile is not None
    assert presentation.style_profile.title_style.font_name == "Aptos"
    title = next(element for slide in presentation.slides for element in slide.elements if element.type == "text")
    assert title.font_name == "Aptos"
    assert title.color == "#112233"
    assert title.bold is True
    assert title.italic is True
    assert title.underline is True
    assert title.strikethrough is True


def test_parser_prefers_bbox_fs_and_keeps_line_geometry(tmp_path):
    artifact_dir = tmp_path / "PreciseDoc" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "PreciseDoc_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "text",
                                "bbox": [80.0, 100.0, 620.0, 210.0],
                                "bbox_fs": [92.0, 108.0, 604.0, 202.0],
                                "lines": [
                                    {
                                        "bbox": [92.0, 108.0, 604.0, 150.0],
                                        "spans": [{"content": "Precise line 1"}],
                                    },
                                    {
                                        "bbox": [92.0, 160.0, 560.0, 202.0],
                                        "spans": [{"content": "Precise line 2"}],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "PreciseDoc"))

    text = next(element for slide in presentation.slides for element in slide.elements if element.type == "text")
    assert text.bbox == [92.0, 108.0, 604.0, 202.0]
    assert text.bbox_fs == [92.0, 108.0, 604.0, 202.0]
    assert text.line_texts == ["Precise line 1", "Precise line 2"]
    assert text.line_bboxes == [[92.0, 108.0, 604.0, 150.0], [92.0, 160.0, 560.0, 202.0]]


def test_parser_prefers_explicit_span_font_size_when_available(tmp_path):
    artifact_dir = tmp_path / "ExplicitFontDoc" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "ExplicitFontDoc_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "title",
                                "bbox": [100.0, 80.0, 620.0, 180.0],
                                "lines": [
                                    {
                                        "bbox": [100.0, 80.0, 620.0, 180.0],
                                        "spans": [
                                            {
                                                "content": "Explicit Size Title",
                                                "font_size": 27.5,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "ExplicitFontDoc"))

    title = next(element for slide in presentation.slides for element in slide.elements if element.type == "text")
    assert title.font_size == 27.5


def test_parser_uses_role_aware_conservative_font_sizes_for_dense_body_text(tmp_path):
    artifact_dir = tmp_path / "DenseBodyDoc" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "DenseBodyDoc_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "title",
                                "bbox": [80.0, 70.0, 900.0, 150.0],
                                "lines": [
                                    {
                                        "bbox": [80.0, 70.0, 900.0, 150.0],
                                        "spans": [{"content": "Readable Title"}],
                                    }
                                ],
                            },
                            {
                                "type": "text",
                                "bbox": [80.0, 190.0, 1180.0, 320.0],
                                "lines": [
                                    {
                                        "bbox": [80.0, 190.0, 1180.0, 240.0],
                                        "spans": [{"content": "This is a very long body line that should stay conservative"}],
                                    },
                                    {
                                        "bbox": [80.0, 245.0, 1160.0, 295.0],
                                        "spans": [{"content": "and not explode into oversized PPT text"}],
                                    },
                                ],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "DenseBodyDoc"))

    title = next(element for slide in presentation.slides for element in slide.elements if element.type == "text" and getattr(element, "semantic_role", None) == "title")
    body = next(element for slide in presentation.slides for element in slide.elements if element.type == "text" and getattr(element, "semantic_role", None) == "body")

    assert title.font_size is not None
    assert body.font_size is not None
    assert title.font_size > body.font_size
    assert 10.0 <= body.font_size <= 20.0


def test_parser_keeps_two_column_year_label_conservative(tmp_path):
    artifact_dir = tmp_path / "CompareDoc" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "CompareDoc_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "image",
                                "bbox": [80.0, 100.0, 480.0, 520.0],
                                "blocks": [],
                                "lines": [],
                            },
                            {
                                "type": "image",
                                "bbox": [700.0, 100.0, 1180.0, 520.0],
                                "blocks": [],
                                "lines": [],
                            },
                            {
                                "type": "text",
                                "bbox": [120.0, 560.0, 240.0, 610.0],
                                "lines": [
                                    {
                                        "bbox": [120.0, 560.0, 240.0, 610.0],
                                        "spans": [{"content": "2024"}],
                                    }
                                ],
                            },
                            {
                                "type": "text",
                                "bbox": [520.0, 560.0, 960.0, 620.0],
                                "lines": [
                                    {
                                        "bbox": [520.0, 560.0, 960.0, 620.0],
                                        "spans": [{"content": "Comparison body text"}],
                                    }
                                ],
                            },
                            {
                                "type": "text",
                                "bbox": [100.0, 40.0, 900.0, 90.0],
                                "lines": [
                                    {
                                        "bbox": [100.0, 40.0, 900.0, 90.0],
                                        "spans": [{"content": "Compare Title"}],
                                    }
                                ],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "CompareDoc"))

    year_label = next(element for slide in presentation.slides for element in slide.elements if element.type == "text" and getattr(element, "content", "") == "2024")
    assert year_label.semantic_role == "subtitle"
    assert year_label.font_size is not None
    assert 16.0 <= year_label.font_size <= 20.0


def test_parser_accepts_middle_json_without_content_list(tmp_path):
    artifact_dir = tmp_path / "sample" / "hybrid_auto"
    artifact_dir.mkdir(parents=True)
    middle_json_path = artifact_dir / "sample_middle.json"
    middle_json_path.write_text(
        json.dumps(
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [1280.0, 720.0],
                        "para_blocks": [
                            {
                                "type": "title",
                                "bbox": [100.0, 80.0, 600.0, 160.0],
                                "lines": [
                                    {
                                        "bbox": [100.0, 80.0, 600.0, 160.0],
                                        "spans": [{"content": "Hello Middle Only"}],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    presentation = parse_mineru_output(str(tmp_path / "sample"))

    assert len(presentation.slides) == 1
    assert presentation.metadata.get("style_source") == "middle_json"
    assert presentation.slides[0].elements[0].content == "Hello Middle Only"
