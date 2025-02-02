import PyPDF2
import re
from typing import Dict, List, Optional
import io

def extract_pdf_content(pdf_file: io.BytesIO) -> Optional[str]:
    """
    Extrahiert Text aus einem PDF-Dokument.

    Args:
        pdf_file: BytesIO object containing the PDF

    Returns:
        Optional[str]: Extrahierter Text oder None bei Fehler
    """
    try:
        # Reset file pointer to beginning
        pdf_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_content = []

        for page in pdf_reader.pages:
            text_content.append(page.extract_text())

        return "\n".join(text_content)
    except Exception as e:
        raise Exception(f"Fehler beim PDF-Lesen: {str(e)}")

def extract_vehicle_info(text: str) -> List[Dict]:
    """
    Extrahiert Fahrzeuginformationen aus dem Text.

    Args:
        text: Extrahierter PDF-Text

    Returns:
        List[Dict]: Liste von Fahrzeugdaten
    """
    vehicles = []
    current_vehicle = None
    current_section = None

    # Updated patterns for better matching
    patterns = {
        'audi_header': r'Audi\s+([A-Z][A-Z0-9\s]+)',
        'type': r'(?:B\d+(?:,\s*B\d+)*)',
        'tire': r'(\d{2,3})[/-](\d{2,3})(?:ZR|R)(\d{2})',
    }

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for Audi model header
        audi_match = re.search(patterns['audi_header'], line)
        if audi_match:
            if current_vehicle:
                vehicles.append(current_vehicle)

            model_name = audi_match.group(1).strip()
            current_vehicle = {
                'fahrzeug': f"Audi {model_name}",
                'reifen': set()
            }
            continue

        # Check for vehicle type (B8, B81, etc.)
        if current_vehicle and re.search(patterns['type'], line):
            type_info = re.search(patterns['type'], line).group(0)
            current_vehicle['fahrzeug'] = f"{current_vehicle['fahrzeug']} {type_info}"

        # Look for tire sizes in the current line
        if current_vehicle:
            tire_matches = re.finditer(patterns['tire'], line)
            for match in tire_matches:
                tire_size = f"{match.group(1)}/{match.group(2)}R{match.group(3)}"
                current_vehicle['reifen'].add(tire_size)

    # Add the last vehicle if exists
    if current_vehicle:
        if len(current_vehicle['reifen']) > 0:
            current_vehicle['reifen'] = list(current_vehicle['reifen'])
            vehicles.append(current_vehicle)

    return vehicles