from app.services.ppt_gen_service import generate_pptx
from app.core.models import Presentation, Slide, TextElement
import os

def test_generate_pptx_simple():
    # Arrange
    presentation = Presentation()
    slide1 = Slide(page_id=1, width=595.0, height=842.0)
    slide1.add_element(TextElement(content="Test Title", bbox=[50.0, 50.0, 500.0, 100.0], type="text"))
    slide1.add_element(TextElement(content="Body Content", bbox=[50.0, 150.0, 500.0, 300.0], type="text"))
    presentation.slides.append(slide1)
    
    # Act
    output_path = generate_pptx(presentation, template_key="default", request_id="test-run")
    
    # Assert
    assert os.path.exists(output_path)
    assert output_path.endswith(".pptx")
    print(f"Generated PPTX at: {output_path}")

if __name__ == "__main__":
    test_generate_pptx_simple()
