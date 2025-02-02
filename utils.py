from typing import List, Dict
import io
import PyPDF2

def validate_pdf(pdf_file: io.BytesIO) -> bool:
    """
    Überprüft, ob es sich um ein gültiges KBA/ABE PDF handelt.

    Args:
        pdf_file: BytesIO object containing the PDF

    Returns:
        bool: True wenn valid, False sonst
    """
    try:
        # Reset file pointer to beginning
        pdf_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        first_page = pdf_reader.pages[0].extract_text().lower()

        # Reset file pointer again for future reads
        pdf_file.seek(0)

        # Typische KBA/ABE Dokumentenmerkmale
        kba_indicators = [
            'kraftfahrt-bundesamt',
            'abe',
            'allgemeine betriebserlaubnis',
            'typgenehmigung',
            'gutachten'
        ]

        return any(indicator in first_page for indicator in kba_indicators)
    except:
        return False

def format_results(results: List[Dict]) -> List[Dict]:
    """
    Formatiert die Analyseergebnisse für die Anzeige.

    Args:
        results: Liste der Analyseergebnisse

    Returns:
        List[Dict]: Formatierte Ergebnisse
    """
    formatted = []

    for result in results:
        formatted.append({
            'Fahrzeug': result['fahrzeug'],
            'Reifengröße': result['reifengroesse'],
            'Status': result['status'],
            'Hinweise': result['hinweise'],
            'Auflagen': result.get('auflagen', []),
            'Technische_Hinweise': result.get('technische_hinweise', []),
            'Original_Codes': result.get('original_codes', {'auflagen': [], 'hinweise': []})
        })

    return formatted