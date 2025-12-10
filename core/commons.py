import pymupdf  
from docx import Document
from pptx import Presentation
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import pytesseract
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import base64

from PIL import Image, ImageOps, ImageStat

import io
import re
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol
from functools import partial
from newsplease import NewsPlease, NewsArticle

class ImageProcessor(Protocol):
    def __call__(self, image: Image.Image, **kwargs) -> Image.Image:
        ...

def invert_colors_image(image: Image.Image, **kwargs) -> Image.Image:
    return ImageOps.invert(image.convert("RGB"))

def grayscale_image(image: Image.Image, **kwargs) -> Image.Image:
    return image.convert("L")

def scale_image_by_factor(img: Image.Image, factor=2, **kwargs) -> Image.Image:
    """
    Upscale/downscale images by a factor while keeping aspect ratio.
    """
    (width, height) = (int(img.width * factor), int(img.height * factor))
    return img.resize((width, height))

def rotate_image(img: Image.Image, angle=0, **kwargs) -> Image.Image:
    """
    Rotate image by a degree.
    """
    return img.rotate(angle)

def mirror_image(img: Image.Image, **kwargs) -> Image.Image:
    """
    Flip image left to right (like a mirror)
    """
    return img.transpose(Image.FLIP_LEFT_RIGHT)

def is_dark_background(img: Image, threshold: float = 127.5) -> bool:
    # dark background can confuse pytesseract, so we may need to invert the image
    # is true when average grayscale is smaller than the threshold
    gray = img.convert("L")  # Grayscale
    stat = ImageStat.Stat(gray)
    avg_brightness = stat.mean[0]
    return avg_brightness < threshold

IMAGE_PROCESSORS: dict[str, ImageProcessor] = {
    "invert": invert_colors_image,
    "grayscale": grayscale_image,
    "scale": scale_image_by_factor,
    "rotate": rotate_image,
    "rotate-left": partial(rotate_image, angle=270),
    "rotate-right": partial(rotate_image, angle=90),
    "mirror": mirror_image
}

class ImageOCR:
    base_image = None
    image_process_ops = []
    languages = "eng"
    
    def __init__(self, image: Image, process_instructions, languages: str):
        if isinstance(process_instructions, str):
            self.image_process_ops = self.get_ops_from_str(process_instructions)
        elif isinstance(process_instructions, list):
            self.image_process_ops = process_instructions
        else:
            raise ValueError("process_instructions must be a string or list!")
        self.base_image = image
        self.languages = languages
    def extract_text_from_image(self) -> str:
        processed_image = self.process_pipeline_images(self.base_image, self.image_process_ops)
        raw_text = pytesseract.image_to_string(processed_image, self.languages) # Apply pytesseract on image
        clean_text = re.sub(r'\n{2,}', '\n', raw_text) # Remove multiple newline (keep one newline)
        print("\n ===== DEBUG: TEXT EXTRACT FROM IMAGE ===== \n" + clean_text) # Debug
        return clean_text
    
    @staticmethod
    def get_ops_from_str(op_str:str) -> list:
        """
        Convert string instructions into a list of functions. Instrucition formats: 
        foo,bar:arg1=val1;arg2=val2,func,...
        """
        ops = []
        for item in op_str.split(","):
            if not item.strip():
                continue  # skip empty entries
            if ":" in item:
                # Param format: arg1=a,arg2=b,...
                name, param_str = item.split(":", 1)
                params = dict(p.split("=") for p in param_str.split(";")) # convert
                # Convert numeric params
                for k, v in params.items():
                    if "." in v or "e" in v.lower(): 
                        params[k] = float(v)
                    elif v.isdigit():
                        params[k] = int(v)
                ops.append((name.strip(), params))
            else:
                ops.append((item.strip(), {}))
        return ops

    @staticmethod
    def process_pipeline_images(image: Image, ops: list) -> Image:
        for op_name, params in ops:
            func = IMAGE_PROCESSORS[op_name]
            image = func(image, **params)
        return image



    def test_ocr(self, lower_bound_size=500, upper_bound_size=1200):
        """
        Extract text from an image using OCR. Return the longest string from extracting manipulated images.
        @params:
            @image: The PIL images.
            @lower_bound_size: Lowest margin for upscaling images.
            @upper_bound_size: The maximum sizes of width or height that can be upscaled in second order.
            @second_scale_factor: Upscale the image in second-order processing.
            @languages: Specific languages need to be scanned.
        """
        text_og = self.extract_text_from_image()
        
        image = self.base_image
        # First order image manipulation: apply on original image, 
        # Using invertion for dark background and upscale if image is too small
        first_ops = []
        if is_dark_background(image, threshold=255/2): # Invert the image if lower than threshold
            first_ops.append( (invert_colors_image, {}) )
        if image.width * image.height <= lower_bound_size * lower_bound_size: # Scale small image by a factor
            first_factor = lower_bound_size / min(image.width, image.height)
            first_ops.append((scale_image_by_factor, {"factor": first_factor}))

        first_image = self.process_pipeline_images(image, first_ops) # process image
        first_image.save("img_first_order.jpg")
        text_first_order = self.extract_text_from_image(first_image, self.languages) # apply ocr and extract text
        
        # Second order image manipulation: apply on first-order processed image
        # Using grayscale and scale image by a factor of two
        second_ops = list(first_ops) # create a copy of the first instructions
        second_ops.append((grayscale_image, {})) # Convert to grayscale
        if max(image.width, image.height) < upper_bound_size: # Upscale if smaller than upperbound margin
            second_factor = upper_bound_size / max(image.width, image.height) 
            second_ops.append((scale_image_by_factor, {"factor": second_factor}))
            
        second_image = self.process_pipeline_images(image, second_ops) # process image
        second_image.save("img_second_order.jpg")
        text_second_order = self.extract_text_from_image(second_image, self.languages) # apply ocr and extract text

        all_texts_extractions = [text_og, text_first_order, text_second_order] 
        
        for text in all_texts_extractions: # debug
            print("========== DEBUG MODE ========== \n", repr(text))
        return max(all_texts_extractions, key=len) # longest string tends to be the most accurate answer?
                                                # After a couple of benchmarking, I figure this is no longer true.
                                                # A better option would be asking the user to 
                                                # either specify pre-processing or edit the image by themself.

def extract_text_from_pdf_by_OCR(pdf_bytes: bytes, process_instruction="", languages='eng'):
    page_count = pdfinfo_from_bytes(pdf_bytes)["Pages"]
    text = ""
    # Apply OCR on each page
    # Note: there is an opportunity to have a multi-thread conversion here
    # However, be aware of race condition (extracting slide before converting) and overloading memory
    for i in range(1, page_count + 1):
        # Convert 1 page at a time
        image = convert_from_bytes(pdf_bytes, dpi=150, first_page=i, last_page=i)[0] 
        # Apply OCR onto the images
        slideOCR = ImageOCR(image, process_instruction, languages)
        slide_text = f"Page {i}:\n" + slideOCR.extract_text_from_image() + '\n'
        text += slide_text    
    
    return text   

def detect_parquet_magic(file_bytes: bytes) -> bool:
    # Why: Parquet signature is always the first 4 bytes
    return file_bytes.startswith(b"PAR1")


def get_etx_from_content_type(content_type):
    if content_type.endswith('pdf'):
        return '.pdf'
    elif content_type.endswith('document'):
        return '.docx'
    elif content_type.endswith('presentation'):
        return '.pptx'
    elif content_type.endswith('sheet'):
        return '.xlsx'
    elif content_type.endswith('text'):
        return '.txt'
    elif content_type.endswith('plain'):
        return '.txt'
    elif content_type.endswith('csv'):
        return '.csv'
    elif content_type.endswith('json'):
        return '.json'
    elif content_type.endswith('xml'):
        return '.xml'
    elif content_type.endswith('jpeg'):
        return '.jpg'
    elif content_type.endswith('png'):
        return '.png'
    elif content_type.endswith("parquet"):
        return '.parquet'
    return content_type

def get_text_from_stream_with_OCR(stream: bytes, ext: str, process_instructions="", languages='eng') -> str:
    supported_pdf = {'.pdf'}
    supported_img = {'.png', '.jpg', '.jpeg'}
    supported_doc = {'.doc' , '.docx', '.pptx', '.ppt', '.csv', '.xlsx'}
    # supported_format = supported_pdf + supported_img + supported_doc
    
    if ext in supported_img:
        image = Image.open(io.BytesIO(stream))
        imageOCR = ImageOCR(image, process_instructions, languages)
        return imageOCR.extract_text_from_image()
    
    if ext in supported_pdf:
        return extract_text_from_pdf_by_OCR(stream, process_instructions, languages)
    
    if ext not in supported_doc:
        raise ValueError(f"File format {ext} not supported for OCR yet!")
    
    # Export an pdf from the file, then apply OCR on each page of the pdf
    # Store the pdf as a temporary file that would be deleted after operation is done
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(stream)
        temp_file.flush()
        temp_path = Path(temp_file.name)

    pdf_path = temp_path.with_suffix(".pdf")
    try:
        # Convert to PDF using LibreOffice
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(temp_path.parent), str(temp_path)],
            check=True,
            timeout=120,
            capture_output=True,
            text=True,
        )
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"Expected PDF not found at {pdf_path}. LibreOffice output:\n{result.stdout}\n{result.stderr}")

        # Apply OCR on the pdf
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        text = extract_text_from_pdf_by_OCR(pdf_bytes, process_instructions, languages)

    finally:
        temp_path.unlink(missing_ok=True)
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
    
    return text

def get_text_from_stream(stream, filetype):
    print("Sanity check: get_text_from_stream called with filetype:", filetype)
    stream = io.BytesIO(stream)
    if filetype == '.pdf':
        return get_text_from_pdf(stream)
    elif filetype == '.docx' or filetype == '.doc':
        return get_text_from_docx(stream)
    elif filetype == '.pptx' or filetype == '.ppt':
        return get_text_from_pptx(stream)
    elif filetype == '.xlsx' or filetype == '.xls':
        return get_text_from_xlsx(stream)
    elif filetype == '.parquet':
        return stream_parquet_as_strings(stream)
    return stream.read().decode('utf-8', errors="ignore").splitlines()
    # reader = PdfReader(stream)
    # texts = []
    # for page in  reader.pages: 
    #     texts.append(page.extract_text())
    # return texts


def row_to_string(row: dict, column_names: list[str]) -> str:
    # Optimization: Pass column_names explicitly to avoid calling row.keys() every time
    # and to guarantee the order matches the file schema exactly.
    parts = [f"{col}:{row[col]}" for col in column_names]
    return ";".join(parts)

def stream_parquet_as_strings(parquet_path: str):
    """
    Generator that yields one formatted string per row, 
    keeping memory usage low.
    """
    # 1. Open the file wrapper (reads only metadata/schema, not data)
    parquet_file = pq.ParquetFile(parquet_path)
    
    # 2. Extract schema names once to ensure deterministic ordering
    columns = parquet_file.schema.names
    
    # 3. Iterate over the file in batches (Row Groups)
    # You can tune batch_size based on your memory constraints (default is usually fine)
    for batch in parquet_file.iter_batches():
        
        # 4. Convert only this small batch to a list of dicts
        batch_rows = batch.to_pylist()
        
        for row in batch_rows:
            yield row_to_string(row, columns)

def get_text_from_pdf(stream):
    print("Extracting text from PDF...")
    pdf_bytes = stream.read()
    with pymupdf.open(stream=pdf_bytes) as doc:
        if doc.is_encrypted:
            doc.authenticate("")
        text = ""
        for page in doc:
            text += page.get_text() + '\n'
    return text

def get_text_from_docx(stream):
    doc = Document(stream)
    texts = []
    for para in doc.paragraphs:
        texts.append(para.text)
    return texts

def get_text_from_pptx(stream):
    prs = Presentation(stream)
    texts = []
    for i, slide in enumerate(prs.slides, start=1):
        slide_text = f"Slide {i}: "
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                slide_text += shape.text + '\n'
        if slide.has_notes_slide:
            note_text = (slide.notes_slide.notes_text_frame.text).strip() # Get texts inside note and strip them
            if note_text != '':
                texts.append(f"Slide {i} note: " + note_text + '\n')
        
        texts.append(slide_text)
    return texts

def get_text_from_xlsx(stream):
    df = pd.read_excel(stream)
    # Convert to list of dicts (records)
    return df.to_string()

def get_text_from_file(file):
    stream = open(file, 'rb').read()
    return get_text_from_stream(stream,  '.jpg')

def get_dict_except_blacklist(target, blacklist: tuple[str,...] | list[str]):
    """Recursively remove fields in blacklist_set from dicts or lists."""
    blacklist_set = set(blacklist)
    if isinstance(target, dict):
        return {
            key: get_dict_except_blacklist(value, blacklist_set)
            for key, value in target.items()
            if key not in blacklist_set
        }
    elif isinstance(target, list):
        return [get_dict_except_blacklist(item, blacklist_set) for item in target]
    else:
        return target


def crawl_news_from_url(url:str):
    article = NewsPlease.from_url(url)
    return article.get_dict()
    
def main():
    # Example usage
    path = '../../test_files/image/' 
    filename = 'khang.jpg'
    stream = open(path + filename, 'rb').read()
    text = get_text_from_stream_with_OCR(stream, '.jpg', "scale:factor=1.25", languages="eng+vie")
    print(text)

if __name__ == "__main__":
    main()