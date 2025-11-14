# Nouveau code refactorisé avec :
# - Fonction de calcul séparée dans un module interne
# - Visualisation des moyennes
# - Simulation "Et si...?"
# - Nettoyage et améliorations diverses

import streamlit as st
import io
import csv
import glob
import importlib.util
import pandas as pd
import plotly.express as px
from typing import Dict, Any, List, Tuple

# ---------- CONFIG ----------
st.set_page_config(page_title="Calculateur de Moyenne", layout="wide")
st.title("🎓 Calculateur de Moyenne")
st.caption("Choisis un dataset, puis les UEs et notes pour calculer ta moyenne.")

# ---------- INIT SESSION ----------
if "ue_data" not in st.session_state:
    st.session_state.ue_data: Dict[str, Dict[str, Any]] = {}


# ---------- MODULE DE CALCUL SÉPARÉ ----------
def calcul_moyennes(ue_data: Dict[str, Any]) -> Tuple[List[Tuple[str, str, str]], float, float or None]:
    resultats = []
    total_coef = 0
    somme_ponderee = 0
    score_total = 0
    poids_restants_total = 0

    for ue, data in ue_data.items():
        coef = data.get("coef", 1)
        notes = data.get("grades", [])
        sc = data.get("seconde_chance")

        score = 0
        poids_effectif = 0
        poids_restants = 0

        for note, poids in notes:
            if poids <= 0:
                continue  # sécurité
            if note is None:
                poids_restants += poids
            else:
                score += note * poids
                poids_effectif += poids

        total_poids = poids_effectif + poids_restants
        moyenne = score / total_poids if total_poids > 0 else 0

        # seconde chance
        if sc is not None:
            moyenne = max(moyenne, 0.5 * moyenne + 0.5 * sc)

        # statut
        if moyenne >= 10:
            statut = "✅ Validée"
        elif poids_restants > 0:
            manque = ((10 * total_poids) - score) / poids_restants
            manque = max(0, min(20, manque))
            statut = f"⚠ Besoin ≥ {manque:.2f}"
        else:
            statut = "❌ Non validée"

        resultats.append((ue, f"{moyenne:.2f}", statut))

        total_coef += coef
        somme_ponderee += moyenne * coef
        score_total += score * coef
        poids_restants_total += poids_restants * coef

    moyenne_generale = somme_ponderee / total_coef if total_coef > 0 else 0

    if poids_restants_total > 0:
        min_globale = (10 * total_coef - score_total) / poids_restants_total
        min_globale = max(0, min(20, min_globale))
    else:
        min_globale = None

    return resultats, moyenne_generale, min_globale


# ---------- CHARGEMENT DYNAMIQUE DES DATASETS ----------
datasets = {}
for filepath in glob.glob("ue_data_*.py"):
    spec = importlib.util.spec_from_file_location("module", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ue_vars = {k: v for k, v in vars(module).items() if k.startswith("ue_data_")}
    if ue_vars:
        datasets[filepath] = ue_vars

# ---------- SÉLECTION EN 2 ÉTAPES ----------
st.sidebar.header("📁 Chargement dataset")
if datasets:
    dataset_file = st.sidebar.selectbox("Fichier :", list(datasets.keys()))
    ue_vars = datasets[dataset_file]
    choix = st.sidebar.selectbox("Dataset :", list(ue_vars.keys()))
    if st.sidebar.button("Charger"):
        st.session_state.ue_data = ue_vars[choix]
        st.sidebar.success("Dataset chargé !")
else:
    st.sidebar.info("Aucun fichier 'ue_data_*.py' trouvé.")

# ---------- AJOUT UE ----------
st.sidebar.header("➕ Ajouter une UE")
nom_ue = st.sidebar.text_input("Nom de l'UE")
coef = st.sidebar.number_input("Coefficient", min_value=0.5, max_value=10.0, value=1.0, step=0.5)
if st.sidebar.button("Ajouter l’UE"):
    if nom_ue.strip():
        st.session_state.ue_data[nom_ue] = {"coef": coef, "grades": []}
        st.sidebar.success("UE ajoutée !")
    else:
        st.sidebar.warning("Nom invalide.")

# ---------- AJOUT NOTE ----------
st.sidebar.header("🧮 Ajouter une note")
if st.session_state.ue_data:
    ue_sel = st.sidebar.selectbox("UE :", list(st.session_state.ue_data.keys()))
    note = st.sidebar.number_input("Note", min_value=0.0, max_value=20.0, step=0.5)
    poids = st.sidebar.number_input("Poids (0-1)", min_value=0.0, max_value=1.0, value=1.0, step=0.1)
    if st.sidebar.button("Ajouter la note"):
        st.session_state.ue_data[ue_sel]["grades"].append((note, poids))
        st.sidebar.success("Note ajoutée !")

# ---------- SECONDE CHANCE ----------
st.sidebar.header("🎯 Seconde chance")
if st.session_state.ue_data:
    ue_sc = st.sidebar.selectbox("UE :", list(st.session_state.ue_data.keys()), key="sec")
    sc_note = st.sidebar.number_input("Note seconde chance", 0.0, 20.0, step=0.5)
    if st.sidebar.button("Appliquer"):
        st.session_state.ue_data[ue_sc]["seconde_chance"] = sc_note
        st.sidebar.success("Seconde chance appliquée !")

# ---------- CALCUL PRINCIPAL ----------
st.markdown("## 📊 Résultats")
if st.session_state.ue_data:
    resultats, moyenne_generale, min_restante = calcul_moyennes(st.session_state.ue_data)

    df = pd.DataFrame(resultats, columns=["UE", "Moyenne", "Statut"])
    st.dataframe(df, use_container_width=True)

    st.subheader(f"Moyenne Générale : {moyenne_generale:.2f}/20")
    st.progress(min(1.0, moyenne_generale / 20))

    if min_restante is not None:
        st.info(f"📌 Moyenne minimale restante pour valider : **{min_restante:.2f}/20**")

    # ---------- GRAPHIQUE ----------
    fig = px.bar(df, x="UE", y="Moyenne", title="Moyenne par UE")
    st.plotly_chart(fig, use_container_width=True)

# ---------- SIMULATION / PRÉDICTION AMÉLIORÉE ----------
st.markdown("### 🔮 Prédiction améliorée : calculer la note nécessaire ou simuler une note")

ue_sim = st.selectbox("UE à considérer", df["UE"].tolist())
mode_pred = st.radio("Type de prédiction", [
    "Simuler une note", 
    "Calculer la note nécessaire pour valider l'UE", 
    "Calculer la note nécessaire pour atteindre une moyenne générale cible"
], index=0)

if mode_pred == "Simuler une note":
    new_note = st.slider("Note simulée", 0.0, 20.0, 10.0, 0.5)
    ue_data_sim = {k: {'coef': v['coef'], 'grades': v['grades'][:], 'seconde_chance': v.get('seconde_chance')} for k, v in st.session_state.ue_data.items()}
    ue_data_sim[ue_sim]['grades'].append((new_note, 1.0))
    _, moyenne_proj, _ = calcul_moyennes(ue_data_sim)
    st.info(f"Avec cette note simulée, la moyenne générale serait **{moyenne_proj:.2f}/20**.")

elif mode_pred == "Calculer la note nécessaire pour valider l'UE":
    ue_obj = st.session_state.ue_data[ue_sim]
    score = sum(n * p for n, p in ue_obj['grades'] if n is not None)
    poids_deja = sum(p for n, p in ue_obj['grades'] if n is not None)
    poids_restants = 1.0 - poids_deja
    if poids_restants <= 0:
        st.warning("Cette UE n'a plus de place pour ajouter une note.")
    else:
        note_min = (10 - (score / (poids_deja + poids_restants))) / poids_restants
        note_min = max(0, min(20, note_min))
        st.info(f"Pour valider **{ue_sim}**, tu dois obtenir **au moins {note_min:.2f}/20** sur la prochaine évaluation.")

elif mode_pred == "Calculer la note nécessaire pour atteindre une moyenne générale cible":
    cible = st.slider("Objectif de moyenne générale", 10.0, 20.0, 12.0, 0.5)
    total_coef = sum(v['coef'] for v in st.session_state.ue_data.values())
    points_cibles = cible * total_coef
    points_actuels = 0
    poids_restants_total = 0
    for ue, data in st.session_state.ue_data.items():
        coef = data['coef']
        notes = data['grades']
        score = sum(n * p for n, p in notes if n is not None)
        poids_deja = sum(p for n, p in notes if n is not None)
        poids_restants = max(0, 1.0 - poids_deja)
        points_actuels += score * coef
        poids_restants_total += poids_restants * coef
    if poids_restants_total <= 0:
        st.warning("Impossible : aucun poids disponible pour augmenter la moyenne.")
    else:
        note_min_globale = (points_cibles - points_actuels) / poids_restants_total
        note_min_globale = max(0, min(20, note_min_globale))
        st.info(f"Pour atteindre **{cible}/20**, il te faut obtenir en moyenne **{note_min_globale:.2f}/20** sur les évaluations restantes.")

    # ---------- EXPORT CSV ----------
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["UE", "Moyenne", "Statut"])
    for ue, moy, statut in resultats:
        writer.writerow([ue, moy, statut])

    st.download_button("⬇️ Télécharger CSV", output.getvalue(), "resultats.csv", "text/csv")
else:
    st.info("Ajoute ou charge d'abord une UE.")
