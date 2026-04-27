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
