import streamlit as st
import pandas as pd
from pdf_processor import extract_pdf_content
from data_analyzer import analyze_vehicle_tire_combination
from utils import format_results, validate_pdf
from pdf_template_manager import PDFTemplateManager
import io
import json
import datetime
from pathlib import Path

# Initialize PDF Template Manager
template_manager = PDFTemplateManager()

def save_feedback(feedback_type: str, description: str, page_section: str) -> bool:
    """
    Saves user feedback to a JSON file.

    Args:
        feedback_type: Type of feedback (bug/suggestion)
        description: Detailed feedback description
        page_section: Section of the page where feedback was submitted

    Returns:
        bool: True if feedback was saved successfully
    """
    try:
        # Create feedback directory if it doesn't exist
        feedback_dir = Path("feedback")
        feedback_dir.mkdir(exist_ok=True)

        feedback_file = feedback_dir / "feedback.json"

        # Load existing feedback
        if feedback_file.exists():
            with open(feedback_file, "r", encoding="utf-8") as f:
                feedback_data = json.load(f)
        else:
            feedback_data = []

        # Add new feedback
        feedback_data.append({
            "type": feedback_type,
            "description": description,
            "section": page_section,
            "timestamp": datetime.datetime.now().isoformat()
        })

        # Save updated feedback
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(feedback_data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return False

def filter_results(results, vehicle_search="", tire_search=""):
    """
    Filtert die Ergebnisse basierend auf den Suchkriterien.
    """
    filtered = []
    for result in results:
        vehicle_match = vehicle_search.lower() in result['Fahrzeug'].lower() if vehicle_search else True
        tire_match = tire_search.lower() in result['Reifengröße'].lower() if tire_search else True
        if vehicle_match and tire_match:
            filtered.append(result)
    return filtered

def main():
    st.set_page_config(
        page_title="KBA Reifen-Prüfung",
        page_icon="🚗",
        layout="wide"
    )

    st.title("KBA Dokument-Analyse für Fahrzeug-Reifen-Kombinationen")

    # Add feedback button in the sidebar
    with st.sidebar:
        st.write("## 📝 Feedback & Bug-Meldung")
        if st.button("Problem melden / Feedback geben"):
            with st.form("feedback_form"):
                feedback_type = st.selectbox(
                    "Art des Feedbacks",
                    ["Bug/Problem", "Verbesserungsvorschlag"]
                )
                page_section = st.selectbox(
                    "Betroffener Bereich",
                    ["PDF-Upload", "Analyse-Ergebnisse", "Vorlagen-Verwaltung", "Sonstiges"]
                )
                description = st.text_area(
                    "Beschreibung",
                    placeholder="Bitte beschreiben Sie das Problem oder Ihren Vorschlag..."
                )
                submit_button = st.form_submit_button("Feedback senden")

                if submit_button:
                    if description.strip():
                        if save_feedback(feedback_type, description, page_section):
                            st.success("Vielen Dank für Ihr Feedback! Wir werden es prüfen.")
                        else:
                            st.error("Feedback konnte nicht gespeichert werden. Bitte versuchen Sie es später erneut.")
                    else:
                        st.warning("Bitte geben Sie eine Beschreibung ein.")

    # Initialize session state
    if 'results' not in st.session_state:
        st.session_state.results = None

    # Tabs für verschiedene Funktionen
    tab1, tab2 = st.tabs(["📄 Dokument analysieren", "⚙️ PDF-Vorlagen verwalten"])

    with tab1:
        # Suchfelder
        col1, col2 = st.columns(2)
        with col1:
            vehicle_search = st.text_input("🚗 Fahrzeug suchen", "")
        with col2:
            tire_search = st.text_input("🛞 Reifengröße suchen", "")

        uploaded_file = st.file_uploader("KBA/ABE PDF-Dokument hochladen", type="pdf")

        if uploaded_file is not None:
            try:
                # Read file content
                file_content = uploaded_file.read()

                # Create fresh BytesIO object for validation
                with io.BytesIO(file_content) as pdf_buffer:
                    if not validate_pdf(pdf_buffer):
                        st.error("Das hochgeladene Dokument scheint kein gültiges KBA/ABE PDF zu sein.")
                        return

                # Process PDF with fresh BytesIO object
                with st.spinner('PDF wird analysiert...'):
                    with io.BytesIO(file_content) as pdf_buffer:
                        pdf_content = extract_pdf_content(pdf_buffer)

                    if not pdf_content:
                        st.error("Keine Daten im PDF gefunden.")
                        return

                    results = analyze_vehicle_tire_combination(pdf_content)

                    if results:
                        formatted_results = format_results(results)
                        st.session_state.results = formatted_results
                    else:
                        st.warning("Keine Fahrzeug-Reifen-Kombinationen im Dokument gefunden.")
                        return

            except Exception as e:
                st.error(f"Ein Fehler ist aufgetreten: {str(e)}")
                st.error("Bitte überprüfen Sie das PDF-Dokument und versuchen Sie es erneut.")
                return

        # Ergebnisanzeige
        if st.session_state.results is not None:
            st.success("Analyse abgeschlossen!")

            # Ergebnisse filtern
            filtered_results = filter_results(st.session_state.results, vehicle_search, tire_search)

            if not filtered_results:
                st.info("Keine Ergebnisse für die aktuelle Suche gefunden.")
                return

            # Show results in tabs
            result_tab1, result_tab2 = st.tabs(["📊 Übersicht", "📝 Details"])

            with result_tab1:
                st.dataframe(
                    pd.DataFrame(filtered_results),
                    use_container_width=True
                )

            with result_tab2:
                for result in filtered_results:
                    with st.expander(f"🚗 {result['Fahrzeug']}"):
                        # Reifengröße und Status
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"### 🛞 {result['Reifengröße']}")
                        with col2:
                            status_color = {
                                'Zulässig ohne Eintragung': '🟢',
                                'Zulässig mit Auflagen': '🟡',
                                'Prüfung erforderlich': '🟠',
                                'Nicht zulässig': '🔴'
                            }
                            status_emoji = status_color.get(result['Status'], '⚪')
                            st.markdown(f"### {status_emoji} {result['Status']}")

                        # Trennlinie
                        st.markdown("---")

                        # Auflagen
                        if result.get('Auflagen'):
                            st.markdown("#### ⚠️ Auflagen (A-Codes)")
                            for auflage in result['Auflagen']:
                                st.markdown(f"• {auflage}")

                        # Technische Hinweise
                        if result.get('Technische_Hinweise'):
                            st.markdown("#### 📝 Technische Hinweise")
                            for hinweis in result['Technische_Hinweise']:
                                st.markdown(f"• {hinweis}")

                        # Reifenkombinationen
                        if result.get('reifen_codes'):
                            st.markdown("#### 🛞 Reifenkombinationen (T-Codes)")
                            for code_info in result['reifen_codes']:
                                st.markdown(f"• **{code_info['code']}**: {code_info['beschreibung']}")

                        # Original Codes
                        if result.get('Original_Codes'):
                            st.markdown("#### 🔢 Original-Codes")
                            col1, col2 = st.columns(2)
                            with col1:
                                if result['Original_Codes'].get('auflagen'):
                                    st.markdown("**Auflagen:**")
                                    for code in sorted(result['Original_Codes']['auflagen']):
                                        st.markdown(f"• `{code}`")
                            with col2:
                                if result['Original_Codes'].get('hinweise'):
                                    st.markdown("**Hinweise:**")
                                    for code in sorted(result['Original_Codes']['hinweise']):
                                        st.markdown(f"• `{code}`")

                        # Zusätzliche Kennzeichnungen
                        if result.get('kennzeichnungen'):
                            st.markdown("#### ℹ️ Zusätzliche Kennzeichnungen")
                            kennzeichnungen = result['kennzeichnungen']
                            col1, col2 = st.columns(2)

                            with col1:
                                if kennzeichnungen.get('manufacturer'):
                                    st.markdown("**Hersteller:**")
                                    st.markdown(f"_{kennzeichnungen['manufacturer']}_")
                                if kennzeichnungen.get('wheel_size'):
                                    st.markdown("**Felgengröße:**")
                                    st.markdown(f"_{kennzeichnungen['wheel_size']}_")
                                if kennzeichnungen.get('type_version'):
                                    st.markdown("**Typ/Ausführung:**")
                                    st.markdown(f"_{kennzeichnungen['type_version']}_")

                            with col2:
                                if kennzeichnungen.get('manufacture_date'):
                                    st.markdown("**Herstelldatum:**")
                                    st.markdown(f"_{kennzeichnungen['manufacture_date']}_")
                                if kennzeichnungen.get('approval_id'):
                                    st.markdown("**Genehmigungszeichen:**")
                                    st.markdown(f"_{kennzeichnungen['approval_id']}_")
                                if kennzeichnungen.get('inset'):
                                    st.markdown("**Einpresstiefe:**")
                                    st.markdown(f"_{kennzeichnungen['inset']}_")

    with tab2:
        st.header("PDF-Vorlagen verwalten")
        st.write("Hier können Sie PDF-Dokumente als Vorlagen hochladen, aus denen das System Codes und deren Beschreibungen lernt.")

        col1, col2 = st.columns([3, 1])
        with col1:
            template_file = st.file_uploader("PDF-Vorlage hochladen", type="pdf", key="template_uploader")
            template_name = st.text_input("Name der Vorlage", placeholder="z.B. KBA-2024-001")
        with col2:
            if st.button("🔄 Vorlagen neu laden"):
                if template_manager.reload_templates():
                    st.success("Alle Vorlagen wurden erfolgreich neu eingelesen.")
                else:
                    st.error("Fehler beim Neuladen der Vorlagen.")

        if template_file and template_name:
            if st.button("Vorlage speichern"):
                file_content = template_file.read()
                with io.BytesIO(file_content) as pdf_buffer:
                    if template_manager.learn_from_pdf(pdf_buffer, template_name):
                        st.success(f"Vorlage '{template_name}' wurde erfolgreich gespeichert und verarbeitet.")
                    else:
                        st.error("Fehler beim Verarbeiten der Vorlage.")

        # Zeige gespeicherte Vorlagen
        st.subheader("Gespeicherte Vorlagen")
        templates = template_manager.codes_database.get('templates', [])
        if templates:
            for template in templates:
                st.write(f"- {template}")
        else:
            st.info("Noch keine Vorlagen gespeichert.")

        # Zeige gelernte Codes
        st.subheader("Gelernte Codes und Beschreibungen")
        codes = template_manager.get_all_codes()

        col1, col2 = st.columns(2)
        with col1:
            if codes['auflagen']:
                st.markdown("##### Auflagen (A-Codes)")
                for code, description in codes['auflagen'].items():
                    st.markdown(f"• **{code}**: {description}")

        with col2:
            if codes['hinweise']:
                st.markdown("##### Hinweise")
                for code, description in codes['hinweise'].items():
                    st.markdown(f"• **{code}**: {description}")

if __name__ == "__main__":
    main()