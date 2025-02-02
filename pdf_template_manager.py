import os
import json
from typing import Dict, List, Optional
import re
from pdf_processor import extract_pdf_content
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFTemplateManager:
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = template_dir
        self.codes_file = os.path.join(template_dir, "codes_database.json")
        os.makedirs(template_dir, exist_ok=True)
        self.load_codes_database()

    def load_codes_database(self):
        """Lädt die gespeicherte Code-Datenbank."""
        try:
            if os.path.exists(self.codes_file):
                with open(self.codes_file, 'r', encoding='utf-8') as f:
                    self.codes_database = json.load(f)
            else:
                self.codes_database = {
                    'auflagen': {},
                    'hinweise': {},
                    'templates': []
                }
        except Exception as e:
            logger.error(f"Fehler beim Laden der Code-Datenbank: {e}")
            self.codes_database = {
                'auflagen': {},
                'hinweise': {},
                'templates': []
            }

    def save_codes_database(self):
        """Speichert die Code-Datenbank."""
        try:
            with open(self.codes_file, 'w', encoding='utf-8') as f:
                json.dump(self.codes_database, f, ensure_ascii=False, indent=2)
            logger.info("Code-Datenbank erfolgreich gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Code-Datenbank: {e}")

    def classify_code(self, code: str) -> Optional[str]:
        """
        Klassifiziert einen Code als Auflage oder Hinweis.

        Args:
            code: Der zu klassifizierende Code

        Returns:
            Optional[str]: 'auflagen' oder 'hinweise' oder None bei ungültigem Code
        """
        code = code.strip()

        # Auflagen-Patterns (A-Codes)
        if re.match(r'^A\d{2}$', code) or re.match(r'^A[A-Z][a-z]$', code):
            return 'auflagen'

        # Hinweis-Patterns
        if any([
            re.match(r'^S\d{2}$', code),  # S-Codes
            re.match(r'^B\d{2}$', code),  # B-Codes
            re.match(r'^F\d{2}$', code),  # F-Codes
            code in ['Car', 'Cou', 'NoE', 'BnK']  # Spezielle Codes
        ]):
            return 'hinweise'

        return None

    def extract_codes_from_text(self, text: str) -> Dict[str, Dict[str, str]]:
        """
        Extrahiert Codes und deren Beschreibungen aus dem Text.
        Erkennt automatisch neue Codes und ihre Beschreibungen.
        """
        codes = {
            'auflagen': {},
            'hinweise': {}
        }

        # Verbesserte Pattern für Code-Beschreibungen
        patterns = {
            'code_line': r'(?:^|\s)([A-Z][A-Za-z0-9]{2,})\s+([^A\n][^\n]+)',  # Allgemeines Pattern für Codes
            'continuation': r'^(?!\s*[A-Z][A-Za-z0-9]{2,}\s)[^\n]+$'  # Fortsetzungszeilen
        }

        current_code = None
        current_description = []

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                if current_code and current_description:
                    category = self.classify_code(current_code)
                    if category:
                        codes[category][current_code] = ' '.join(current_description)
                    current_code = None
                    current_description = []
                continue

            # Suche nach neuen Code-Definitionen
            code_match = re.match(patterns['code_line'], line)
            if code_match:
                # Speichere vorherigen Code falls vorhanden
                if current_code and current_description:
                    category = self.classify_code(current_code)
                    if category:
                        codes[category][current_code] = ' '.join(current_description)

                current_code = code_match.group(1)
                current_description = [code_match.group(2).strip()]

            # Prüfe auf Fortsetzungszeilen
            elif current_code and re.match(patterns['continuation'], line):
                current_description.append(line)

        # Letzten Code hinzufügen
        if current_code and current_description:
            category = self.classify_code(current_code)
            if category:
                codes[category][current_code] = ' '.join(current_description)

        return codes

    def learn_from_pdf(self, pdf_content: io.BytesIO, template_name: str) -> bool:
        """
        Lernt Codes und deren Beschreibungen aus einer PDF-Vorlage.
        """
        try:
            text = extract_pdf_content(pdf_content)
            if not text:
                logger.error("Kein Text aus PDF extrahiert")
                return False

            logger.info(f"Verarbeite Template: {template_name}")
            new_codes = self.extract_codes_from_text(text)

            # Statistiken für Logging
            stats = {'new': 0, 'updated': 0}

            # Aktualisiere die Datenbank mit neuen Codes
            for category in ['auflagen', 'hinweise']:
                for code, description in new_codes[category].items():
                    if code not in self.codes_database[category]:
                        logger.info(f"Neuer {category}-Code gefunden: {code}")
                        self.codes_database[category][code] = description
                        stats['new'] += 1
                    elif self.codes_database[category][code] != description:
                        logger.info(f"Aktualisiere Beschreibung für {code}")
                        self.codes_database[category][code] = description
                        stats['updated'] += 1

            # Füge Template zur Liste hinzu
            if template_name not in self.codes_database['templates']:
                self.codes_database['templates'].append(template_name)

            self.save_codes_database()
            logger.info(f"Template verarbeitet: {stats['new']} neue Codes, {stats['updated']} aktualisierte Codes")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Lernen aus PDF: {str(e)}")
            return False

    def get_code_description(self, code: str) -> Optional[str]:
        """
        Gibt die Beschreibung für einen Code zurück.
        """
        category = self.classify_code(code)
        if category:
            return self.codes_database[category].get(code)
        return None

    def get_all_codes(self) -> Dict[str, Dict[str, str]]:
        """
        Gibt alle bekannten Codes und deren Beschreibungen zurück.
        """
        return self.codes_database

    def reload_templates(self):
        """
        Liest alle gespeicherten Vorlagen erneut ein und aktualisiert die Code-Datenbank.
        """
        try:
            logger.info("Starte Neueinlesen aller Vorlagen")
            # Setze Code-Datenbank zurück
            self.codes_database = {
                'auflagen': {},
                'hinweise': {},
                'templates': []
            }

            template_files = [f for f in os.listdir(self.template_dir) if f.endswith('.pdf')]

            for template_file in template_files:
                template_path = os.path.join(self.template_dir, template_file)
                logger.info(f"Lese Vorlage neu ein: {template_file}")

                try:
                    with open(template_path, 'rb') as f:
                        pdf_content = io.BytesIO(f.read())
                        self.learn_from_pdf(pdf_content, template_file)
                except Exception as e:
                    logger.error(f"Fehler beim Einlesen der Vorlage {template_file}: {e}")
                    continue

            logger.info(f"Vorlagen-Reload abgeschlossen: {len(template_files)} Vorlagen verarbeitet")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Reload der Vorlagen: {e}")
            return False