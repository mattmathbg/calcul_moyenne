import streamlit as st
import io
import csv
from typing import Dict, Any, List, Tuple

# ---------- CONFIG ----------
st.set_page_config(page_title="Calculateur de Moyenne — S5", layout="wide")
st.title("🎓 Calculateur de Moyenne — S5")
st.caption("Choisis un dataset existant ou ajoute tes UEs et notes, puis découvre ta moyenne générale.")

# ---------- IMPORT DES DONNÉES ----------
try:
    import ue_data_s5  # ton fichier .py contenant ue_data_moi, ue_data_hugo, etc.
except ImportError:
    st.error("Impossible de charger ue_data_s5.py")
    st.stop()

# Récupère toutes les variables ue_data_* du fichier
ENSEMBLES_DONNEES: Dict[str, Dict] = {
    name: getattr(ue_data_s5, name)
    for name in dir(ue_data_s5)
    if name.startswith("ue_data_")
}

# ---------- INIT SESSION ----------
if "ue_data" not in st.session_state:
    st.session_state.ue_data: Dict[str, Dict[str, Any]] = {}
if "selected_dataset" not in st.session_state:
    st.session_state.selected_dataset = None

# ---------- FONCTION CALCUL DES MOYENNES ----------
def calculer_moyennes(ue_data: Dict[str, Any]) -> Tuple[List[Tuple[str,str,str]], float, float or None, List[str]]:
    resultats = []
    moyenne_globale, total_coefficients = 0.0, 0.0
    poids_restants_globaux, score_actuel_global = 0.0, 0.0
    ue_modifiables = []

    for ue, data in ue_data.items():
        coef = data.get("coef", 1)
        notes = data.get("grades", [])
        score_actuel, poids_total, poids_restants = 0.0, 0.0, 0.0

        for note, poids in notes:
            if note is not None:
                score_actuel += note * poids
                poids_total += poids
            else:
                poids_restants += poids

        poids_total += poids_restants if poids_restants else 0
        moyenne_ue = (score_actuel / poids_total) if poids_total else 0.0

        note_sc = data.get("seconde_chance")
        if note_sc is not None:
            moyenne_ue = max(moyenne_ue, 0.5*moyenne_ue + 0.5*note_sc)

        score_necessaire = 10 * poids_total - score_actuel
        note_minimale = 0.0
        if poids_restants:
            try:
                note_minimale = score_necessaire / poids_restants
            except ZeroDivisionError:
                note_minimale = 0.0
            note_minimale = max(0.0, min(20.0, note_minimale))

        if moyenne_ue >= 10:
            statut = "✅ Validée"
        elif note_sc is not None:
            statut = "⚠ En attente du rattrapage"
        elif poids_restants:
            statut = f"⚠ Besoin ≥ {note_minimale:.2f}"
        else:
            statut = "❌ Non validée"

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

# ---------- CHOIX DU DATASET ----------
if ENSEMBLES_DONNEES:
    dataset = st.selectbox("Choisir un dataset pré-rempli", list(ENSEMBLES_DONNEES.keys()))
    if st.button("Charger ce dataset"):
        st.session_state.ue_data = ENSEMBLES_DONNEES[dataset]
        st.session_state.selected_dataset = dataset
        st.success(f"Dataset '{dataset}' chargé !")

# ---------- AJOUT UE ----------
st.sidebar.header("➕ Ajouter une UE")
ue_name = st.sidebar.text_input("Nom de l'UE")
coef = st.sidebar.number_input("Coefficient", min_value=0.5, max_value=10.0, value=1.0, step=0.5)
if st.sidebar.button("Ajouter l’UE"):
    if ue_name.strip():
        st.session_state.ue_data[ue_name] = {"coef": coef, "grades": []}
        st.sidebar.success(f"UE '{ue_name}' ajoutée.")

# ---------- AJOUT NOTE ----------
st.sidebar.markdown("---")
if st.session_state.ue_data:
    st.sidebar.header("🧮 Ajouter une note")
    ue_select = st.sidebar.selectbox("UE", options=list(st.session_state.ue_data.keys()))
    note = st.sidebar.number_input("Note", 0.0, 20.0, step=0.5)
    poids = st.sidebar.number_input("Poids", 0.0, 1.0, step=0.1, value=1.0)
    if st.sidebar.button("Ajouter la note"):
        st.session_state.ue_data[ue_select]["grades"].append((note, poids))
        st.sidebar.success(f"Note {note} ajoutée à {ue_select}.")

# ---------- SECONDE CHANCE ----------
st.sidebar.markdown("---")
if st.session_state.ue_data:
    st.sidebar.header("🎯 Seconde chance")
    ue_sc = st.sidebar.selectbox("UE concernée", options=list(st.session_state.ue_data.keys()))
    sc_note = st.sidebar.number_input("Note seconde chance", 0.0, 20.0, step=0.5)
    if st.sidebar.button("Appliquer seconde chance"):
        st.session_state.ue_data[ue_sc]["seconde_chance"] = sc_note
        st.sidebar.success(f"Seconde chance {sc_note} appliquée à {ue_sc}.")

# ---------- TABLEAU DES RESULTATS ----------
st.markdown("## 📊 Résultats")
if st.session_state.ue_data:
    resultats, moyenne_generale, moyenne_min_restante, ue_modifiables = calculer_moyennes(st.session_state.ue_data)
    st.table([{"UE": ue, "Moyenne": moyenne, "Statut": statut} for ue, moyenne, statut in resultats])
    st.markdown(f"### Moyenne Générale : **{moyenne_generale:.2f}/20**")
    if moyenne_generale >= 10:
        st.success("Moyenne générale validée ✅")
    else:
        st.error("Moyenne générale insuffisante ❌")
    if moyenne_min_restante is not None:
        st.info(f"📌 Moyenne minimale requise pour valider : **{moyenne_min_restante:.2f}/20**")
    st.progress(min(1.0, moyenne_generale / 20))

    # Export CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["UE", "Moyenne", "Statut", "Seconde chance"])
    for ue, moyenne, statut in resultats:
        sc = st.session_state.ue_data[ue].get("seconde_chance", "—")
        writer.writerow([ue, moyenne, statut, sc])
    st.download_button("⬇️ Télécharger en CSV", output.getvalue().encode(), "resultats.csv", "text/csv")
else:
    st.info("Aucune UE encore ajoutée. Choisis un dataset ou ajoute tes notes manuellement.")
