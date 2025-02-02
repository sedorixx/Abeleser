import os
from openai import OpenAI
from typing import Dict, List, Optional
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def analyze_vehicle_data(text: str) -> List[Dict]:
    """
    Analysiert den PDF-Text mit OpenAI, um Fahrzeug- und Reifenkombinationen zu extrahieren.

    Args:
        text: Extrahierter Text aus dem PDF

    Returns:
        List[Dict]: Liste von Fahrzeug-Reifen-Kombinationen
    """
    try:
        logger.info("Starte KI-Analyse des Dokumententexts")

        system_prompt = """
        Du bist ein Experte für KBA (Kraftfahrt-Bundesamt) Dokumente. Analysiere den Text und extrahiere alle Fahrzeug-Reifen-Kombinationen.
        Achte besonders auf:
        - Handelsbezeichnung (z.B. "Audi A4")
        - Fahrzeug-Typ (z.B. "B8, B81")
        - Reifengrößen (z.B. "255/40R19", "215/55R17")

        Gib die Daten in folgendem JSON-Format zurück:
        {
            "fahrzeuge": [
                {
                    "handelsbezeichnung": string,
                    "typ": string,
                    "reifen": [string]
                }
            ]
        }
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        # Parse JSON response
        result = json.loads(response.choices[0].message.content)
        logger.info(f"KI-Analyse erfolgreich: {len(result.get('fahrzeuge', [])) } Fahrzeuge gefunden")

        # Convert to internal format
        vehicles = []
        for v in result['fahrzeuge']:
            vehicle = {
                'fahrzeug': f"{v['handelsbezeichnung']} {v['typ']}".strip(),
                'reifen': v['reifen']
            }
            vehicles.append(vehicle)

        return vehicles

    except Exception as e:
        logger.error(f"Fehler bei der KI-Analyse: {str(e)}")
        # Fallback zur regelbasierten Analyse
        return fallback_analyze_vehicle_data(text)

def fallback_analyze_vehicle_data(text: str) -> List[Dict]:
    """
    Regelbasierte Analyse als Fallback wenn KI-Analyse fehlschlägt.
    """
    import re
    vehicles = []
    current_vehicle = None

    # Patterns für die Analyse
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

        # Suche nach Audi Modell
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

        # Suche nach Fahrzeugtyp
        if current_vehicle and re.search(patterns['type'], line):
            type_info = re.search(patterns['type'], line).group(0)
            current_vehicle['fahrzeug'] = f"{current_vehicle['fahrzeug']} {type_info}"

        # Suche nach Reifengrößen
        if current_vehicle:
            tire_matches = re.finditer(patterns['tire'], line)
            for match in tire_matches:
                tire_size = f"{match.group(1)}/{match.group(2)}R{match.group(3)}"
                current_vehicle['reifen'].add(tire_size)

    # Letztes Fahrzeug hinzufügen
    if current_vehicle and len(current_vehicle['reifen']) > 0:
        current_vehicle['reifen'] = list(current_vehicle['reifen'])
        vehicles.append(current_vehicle)

    return vehicles

def validate_tire_combination(vehicle: str, tire: str) -> Dict:
    """
    Verwendet KI um zu überprüfen, ob eine Fahrzeug-Reifen-Kombination zulässig ist.
    Falls KI nicht verfügbar, verwendet regelbasierte Prüfung.

    Args:
        vehicle: Fahrzeugbezeichnung
        tire: Reifengröße

    Returns:
        Dict: Status und Hinweise zur Kombination
    """
    try:
        logger.info(f"Prüfe Kombination: {vehicle} mit {tire}")

        prompt = f"""
        Bewerte die folgende Fahrzeug-Reifen-Kombination auf Zulässigkeit:
        Fahrzeug: {vehicle}
        Reifen: {tire}

        Antworte im JSON-Format:
        {{
            "status": string (einer von: "Zulässig ohne Eintragung", "Prüfung erforderlich", "Nicht zulässig"),
            "hinweise": string (detaillierte Begründung)
        }}
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"Kombinationsprüfung erfolgreich: {result['status']}")
        return result

    except Exception as e:
        logger.error(f"Fehler bei der Kombinationsprüfung: {str(e)}")
        # Fallback zur regelbasierten Prüfung
        return fallback_validate_tire_combination(vehicle, tire)

def fallback_validate_tire_combination(vehicle: str, tire: str) -> Dict:
    """
    Regelbasierte Prüfung als Fallback.
    """
    # Extrahiere Reifendimensionen
    import re
    match = re.match(r'(\d+)/(\d+)R(\d+)', tire)
    if not match:
        return {
            'status': 'Nicht zulässig',
            'hinweise': 'Ungültiges Reifenformat'
        }

    width, aspect, diameter = map(int, match.groups())

    # Grundlegende Plausibilitätsprüfungen
    if width < 155 or width > 335:
        return {
            'status': 'Prüfung erforderlich',
            'hinweise': 'Ungewöhnliche Reifenbreite'
        }

    if aspect < 25 or aspect > 80:
        return {
            'status': 'Prüfung erforderlich',
            'hinweise': 'Ungewöhnliches Höhen-Breiten-Verhältnis'
        }

    if diameter < 16 or diameter > 22:
        return {
            'status': 'Prüfung erforderlich',
            'hinweise': 'Ungewöhnlicher Felgendurchmesser'
        }

    return {
        'status': 'Zulässig ohne Eintragung',
        'hinweise': 'Standardkombination innerhalb üblicher Parameter'
    }