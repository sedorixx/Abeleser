from typing import Dict, List, Optional
from document_analyzer import analyze_vehicle_data, validate_tire_combination

def analyze_vehicle_tire_combination(pdf_content: str) -> List[Dict]:
    """
    Analysiert die Fahrzeug-Reifen-Kombinationen aus dem PDF-Inhalt.

    Args:
        pdf_content: Extrahierter PDF-Text

    Returns:
        List[Dict]: Analyseergebnisse
    """
    results = []

    # Verwende regelbasierte Analyse
    vehicles = analyze_vehicle_data(pdf_content)

    if not vehicles:
        # Fallback zur direkten Extraktion aus dem PDF
        from pdf_processor import extract_vehicle_info
        vehicles = extract_vehicle_info(pdf_content)

    for vehicle in vehicles:
        for tire_info in vehicle['reifen']:
            combination_status = validate_tire_combination(vehicle['fahrzeug'], tire_info)
            results.append({
                'fahrzeug': vehicle['fahrzeug'],
                'reifengroesse': tire_info['groesse'],
                'status': combination_status['status'],
                'hinweise': combination_status['hinweise'],
                'auflagen': combination_status.get('auflagen', [])
            })

    return results