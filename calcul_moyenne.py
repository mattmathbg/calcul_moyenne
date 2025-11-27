import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import io
import glob
import importlib.util
import os

# ---------- CONFIGURATION PAGE ----------
st.set_page_config(
    page_title="GradeMaster Pro + Git (V2.2)",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- CSS PERSONNALISÉ ----------
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #ff4b4b, #ffa425, #2ecc71);
    }
    </style>
""", unsafe_allow_html=True)

# ---------- GESTION DE L'ÉTAT (SESSION) ----------
if "ue_data" not in st.session_state:
    st.session_state.ue_data = {}

# ---------- FONCTIONS UTILITAIRES ----------

def normaliser_donnees(data_raw):
    """
    Convertit les données brutes (format V1 avec tuples) vers le format V2 (avec dicts)
    et assure que toutes les notes non remplies sont None.
    """
    data_propre = {}
    for ue, details in data_raw.items():
        # Copie de sécurité
        nouvelle_ue = {
            "coef": details.get("coef", 1.0),
            "sc": details.get("seconde_chance", details.get("sc", None)),
            "grades": []
        }
        
        # Conversion des notes
        raw_grades = details.get("grades", [])
        for g in raw_grades:
            note = None
            poids = None
            
            if isinstance(g, (list, tuple)) and len(g) >= 2:
                # V1: Tuple (note, poids)
                note = g[0]
                poids = g[1]
            elif isinstance(g, dict):
                # V2: Dict {'note': x, 'poids': y}
                note = g.get("note")
                poids = g.get("poids")
                
            # Assure que la note est None si elle n'est pas un nombre
            if note == '': note = None 
            if isinstance(note, str) and not note.replace('.', '', 1).isdigit():
                note = None
            
            nouvelle_ue["grades"].append({"note": note, "poids": poids})
                
        data_propre[ue] = nouvelle_ue
    return data_propre

def scanner_fichiers_locaux():
    """Scanne le dossier pour trouver les fichiers ue_data_*.py"""
    datasets = {}
    fichiers = glob.glob("ue_data_*.py")
    
    for filepath in fichiers:
        nom_fichier = os.path.basename(filepath)
        try:
            spec = importlib.util.spec_from_file_location("module", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Récupère toutes les variables commençant par ue_data_
            vars_module = {k: v for k, v in vars(module).items() if k.startswith("ue_data_")}
            if vars_module:
                datasets[nom_fichier] = vars_module
        except Exception as e:
            print(f"Erreur chargement {filepath}: {e}")
            
    return datasets

def reset_app():
    st.session_state.ue_data = {}
    st.toast("Application réinitialisée !", icon="🗑️")

def calcul_metriques(data):
    """
    Calcule toutes les stats pour le dashboard, y compris la moyenne pessimiste.
    """
    resultats_detail = []
    total_points_actuel = 0.0
    total_coef_actuel = 0.0 # Coef des UEs avec au moins une note reçue
    total_points_pessimiste = 0.0
    total_coef_pessimiste = 0.0 # Coef de toutes les UEs définies
    ue_validees = 0
    ue_total = 0

    for nom, details in data.items():
        coef = details.get("coef", 1.0)
        grades = details.get("grades", [])
        sc = details.get("sc", None)

        # 1. Calcul de la Moyenne Actuelle (uniquement les notes reçues)
        num_actuel = sum(g["note"] * g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
        den_actuel = sum(g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
        
        moyenne_ue_actuelle = num_actuel / den_actuel if den_actuel > 0 else 0.0

        # 2. Calcul de la Moyenne Pessimiste (notes reçues + 0 pour les manquantes)
        num_pessimiste = 0.0
        den_pessimiste = sum(g["poids"] for g in grades if g.get("poids") is not None)
        
        for g in grades:
            note = g.get("note")
            poids = g.get("poids")
            if poids is not None and poids > 0:
                if note is not None:
                    # Grade reçu
                    num_pessimiste += note * poids
                # Si note est None, on assume 0/20, donc 0 * poids.
        
        moyenne_ue_pessimiste = num_pessimiste / den_pessimiste if den_pessimiste > 0 else 0.0
        
        # --- Application de la Seconde Chance (SC) ---
        moyenne_ue_actuelle_sc = moyenne_ue_actuelle
        moyenne_ue_pessimiste_sc = moyenne_ue_pessimiste
        
        if sc is not None:
            moyenne_ue_actuelle_sc = max(moyenne_ue_actuelle, (moyenne_ue_actuelle + sc) / 2)
            moyenne_ue_pessimiste_sc = max(moyenne_ue_pessimiste, (moyenne_ue_pessimiste + sc) / 2)

        # --- Mise à Jour des Totaux Globaux ---

        # 1. Total Actuel (pour l'affichage de la moyenne Actuelle et le tableau de détails)
        if den_actuel > 0:
            total_points_actuel += moyenne_ue_actuelle_sc * coef
            total_coef_actuel += coef

            statut = "✅" if moyenne_ue_actuelle_sc >= 10 else "❌"
            if moyenne_ue_actuelle_sc >= 10: ue_validees += 1
            ue_total += 1 # Compte les UEs avec au moins une note

            resultats_detail.append({
                "UE": nom,
                "Coef": coef,
                "Moyenne": round(moyenne_ue_actuelle_sc, 2), # Affiche la moyenne actuelle dans le tableau
                "Statut": statut
            })
        elif den_pessimiste > 0:
            # Si aucune note reçue, mais des notes prévues, on compte l'UE
            ue_total += 1

        # 2. Total Pessimiste (pour l'affichage de la moyenne Pessimiste)
        if den_pessimiste > 0:
            total_points_pessimiste += moyenne_ue_pessimiste_sc * coef
            total_coef_pessimiste += coef
        
    # --- Moyennes Générales Finales ---
    moyenne_gen_actuelle = total_points_actuel / total_coef_actuel if total_coef_actuel > 0 else 0.0
    moyenne_gen_pessimiste = total_points_pessimiste / total_coef_pessimiste if total_coef_pessimiste > 0 else 0.0

    return resultats_detail, moyenne_gen_actuelle, moyenne_gen_pessimiste, ue_validees, ue_total, total_coef_pessimiste
# ---------- SIDEBAR (MENU) ----------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # --- SECTION GIT / FICHIERS LOCAUX ---
    st.subheader("📂 Fichiers locaux (Git)")
    datasets_locaux = scanner_fichiers_locaux()
    
    if datasets_locaux:
        fichier_choisi = st.selectbox("1. Fichier :", list(datasets_locaux.keys()))
        if fichier_choisi:
            vars_dispo = datasets_locaux[fichier_choisi]
            dataset_choisi = st.selectbox("2. Dataset :", list(vars_dispo.keys()))
            
            if st.button("Charger ce dataset"):
                raw_data = vars_dispo[dataset_choisi]
                # Conversion des données pour qu'elles matchent le format V2
                st.session_state.ue_data = normaliser_donnees(raw_data)
                st.toast(f"Dataset '{dataset_choisi}' chargé !", icon="🚀")
                st.rerun()
    else:
        st.caption("Aucun fichier 'ue_data_*.py' trouvé dans le dossier.")

    st.divider()

    # --- SECTION JSON ---
    with st.expander("💾 Sauvegarde JSON"):
        st.download_button("Export JSON", json.dumps(st.session_state.ue_data, indent=4), "notes.json")
        f = st.file_uploader("Import JSON", type="json")
        if f: 
            st.session_state.ue_data = json.load(f)
            st.rerun()
        if st.button("Tout effacer", type="primary"): reset_app()

# ---------- INTERFACE PRINCIPALE ----------
st.title("🎓 GradeMaster Pro (V2.2)")

# Création des onglets
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "📝 Saisie & UEs", "🔮 Simulation", "📋 Détails Raw"])

# === TAB 1: DASHBOARD ===
with tab1:
    details, moy_actuelle, moy_pessimiste, valides, total_ues, total_coef_pessimiste = calcul_metriques(st.session_state.ue_data)    
    if not st.session_state.ue_data:
        st.info("👈 Utilisez le menu à gauche pour charger un fichier 'ue_data_*.py' ou commencez manuellement.")
    else:
        # Affichage des deux moyennes et des métriques
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Moyenne Actuelle", f"{moy_actuelle:.2f}/20", 
                    delta=f"{moy_actuelle-10:.2f} vs val. (Notes reçues)", 
                    delta_color="normal" if moy_actuelle >= 10 else "inverse")
        col2.metric("Moyenne Pessimiste", f"{moy_pessimiste:.2f}/20", 
                    delta=f"{moy_pessimiste-10:.2f} vs val. (Notes manquantes à 0)", 
                    delta_color="normal" if moy_pessimiste >= 10 else "inverse")
        col3.metric("UE Validées", f"{valides}/{total_ues}")
        col4.metric("Coefficients Totaux", total_coef_pessimiste) # Utilise le coefficient total de toutes les UEs

        c1, c2 = st.columns([1, 2])
        with c1:
            # Jauge basée sur la moyenne actuelle
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = moy_actuelle, title = {'text': "Moyenne Actuelle"},
                gauge = {'axis': {'range': [0, 20]}, 
                         'bar': {'color': "#2b86d9"},
                         'steps': [{'range': [0, 10], 'color': "#ffe0e0"}, {'range': [10, 20], 'color': "#e0ffe0"}],
                         'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 10}}
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with c2:
            if details:
                df_res = pd.DataFrame(details)
                df_res['Color'] = df_res['Moyenne'].apply(lambda x: '#2ecc71' if x >= 10 else '#e74c3c')
                fig_bar = px.bar(df_res, x="UE", y="Moyenne", text="Moyenne", title="Résultats par UE (Notes Reçues)")
                fig_bar.update_traces(marker_color=df_res['Color'], textposition='outside')
                fig_bar.add_hline(y=10, line_dash="dash", line_color="black")
                st.plotly_chart(fig_bar, use_container_width=True)

# === TAB 2: SAISIE ===
with tab2:
    c_add, c_edit = st.columns([1, 2])
    with c_add:
        st.subheader("➕ Ajouter une UE")
        new_ue_name = st.text_input("Nom UE")
        new_ue_coef = st.number_input("Coef", 1.0, 20.0, step=0.5)
        # Ajout de l'option de Seconde Chance
        new_ue_sc = st.number_input("Note Seconde Chance (Optionnel)", 0.0, 20.0, None, step=0.5)
        if st.button("Créer"):
            if new_ue_name:
                st.session_state.ue_data[new_ue_name] = {"coef": new_ue_coef, "grades": [], "sc": new_ue_sc}
                st.rerun()

    with c_edit:
        st.subheader("✏️ Modifier les notes")
        if st.session_state.ue_data:
            ue_select = st.selectbox("UE à modifier", list(st.session_state.ue_data.keys()))
            curr_data = st.session_state.ue_data[ue_select]
            
            # Modifier le coefficient et la SC de l'UE
            # CORRECTION APPLIQUÉE : Assurer que la valeur (value) est toujours un float.
            curr_data["coef"] = st.number_input(
                "Coefficient de l'UE", 
                min_value=1.0, 
                max_value=20.0, 
                value=float(curr_data.get("coef", 1.0)), # <- Convertir la valeur par défaut en float
                key=f"coef_{ue_select}"
            )
            # st.number_input pour la SC est correcte car vous utilisez `None` si vide.
            curr_data["sc"] = st.number_input("Note Seconde Chance", 0.0, 20.0, curr_data.get("sc"), key=f"sc_{ue_select}", help="Laissez vide pour désactiver.")
            
            # DataFrame pour l'éditeur
            df_grades = pd.DataFrame(curr_data["grades"])
            if df_grades.empty: df_grades = pd.DataFrame(columns=["note", "poids"])

            edited_df = st.data_editor(
                df_grades, num_rows="dynamic",
                column_config={
                    "note": st.column_config.NumberColumn("Note (laissez vide si non reçue)", min_value=0.0, max_value=20.0, step=0.5),
                    "poids": st.column_config.NumberColumn("Poids", min_value=0.0, max_value=1.0, step=0.1, help="Doit être 1.0 au total par UE.")
                }, key=f"ed_{ue_select}"
            )

            if st.button("💾 Sauvegarder notes & paramètres UE"):
                # Nettoyage des données
                clean = [g for g in edited_df.to_dict('records') if g.get('poids') is not None and g.get('poids') > 0]
                
                # Assurer que les notes sont None si elles sont vides/non numériques
                for item in clean:
                    if not isinstance(item['note'], (int, float)):
                        item['note'] = None
                        
                st.session_state.ue_data[ue_select]["grades"] = clean
                st.toast("Sauvegardé !", icon="✅")
                st.rerun()

# === TAB 3: SIMULATION ===
with tab3:
    st.subheader("🔮 Simulation")
    if st.session_state.ue_data:
        # Affichage des résultats basés sur la moyenne actuelle pour référence
        st.metric("Moyenne Actuelle de Référence", f"{moy_actuelle:.2f}/20")
        st.markdown("---")

        sim_ue = st.selectbox("UE cible", list(st.session_state.ue_data.keys()))
        
        # Copie profonde pour simuler
        data_sim = json.loads(json.dumps(st.session_state.ue_data))
        
        c1, c2 = st.columns(2)
        with c1:
            note_sim = st.slider("Note imaginée", 0.0, 20.0, 10.0)
            poids_sim = st.slider("Poids", 0.1, 1.0, 0.5)
        
        with c2:
            # Ajoute la note de simulation à la liste des grades
            data_sim[sim_ue]['grades'].append({"note": note_sim, "poids": poids_sim})
            
            # Recalcul des métriques avec la note simulée
            _, sim_moy_actuelle, sim_moy_pessimiste, _, _ = calcul_metriques(data_sim)
            
            st.metric("Nouvelle Moyenne Actuelle", f"{sim_moy_actuelle:.2f}", 
                      delta=f"{sim_moy_actuelle - moy_actuelle:+.2f}")
            
            st.metric("Nouvelle Moyenne Pessimiste", f"{sim_moy_pessimiste:.2f}", 
                      delta=f"{sim_moy_pessimiste - moy_pessimiste:+.2f}")

# === TAB 4: RAW ===
with tab4:
    st.subheader("Détails des UEs (Moyenne Actuelle)")
    if details: st.dataframe(pd.DataFrame(details), use_container_width=True)
    st.subheader("Données JSON Brutes de Session")
    st.json(st.session_state.ue_data)