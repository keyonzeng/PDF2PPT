import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "mineru_output"


def process_pdf(input_file_path: str, model: str = "auto", request_id: str | None = None) -> dict:
    """
    Runs Mineru CLI to process a PDF.
    
    Args:
        input_file_path: Absolute path to the uploaded PDF file
        model: Mineru model to use ("auto" by default)
    """
    input_file = Path(input_file_path).resolve()
    output_path = OUTPUT_DIR
    
    # Ensure output directory exists (idempotent)
    output_path.mkdir(exist_ok=True, parents=True)

    if not input_file.exists():
        return {
            "status": "error",
            "error": f"Input PDF not found: {input_file}"
        }
    
    # Mineru CLI command
    cmd = [
        "uv", "run", "mineru",
        "-p", str(input_file),
        "-o", str(output_path),
        "-m", model
    ]

    print(f"Running Mineru: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True,
            cwd=str(BASE_DIR)
        )
        print(result.stdout)
        
        output_folder = output_path / input_file.stem
        if not output_folder.exists():
            return {
                "status": "error",
                "error": f"MinerU output folder was not created for {input_file.stem}"
            }

        return {
            "status": "success",
            "output_folder": str(output_folder),
            "logs": result.stdout,
            "request_id": request_id,
        }
        
    except subprocess.CalledProcessError as e:
        print(f"Mineru Failed: {e.stderr}")
        return {
            "status": "error",
            "error": e.stderr or e.stdout or "MinerU failed without stderr output"
        }
