import logging
from typing import Dict, List
import re
from pdf_template_manager import PDFTemplateManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize template manager
template_manager = PDFTemplateManager()

def extract_codes_from_line(line: str) -> Dict[str, List[str]]:
    """
    Extrahiert und kategorisiert alle Codes aus einer Zeile.
    """
    codes = {
        'auflagen': [],
        'hinweise': [],
        'reifen_codes': []
    }

    # Verbesserte Patterns für Code-Erkennung
    patterns = {
        # Erweiterte Auflagen-Erkennung: A12, A12a, A12.1, A-12, etc.
        'auflagen': r'(?:^|\s)(A(?:[0-9]+[a-z]?(?:\.[0-9]+)?|-[0-9]+))(?=[\s\.,]|$)',
        # T-Codes für Reifenkombinationen
        'reifen': r'(?:^|\s)(T\d+)(?=[\s\.,]|$)',
        # Andere technische Codes und Spezialfälle
        'hinweise': r'(?:^|\s)([BCDEFGHIJKLMNOPQRSUVWXYZ]\d+[a-z]?|Car|Cou|NoE|BnK)(?=[\s\.,]|$)'
    }

    # Debug-Log für die Zeile
    logger.info(f"Verarbeite Zeile: {line}")

    # Extrahiere Codes für jede Kategorie
    for category, pattern in patterns.items():
        matches = list(re.finditer(pattern, line))
        if matches:
            for match in matches:
                code = match.group(1)
                if category == 'reifen':
                    # Für T-Codes die komplette Beschreibung extrahieren
                    codes['reifen_codes'].append({
                        'code': code,
                        'beschreibung': line.strip()
                    })
                elif category == 'auflagen':
                    # Für Auflagen den Code normalisieren und speichern
                    normalized_code = code.replace('-', '')  # Entferne mögliche Bindestriche
                    codes['auflagen'].append(normalized_code)
                else:
                    codes['hinweise'].append(code)

    # Debug-Log für extrahierte Codes
    logger.info(f"Extrahierte Codes: {codes}")
    return codes

def analyze_vehicle_data(text: str) -> List[Dict]:
    """
    Regelbasierte Analyse von KBA Dokumenten.
    """
    vehicles = []
    current_vehicle = None
    current_section = None

    # Updated patterns for better matching
    patterns = {
        'audi_header': r'Audi\s+([A-Z][A-Z0-9\s]+)',
        'type': r'(?:B\d+(?:,\s*B\d+)*)',
        'tire': r'(\d{2,3})[/-](\d{2,3})(?:ZR|R)(\d{2})',
        'manufacturer': r'Hersteller(?:zeichen)?:\s*([^\n]+)',
        'wheel_size': r'Felgengröße:\s*([^\n]+)',
        'type_version': r'Typ und (?:die )?Ausführung:\s*([^\n]+)',
        'manufacture_date': r'Herstelldatum \((?:Monat und Jahr|month and year)\):\s*([^\n]+)',
        'approval_id': r'Genehmigungszeichen:\s*([^\n]+)',
        'inset': r'Einpresstiefe:\s*([^\n]+)',
        # Verbesserte T-Code Erkennung
        't_code': r'(T\d+)\s+Reifen\s+\([^)]+\)\s+zulässig\s+für\s+([^\n]+)'
    }

    lines = text.split('\n')
    current_code_block = None
    code_description = []

    for line in lines:
        line = line.strip()
        if not line:
            # Speichere gesammelte Code-Beschreibung
            if current_code_block and code_description:
                template_manager.codes_database.setdefault('auflagen', {})[current_code_block] = ' '.join(code_description)
            current_code_block = None
            code_description = []
            continue

        # Suche nach Auflagen/Hinweis-Definitionen
        code_match = re.match(r'^([A-Z]\d+[a-z]?(?:\.[0-9]+)?)\s+(.+)$', line)
        if code_match:
            # Speichere vorherige Code-Beschreibung
            if current_code_block and code_description:
                template_manager.codes_database.setdefault('auflagen', {})[current_code_block] = ' '.join(code_description)
            current_code_block = code_match.group(1)
            code_description = [code_match.group(2)]
            continue
        elif current_code_block and line:
            code_description.append(line)

        # Suche nach T-Code Beschreibungen
        t_code_match = re.search(patterns['t_code'], line)
        if t_code_match:
            if current_vehicle and 'reifen_codes' not in current_vehicle:
                current_vehicle['reifen_codes'] = []
            if current_vehicle:
                current_vehicle['reifen_codes'].append({
                    'code': t_code_match.group(1),
                    'beschreibung': t_code_match.group(2).strip()
                })
            continue

        # Rest der Funktion bleibt unverändert...
        audi_match = re.search(patterns['audi_header'], line)
        if audi_match:
            if current_vehicle:
                vehicles.append(current_vehicle)

            model_name = audi_match.group(1).strip()
            current_vehicle = {
                'fahrzeug': f"Audi {model_name}",
                'reifen': [],
                'kennzeichnungen': {},
                'reifen_codes': []
            }
            continue

        if current_vehicle:
            tire_matches = list(re.finditer(patterns['tire'], line))
            if tire_matches:
                for match in tire_matches:
                    tire_size = f"{match.group(1)}/{match.group(2)}R{match.group(3)}"
                    codes = extract_codes_from_line(line)
                    current_vehicle['reifen'].append({
                        'groesse': tire_size,
                        'codes': codes,
                        'original_line': line
                    })

            for key, pattern in patterns.items():
                if key not in ['audi_header', 'type', 'tire', 't_code']:
                    match = re.search(pattern, line)
                    if match:
                        current_vehicle['kennzeichnungen'][key] = match.group(1).strip()

    # Füge das letzte Fahrzeug hinzu
    if current_vehicle and (len(current_vehicle['reifen']) > 0 or len(current_vehicle.get('reifen_codes', [])) > 0):
        vehicles.append(current_vehicle)

    return vehicles

def validate_tire_combination(vehicle: str, tire_info: Dict) -> Dict:
    """
    Validiert eine Fahrzeug-Reifen-Kombination und prüft die zugehörigen Codes.
    """
    tire = tire_info['groesse']
    codes = tire_info.get('codes', {'auflagen': [], 'hinweise': [], 'reifen_codes': []})
    original_line = tire_info.get('original_line', '')

    # Validiere Reifengröße
    match = re.match(r'(\d+)/(\d+)R(\d+)', tire)
    if not match:
        return {
            'status': 'Nicht zulässig',
            'hinweise': ['Ungültiges Reifenformat'],
            'auflagen': [],
            'technische_hinweise': []
        }

    width, aspect, diameter = map(int, match.groups())
    validation_messages = []

    # Grundlegende Dimensionsprüfungen
    if width < 155 or width > 335:
        validation_messages.append('Ungewöhnliche Reifenbreite')
    if aspect < 25 or aspect > 80:
        validation_messages.append('Ungewöhnliches Höhen-Breiten-Verhältnis')
    if diameter < 16 or diameter > 22:
        validation_messages.append('Ungewöhnlicher Felgendurchmesser')

    # Verarbeite Auflagen und Hinweise
    auflagen = []
    technische_hinweise = []
    reifen_codes = codes.get('reifen_codes', [])

    # Verarbeite Auflagen (A-Codes)
    for code in codes['auflagen']:
        description = template_manager.get_code_description(code)
        if description:
            auflagen.append(f"{code}: {description}")
        else:
            auflagen.append(code)

    # Verarbeite Hinweise
    for code in codes['hinweise']:
        description = template_manager.get_code_description(code)
        if description:
            technische_hinweise.append(f"{code}: {description}")
        else:
            technische_hinweise.append(code)

    # Bestimme Status basierend auf Codes und Validierung
    if validation_messages:
        status = 'Prüfung erforderlich'
    elif codes['auflagen']:
        status = 'Zulässig mit Auflagen'
    else:
        status = 'Zulässig ohne Eintragung'

    return {
        'status': status,
        'hinweise': validation_messages,
        'auflagen': auflagen,
        'technische_hinweise': technische_hinweise,
        'original_codes': codes,
        'reifen_codes': reifen_codes
    }