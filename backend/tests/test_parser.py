from app.services.parser_service import parse_mineru_output
import json
from pathlib import Path

def test_parser():
    output_folder = Path("mineru_output") / "TheLastLeaf"
    
    try:
        presentation = parse_mineru_output(str(output_folder))
        print(f"Successfully parsed presentation with {len(presentation.slides)} slides.")
        
        for i, slide in enumerate(presentation.slides):
            print(f"Slide {i+1} (Page {slide.page_id}): {len(slide.elements)} elements")
            for elem in slide.elements[:3]: # print first 3 elements
                print(f"  - {elem.type}: {elem.content[:50]}...")
                
    except Exception as e:
        print(f"Parser failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parser()
