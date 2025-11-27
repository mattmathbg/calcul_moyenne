import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import io

# ---------- CONFIGURATION PAGE ----------
st.set_page_config(
    page_title="GradeMaster Pro",
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
    # Structure: { "NomUE": {"coef": float, "grades": [{"note": float, "poids": float}], "sc": float} }
    st.session_state.ue_data = {}

# ---------- FONCTIONS UTILITAIRES ----------

def reset_app():
    st.session_state.ue_data = {}
    st.toast("Application réinitialisée !", icon="🗑️")

def export_json():
    return json.dumps(st.session_state.ue_data, indent=4)

def load_json(uploaded_file):
    try:
        data = json.load(uploaded_file)
        st.session_state.ue_data = data
        st.toast("Données chargées avec succès !", icon="✅")
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")

def calcul_metriques(data):
    """Calcule toutes les stats nécessaires pour le dashboard"""
    resultats_detail = []
    total_points = 0
    total_coef = 0
    ue_validees = 0
    ue_total = 0

    for nom, details in data.items():
        coef = details.get("coef", 1.0)
        grades = details.get("grades", [])
        sc = details.get("sc", None)

        # Calcul moyenne brute de l'UE
        numerateur = sum(g["note"] * g["poids"] for g in grades)
        denominateur = sum(g["poids"] for g in grades)
        
        moyenne = numerateur / denominateur if denominateur > 0 else 0.0

        # Application Seconde Chance
        if sc is not None:
            moyenne = max(moyenne, (moyenne + sc) / 2) # Exemple de règle (moyenne des deux)
            # Note: Adapte la règle sc selon ton université (ex: max(moyenne, sc))

        statut = "✅" if moyenne >= 10 else "❌"
        if moyenne >= 10: ue_validees += 1
        ue_total += 1

        total_points += moyenne * coef
        total_coef += coef

        resultats_detail.append({
            "UE": nom,
            "Coef": coef,
            "Moyenne": round(moyenne, 2),
            "Statut": statut,
            "Progression": min(1.0, denominateur) # Suppose que total poids attendu est 1.0
        })

    moyenne_gen = total_points / total_coef if total_coef > 0 else 0.0
    return resultats_detail, moyenne_gen, ue_validees, ue_total

# ---------- SIDEBAR (MENU) ----------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Import / Export
    with st.expander("💾 Sauvegarde & Chargement"):
        st.download_button("Télécharger mes données (JSON)", export_json(), "mes_notes.json", "application/json")
        f = st.file_uploader("Charger un fichier", type="json")
        if f: load_json(f)
        if st.button("Tout effacer", type="primary"): reset_app()
    
    st.divider()
    st.info("💡 Astuce : Passez par l'onglet 'Saisie' pour ajouter vos notes rapidement.")

# ---------- INTERFACE PRINCIPALE ----------
st.title("🎓 GradeMaster Pro")
st.markdown("Suivez vos résultats, simulez vos examens et validez votre année.")

# Création des onglets
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "📝 Saisie & UEs", "🔮 Simulation", "📋 Détails Raw"])

# === TAB 1: TABLEAU DE BORD ===
with tab1:
    details, moy_gen, valides, total_ues = calcul_metriques(st.session_state.ue_data)
    
    if not st.session_state.ue_data:
        st.warning("Aucune donnée. Commencez par ajouter des UEs dans l'onglet 'Saisie' !")
    else:
        # KPI Row
        col1, col2, col3 = st.columns(3)
        col1.metric("Moyenne Générale", f"{moy_gen:.2f}/20", delta=f"{moy_gen-10:.2f} vs validation")
        col2.metric("UE Validées", f"{valides}/{total_ues}")
        col3.metric("Crédits (Coefs)", sum(d['Coef'] for d in details))

        # Graphiques
        c1, c2 = st.columns([1, 2])
        
        with c1:
            # Jauge
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = moy_gen,
                title = {'text': "Performance"},
                gauge = {
                    'axis': {'range': [0, 20]},
                    'bar': {'color': "darkblue"},
                    'steps' : [
                        {'range': [0, 10], 'color': "#ffe0e0"},
                        {'range': [10, 12], 'color': "#fff4e0"},
                        {'range': [12, 20], 'color': "#e0ffe0"}],
                    'threshold' : {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 10}
                }
            ))
            fig_gauge.update_layout(height=300, margin=dict(l=20,r=20,t=50,b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with c2:
            # Bar Chart coloré
            if details:
                df_res = pd.DataFrame(details)
                df_res['Color'] = df_res['Moyenne'].apply(lambda x: '#2ecc71' if x >= 10 else '#e74c3c')
                
                fig_bar = px.bar(
                    df_res, x="UE", y="Moyenne", 
                    text="Moyenne",
                    title="Résultats par Unité d'Enseignement"
                )
                fig_bar.update_traces(marker_color=df_res['Color'], textposition='outside')
                fig_bar.add_hline(y=10, line_dash="dash", line_color="black", annotation_text="Validation")
                fig_bar.update_layout(yaxis_range=[0, 22])
                st.plotly_chart(fig_bar, use_container_width=True)

# === TAB 2: SAISIE & UEs ===
with tab2:
    c_add, c_edit = st.columns([1, 2])
    
    with c_add:
        st.subheader("➕ Nouvelle UE")
        new_ue_name = st.text_input("Nom de l'UE (ex: Mathématiques)")
        new_ue_coef = st.number_input("Coefficient", 1.0, 20.0, step=0.5)
        if st.button("Créer l'UE"):
            if new_ue_name and new_ue_name not in st.session_state.ue_data:
                st.session_state.ue_data[new_ue_name] = {"coef": new_ue_coef, "grades": [], "sc": None}
                st.success(f"UE '{new_ue_name}' ajoutée !")
                st.rerun()
            elif new_ue_name in st.session_state.ue_data:
                st.error("Cette UE existe déjà.")

    with c_edit:
        st.subheader("✏️ Gestion des Notes")
        if st.session_state.ue_data:
            ue_select = st.selectbox("Choisir l'UE à modifier", list(st.session_state.ue_data.keys()))
            
            # Récupération des données pour l'éditeur
            current_grades = st.session_state.ue_data[ue_select]["grades"]
            df_grades = pd.DataFrame(current_grades)
            
            if df_grades.empty:
                df_grades = pd.DataFrame(columns=["note", "poids"])

            st.caption("Ajoutez ou modifiez les lignes ci-dessous. Poids total recommandé = 1.0")
            edited_df = st.data_editor(
                df_grades, 
                num_rows="dynamic", 
                column_config={
                    "note": st.column_config.NumberColumn("Note /20", min_value=0, max_value=20, step=0.5),
                    "poids": st.column_config.NumberColumn("Poids (0 à 1)", min_value=0, max_value=1, step=0.1)
                },
                key=f"editor_{ue_select}"
            )

            # Bouton de sauvegarde explicite pour confirmer les changements complexes
            if st.button("💾 Enregistrer les notes pour " + ue_select):
                # Conversion du DF en liste de dicts
                new_grades = edited_df.to_dict('records')
                # Nettoyage (suppression des lignes vides si nécessaire)
                clean_grades = [g for g in new_grades if not pd.isna(g['note'])]
                st.session_state.ue_data[ue_select]["grades"] = clean_grades
                st.toast("Notes mises à jour !", icon="💾")
                st.rerun()

            # Gestion coef et seconde chance
            with st.expander("Options avancées UE"):
                new_coef = st.number_input("Modifier Coefficient", value=st.session_state.ue_data[ue_select]['coef'])
                sc_val = st.number_input("Note Seconde Chance (laisser 0 si aucune)", 
                                       value=st.session_state.ue_data[ue_select].get('sc') or 0.0)
                
                if st.button("Mettre à jour paramètres"):
                    st.session_state.ue_data[ue_select]['coef'] = new_coef
                    st.session_state.ue_data[ue_select]['sc'] = sc_val if sc_val > 0 else None
                    st.rerun()
                
                if st.button("🗑️ Supprimer cette UE", type="primary"):
                    del st.session_state.ue_data[ue_select]
                    st.rerun()

        else:
            st.info("Créez une UE à gauche pour commencer.")

# === TAB 3: SIMULATION ===
with tab3:
    st.subheader("🔮 Simulateur 'Et si...?'")
    if not st.session_state.ue_data:
        st.warning("Il faut des données pour simuler.")
    else:
        st.markdown("Simulez une note dans une UE pour voir l'impact sur votre moyenne générale.")
        
        sim_ue = st.selectbox("UE à simuler", list(st.session_state.ue_data.keys()), key="sim_select")
        
        # Calcul actuel
        data_copy = json.loads(json.dumps(st.session_state.ue_data)) # Deep copy
        current_grades = data_copy[sim_ue]['grades']
        poids_actuel = sum(g['poids'] for g in current_grades)
        poids_restant = max(0.0, 1.0 - poids_actuel)
        
        col_sim1, col_sim2 = st.columns(2)
        
        with col_sim1:
            st.write(f"Poids notes actuelles : **{poids_actuel:.2f}**")
            st.write(f"Poids restant théorique : **{poids_restant:.2f}**")
            
            sim_note = st.slider("Note hypothétique", 0.0, 20.0, 10.0, 0.5)
            sim_poids = st.slider("Poids de cette note", 0.1, 1.0, min(0.5, poids_restant) if poids_restant > 0 else 0.5)
        
        with col_sim2:
            # Ajout temporaire pour calcul
            data_copy[sim_ue]['grades'].append({"note": sim_note, "poids": sim_poids})
            _, sim_moy_gen, _, _ = calcul_metriques(data_copy)
            
            delta = sim_moy_gen - moy_gen
            st.metric("Nouvelle Moyenne Générale", f"{sim_moy_gen:.2f}", delta=f"{delta:+.2f}")
            
            if sim_moy_gen >= 10 and moy_gen < 10:
                st.balloons()
                st.success("🎉 Cette note vous permettrait de valider l'année !")

# === TAB 4: RAW DATA ===
with tab4:
    st.markdown("### Vue tabulaire complète")
    if details:
        st.dataframe(pd.DataFrame(details), use_container_width=True)