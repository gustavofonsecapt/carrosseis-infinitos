from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi import status

from app.core.errors import AppError

from app.core.config import settings
from app.models import Project


class ExportService:
    def __init__(self) -> None:
        self.data_dir = settings.data_dir

    def build_zip(self, project: Project) -> BytesIO:
        if not project.slides:
            raise AppError("invalid_state", "Project has no slides to export", status.HTTP_400_BAD_REQUEST)

        buffer = BytesIO()
        with ZipFile(buffer, "w") as zf:
            for slide in sorted(project.slides, key=lambda s: s.index):
                if not slide.render_path:
                    raise AppError("export_failed_missing_file", "Slide without render. Run /render first.", status.HTTP_409_CONFLICT, {"slide_index": slide.index})
                png_path = Path(slide.render_path)
                if not png_path.exists():
                    raise AppError("export_failed_missing_file", f"Render missing on disk: {png_path}", status.HTTP_409_CONFLICT, {"slide_index": slide.index})
                zf.write(png_path, arcname=f"slide_{slide.index:02d}.png")
        buffer.seek(0)
        return buffer
