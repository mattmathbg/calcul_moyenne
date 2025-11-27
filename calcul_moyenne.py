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
    page_title="GradeMaster Pro + Git",
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
    V1: grades = [(10, 1.0)]
    V2: grades = [{'note': 10, 'poids': 1.0}]
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
            if isinstance(g, (list, tuple)) and len(g) >= 2:
                # Conversion Tuple -> Dict
                nouvelle_ue["grades"].append({"note": g[0], "poids": g[1]})
            elif isinstance(g, dict):
                # Déjà au bon format
                nouvelle_ue["grades"].append(g)
                
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
    """Calcule toutes les stats pour le dashboard"""
    resultats_detail = []
    total_points = 0
    total_coef = 0
    ue_validees = 0
    ue_total = 0

    for nom, details in data.items():
        coef = details.get("coef", 1.0)
        grades = details.get("grades", [])
        sc = details.get("sc", None)

        numerateur = sum(g["note"] * g["poids"] for g in grades if g["note"] is not None)
        denominateur = sum(g["poids"] for g in grades if g["note"] is not None)
        
        moyenne = numerateur / denominateur if denominateur > 0 else 0.0

        if sc is not None:
            moyenne = max(moyenne, (moyenne + sc) / 2)

        statut = "✅" if moyenne >= 10 else "❌"
        if moyenne >= 10: ue_validees += 1
        ue_total += 1

        total_points += moyenne * coef
        total_coef += coef

        resultats_detail.append({
            "UE": nom,
            "Coef": coef,
            "Moyenne": round(moyenne, 2),
            "Statut": statut
        })

    moyenne_gen = total_points / total_coef if total_coef > 0 else 0.0
    return resultats_detail, moyenne_gen, ue_validees, ue_total

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
                # On convertit les données pour qu'elles matchent le format V2
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
st.title("🎓 GradeMaster Pro")

# Création des onglets
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "📝 Saisie & UEs", "🔮 Simulation", "📋 Détails Raw"])

# === TAB 1: DASHBOARD ===
with tab1:
    details, moy_gen, valides, total_ues = calcul_metriques(st.session_state.ue_data)
    
    if not st.session_state.ue_data:
        st.info("👈 Utilisez le menu à gauche pour charger un fichier 'ue_data_*.py' ou commencez manuellement.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Moyenne Générale", f"{moy_gen:.2f}/20", delta=f"{moy_gen-10:.2f} vs val.")
        col2.metric("UE Validées", f"{valides}/{total_ues}")
        col3.metric("Crédits", sum(d['Coef'] for d in details))

        c1, c2 = st.columns([1, 2])
        with c1:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = moy_gen, title = {'text': "Moyenne"},
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
                fig_bar = px.bar(df_res, x="UE", y="Moyenne", text="Moyenne", title="Résultats par UE")
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
        if st.button("Créer"):
            if new_ue_name:
                st.session_state.ue_data[new_ue_name] = {"coef": new_ue_coef, "grades": [], "sc": None}
                st.rerun()

    with c_edit:
        st.subheader("✏️ Modifier les notes")
        if st.session_state.ue_data:
            ue_select = st.selectbox("UE à modifier", list(st.session_state.ue_data.keys()))
            curr_data = st.session_state.ue_data[ue_select]
            
            # DataFrame pour l'éditeur
            df_grades = pd.DataFrame(curr_data["grades"])
            if df_grades.empty: df_grades = pd.DataFrame(columns=["note", "poids"])

            edited_df = st.data_editor(
                df_grades, num_rows="dynamic",
                column_config={
                    "note": st.column_config.NumberColumn("Note", min_value=0, max_value=20, step=0.5),
                    "poids": st.column_config.NumberColumn("Poids (0-1)", min_value=0, max_value=1, step=0.1)
                }, key=f"ed_{ue_select}"
            )

            if st.button("💾 Sauvegarder notes"):
                clean = [g for g in edited_df.to_dict('records') if not pd.isna(g['note'])]
                st.session_state.ue_data[ue_select]["grades"] = clean
                st.toast("Sauvegardé !", icon="✅")
                st.rerun()

# === TAB 3: SIMULATION ===
with tab3:
    st.subheader("🔮 Simulation")
    if st.session_state.ue_data:
        sim_ue = st.selectbox("UE cible", list(st.session_state.ue_data.keys()))
        
        # Copie profonde pour simuler
        data_sim = json.loads(json.dumps(st.session_state.ue_data))
        
        c1, c2 = st.columns(2)
        with c1:
            note_sim = st.slider("Note imaginée", 0.0, 20.0, 10.0)
            poids_sim = st.slider("Poids", 0.1, 1.0, 0.5)
        
        with c2:
            data_sim[sim_ue]['grades'].append({"note": note_sim, "poids": poids_sim})
            _, sim_moy, _, _ = calcul_metriques(data_sim)
            delta = sim_moy - moy_gen
            st.metric("Nouvelle Moyenne", f"{sim_moy:.2f}", delta=f"{delta:+.2f}")

# === TAB 4: RAW ===
with tab4:
    if details: st.dataframe(pd.DataFrame(details), use_container_width=True)