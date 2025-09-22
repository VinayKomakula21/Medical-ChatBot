import logging
from pathlib import Path
from typing import List, Dict, Any
import PyPDF2
from PIL import Image
import io

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path: Path) -> str:
    text = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"

        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {e}")
        raise

def get_pdf_metadata(file_path: Path) -> Dict[str, Any]:
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            metadata = {
                "page_count": len(pdf_reader.pages),
                "encrypted": pdf_reader.is_encrypted
            }

            # Extract document info if available
            if pdf_reader.metadata:
                info = pdf_reader.metadata
                metadata.update({
                    "title": info.get('/Title', ''),
                    "author": info.get('/Author', ''),
                    "subject": info.get('/Subject', ''),
                    "creator": info.get('/Creator', ''),
                    "producer": info.get('/Producer', ''),
                    "creation_date": str(info.get('/CreationDate', '')),
                    "modification_date": str(info.get('/ModDate', ''))
                })

            return metadata
    except Exception as e:
        logger.error(f"Error getting PDF metadata from {file_path}: {e}")
        return {"page_count": 0, "encrypted": False}

def extract_images_from_pdf(file_path: Path, output_dir: Path) -> List[Path]:
    image_paths = []
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            for page_num, page in enumerate(pdf_reader.pages):
                if '/XObject' in page['/Resources']:
                    xObject = page['/Resources']['/XObject'].get_object()

                    for obj in xObject:
                        if xObject[obj]['/Subtype'] == '/Image':
                            size = (xObject[obj]['/Width'], xObject[obj]['/Height'])
                            data = xObject[obj].get_data()

                            if xObject[obj]['/ColorSpace'] == '/DeviceRGB':
                                mode = "RGB"
                            else:
                                mode = "P"

                            if '/Filter' in xObject[obj]:
                                if xObject[obj]['/Filter'] == '/FlateDecode':
                                    img = Image.frombytes(mode, size, data)
                                    image_path = output_dir / f"page_{page_num}_{obj[1:]}.png"
                                    img.save(image_path)
                                    image_paths.append(image_path)

        return image_paths
    except Exception as e:
        logger.error(f"Error extracting images from PDF {file_path}: {e}")
        return []

def split_pdf_by_pages(file_path: Path, output_dir: Path, pages_per_split: int = 10) -> List[Path]:
    split_files = []
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)

            for start_page in range(0, total_pages, pages_per_split):
                pdf_writer = PyPDF2.PdfWriter()
                end_page = min(start_page + pages_per_split, total_pages)

                for page_num in range(start_page, end_page):
                    pdf_writer.add_page(pdf_reader.pages[page_num])

                output_path = output_dir / f"split_{start_page + 1}_to_{end_page}.pdf"
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)

                split_files.append(output_path)

        return split_files
    except Exception as e:
        logger.error(f"Error splitting PDF {file_path}: {e}")
        raise