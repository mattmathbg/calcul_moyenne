import streamlit as st
import importlib
import io
import csv
from typing import Dict, Any, List, Tuple

# ---- Import des jeux de données depuis ue_data_s4.py ----
# Assure-toi d'avoir un fichier ue_data_s4.py dans le même repo contenant variables ue_data_*
try:
    import ue_data_s4
except Exception as e:
    st.error(f"Impossible d'importer ue_data_s4.py : {e}")
    raise

# Récupère toutes les variables commençant par 'ue_data_'
ENSEMBLES_DONNEES: Dict[str, Dict] = {
    name: getattr(ue_data_s4, name)
    for name in dir(ue_data_s4)
    if name.startswith("ue_data_")
}

# ---- Fonctions (même logique que ton script original) ----
def charger_donnees(selection: str) -> Dict[str, Any]:
    data = ENSEMBLES_DONNEES.get(selection, {})
    # On clone la structure pour travailler sur une copie (évite de modifier l'original)
    import copy
    data_copy = copy.deepcopy(data)
    for ue in data_copy:
        if "rattrapage" in data_copy[ue]:
            data_copy[ue]["seconde_chance"] = data_copy[ue]["rattrapage"]
    return data_copy

def calculer_moyennes(ue_data: Dict[str, Any]) -> Tuple[List[Tuple[str,str,str]], float, float or None, List[str]]:
    resultats = []
    moyenne_globale, total_coefficients = 0.0, 0.0
    poids_restants_globaux, score_actuel_global = 0.0, 0.0
    ue_modifiables = []

    for ue, data in ue_data.items():
        coef = data.get("coef", 1)
        notes = data.get("grades", [])  # liste de (note or None, poids)
        score_actuel, poids_total, poids_restants = 0.0, 0.0, 0.0

        for note, poids in notes:
            if note is not None:
                score_actuel += note * poids
                poids_total += poids
            else:
                poids_restants += poids

        poids_total += poids_restants if poids_restants else 0
        moyenne_ue = (score_actuel / poids_total) if poids_total else 0.0

        note_seconde_chance = data.get("seconde_chance")
        if note_seconde_chance is not None:
            # on applique la règle que tu avais : moyenne = max(moyenne, 0.5*moyenne + 0.5*note_sc)
            moyenne_ue = max(moyenne_ue, moyenne_ue * 0.5 + note_seconde_chance * 0.5)

        score_necessaire = 10 * poids_total - score_actuel
        note_minimale = 0.0
        if poids_restants:
            try:
                note_minimale = score_necessaire / poids_restants
            except ZeroDivisionError:
                note_minimale = 0.0
            note_minimale = max(0.0, min(20.0, note_minimale))

        if moyenne_ue >= 10:
            statut = "✔ Validée"
        elif note_seconde_chance is not None:
            statut = "⚠ En attente du rattrapage"
        elif poids_restants:
            statut = f"⚠ {note_minimale:.2f}"
        else:
            statut = "❌ Impossible"

        moyenne_globale += moyenne_ue * coef
        total_coefficients += coef

        score_actuel_global += score_actuel * coef
        poids_restants_globaux += poids_restants * coef

        if poids_restants > 0:
            ue_modifiables.append(ue)

        resultats.append((ue, f"{moyenne_ue:.2f}", statut))

    moyenne_generale = (moyenne_globale / total_coefficients) if total_coefficients else 0.0

    if poids_restants_globaux > 0:
        score_necessaire_global = 10 * total_coefficients - score_actuel_global
        moyenne_min_restante = score_necessaire_global / poids_restants_globaux
        moyenne_min_restante = max(0.0, min(20.0, moyenne_min_restante))
    else:
        moyenne_min_restante = None

    return resultats, moyenne_generale, moyenne_min_restante, ue_modifiables

# ---- Session state initialization ----
if "selected_dataset" not in st.session_state:
    st.session_state.selected_dataset = list(ENSEMBLES_DONNEES.keys())[0] if ENSEMBLES_DONNEES else None
if "ue_data" not in st.session_state:
    st.session_state.ue_data = {}
if "original_loaded_name" not in st.session_state:
    st.session_state.original_loaded_name = None

# ---- UI ----
st.set_page_config(page_title="Gestion des Moyennes — Web", layout="wide")
st.title("Gestion des Moyennes avec Seconde Chance")

col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Jeux de données")
    if not ENSEMBLES_DONNEES:
        st.error("Aucun jeu de données ue_data_* trouvé dans ue_data_s4.py")
    else:
        dataset = st.selectbox("Choisissez l'ensemble de données :", list(ENSEMBLES_DONNEES.keys()), index=list(ENSEMBLES_DONNEES.keys()).index(st.session_state.selected_dataset) if st.session_state.selected_dataset in ENSEMBLES_DONNEES else 0)
        if st.button("Charger"):
            st.session_state.ue_data = charger_donnees(dataset)
            st.session_state.selected_dataset = dataset
            st.session_state.original_loaded_name = dataset
            st.success(f"Jeu de données '{dataset}' chargé.")

    st.markdown("---")
    st.subheader("Simuler une note")
    if st.session_state.ue_data:
        ue_to_sim = st.selectbox("UE à simuler :", options=list(st.session_state.ue_data.keys()), key="sim_ue")
        new_note = st.number_input("Nouvelle note (0-20)", min_value=0.0, max_value=20.0, step=0.5, format="%.2f", key="sim_note")
        if st.button("Simuler la note"):
            grades = st.session_state.ue_data[ue_to_sim].get("grades", [])
            for i, (note, poids) in enumerate(grades):
                if note is None:
                    grades[i] = (new_note, poids)
                    st.session_state.ue_data[ue_to_sim]["grades"] = grades
                    st.success(f"Note {new_note} ajoutée à '{ue_to_sim}'.")
                    break
            else:
                st.warning("Aucun examen restant pour cette UE.")
    else:
        st.info("Chargez un jeu de données pour simuler des notes.")

    st.markdown("---")
    st.subheader("Définir une seconde chance")
    if st.session_state.ue_data:
        ue_sc = st.selectbox("UE pour seconde chance :", options=list(st.session_state.ue_data.keys()), key="sc_ue")
        sc_note = st.number_input("Note seconde chance (0-20)", min_value=0.0, max_value=20.0, step=0.5, format="%.2f", key="sc_note")
        if st.button("Appliquer seconde chance"):
            st.session_state.ue_data[ue_sc]["seconde_chance"] = sc_note
            st.success(f"Seconde chance pour '{ue_sc}' définie à {sc_note}.")
    else:
        st.info("Chargez un jeu de données pour définir une seconde chance.")

    st.markdown("---")
    if st.session_state.ue_data:
        # Export CSV (streamlit download)
        def build_csv_string(ue_data_local):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["UE", "Moyenne", "Statut", "Seconde Chance"])
            resultats, _, _, _ = calculer_moyennes(ue_data_local)
            for ue, moyenne, statut in resultats:
                note_sc = ue_data_local.get(ue, {}).get("seconde_chance", "N/A")
                writer.writerow([ue, moyenne, statut, note_sc])
            return output.getvalue().encode("utf-8")

        csv_bytes = build_csv_string(st.session_state.ue_data)
        st.download_button("Exporter les résultats en CSV", data=csv_bytes, file_name="resultats.csv", mime="text/csv")

with col2:
    st.subheader("Tableau des résultats")
    if st.session_state.ue_data:
        resultats, moyenne_generale, moyenne_min_restante, ue_modifiables = calculer_moyennes(st.session_state.ue_data)

        # Affiche tableau
        st.table([{"UE": ue, "Moyenne": moyenne, "Statut": statut} for ue, moyenne, statut in resultats])

        # Moyenne générale
        st.markdown(f"### Moyenne Générale : **{moyenne_generale:.2f}/20**")
        if moyenne_generale >= 10:
            st.success("Moyenne générale validée ✅")
        else:
            st.error("Moyenne générale insuffisante ❌")

        # Moyenne minimale restante
        if moyenne_min_restante is not None:
            st.info(f"📌 Moyenne min nécessaire (pour compenser les notes manquantes) : **{moyenne_min_restante:.2f}/20**")
        else:
            st.success("✔ Toutes les notes sont déjà attribuées.")

        # Barre de progression (0..20 -> 0..1 pour st.progress)
        prog = max(0.0, min(1.0, moyenne_generale / 20.0))
        st.progress(prog)

        # Affiche UEs modifiables
        if ue_modifiables:
            st.write("UE modifiables (épreuves restantes) :", ", ".join(ue_modifiables))
        else:
            st.write("Aucune UE modifiable — toutes les épreuves sont notées.")
    else:
        st.info("Aucun jeu de données chargé. Sélectionne et charge un jeu de données à gauche.")

# Footer / aide rapide
st.markdown("---")
st.caption("Application convertie de Tkinter -> Streamlit. Déployable sur Streamlit Cloud (gratuit) ou autres plateformes.")
