import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from calculator import Calculator
from data_manager import DataManager

def ui_sidebar():
    DataManager.init_state()
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        datasets = DataManager.scanner_fichiers_locaux()
        if datasets:
            f_choisi = st.selectbox("Fichier", list(datasets.keys()))
            if f_choisi:
                d_choisi = st.selectbox("Dataset", list(datasets[f_choisi].keys()))
                if st.button("Charger"):
                    st.session_state.ue_data = DataManager.normaliser_donnees(datasets[f_choisi][d_choisi])
                    st.rerun()
        
        st.divider()
        st.download_button("💾 Export JSON", json.dumps(st.session_state.ue_data, indent=4), "notes.json")
        uploaded = st.file_uploader("📂 Import JSON", type="json")
        if uploaded:
            st.session_state.ue_data = json.load(uploaded)
            st.rerun()
            
        if st.button("🗑️ Reset", type="primary"):
            st.session_state.ue_data = {}
            st.rerun()

def ui_dashboard():
    st.header("📊 Tableau de Bord")
    if not st.session_state.ue_data:
        st.info("Ajoutez des UEs ou chargez un fichier.")
        return

    res = Calculator.compute_stats(st.session_state.ue_data)
    
    # Indicateurs
    c_main, c_det = st.columns()
    with c_main:
        delta = res['Année'] - 10
        st.metric("Moyenne Annuelle (Pessimiste)", f"{res['Année']:.2f}/20", delta=f"{delta:.2f}")
        st.metric("🎯 Moyenne Actuelle (réelle)", f"{res['Actuelle']:.2f}/20", help="Basée uniquement sur les notes reçues.")
        
        if res['Année'] >= 10:
            msg = "✅ VALIDÉ PAR COMPENSATION" if (res['S1'] < 10 or res['S2'] < 10) else "🎉 ANNÉE VALIDÉE"
            st.markdown(f'<div class="success-box"><b>{msg}</b></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="warning-box">⚠️ <b>NON VALIDÉ</b></div>', unsafe_allow_html=True)

    with c_det:
        c1, c2 = st.columns(2)
        c1.metric("Semestre 1", f"{res['S1']:.2f}")
        c2.metric("Semestre 2", f"{res['S2']:.2f}")
        
        # Jauges
        for val, title, col in [(res['S1'], "S1", "#3498db"), (res['S2'], "S2", "#9b59b6")]:
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=val, title={'text': title},
                gauge={'axis': {'range':}, 'bar': {'color': col}, 'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 10}}
            ))
            fig.update_layout(height=120, margin=dict(l=10,r=10,t=10,b=10))
            if title == "S1": c1.plotly_chart(fig, use_container_width=True) 
            else: c2.plotly_chart(fig, use_container_width=True)

    st.divider()
    
    # --- Affichage des Catégories ---
    if res.get('categories'):
        st.subheader("📚 Moyennes par Catégorie")
        cat_cols = st.columns(len(res['categories']))
        for i, (cat_name, cat_val) in enumerate(res['categories'].items()):
            cat_cols[i].metric(cat_name, f"{cat_val:.2f}/20")

    # Graphique général
    if res.get('details'):
        df = pd.DataFrame(res['details'])
        fig = px.bar(df, x="Nom", y="Moyenne", color="Catégorie", text="Moyenne", hover_data=["Semestre", "Moyenne Actuelle"])
        fig.add_hline(y=10, line_dash="dash")
        st.plotly_chart(fig, use_container_width=True)

def ui_input():
    st.header("📝 Saisie des notes")
    c_add, c_edit = st.columns()
    
    with c_add:
        st.subheader("Ajouter UE")
        with st.form("new_ue"):
            nom = st.text_input("Nom")
            cat = st.text_input("Catégorie", "Général")
            coef = st.number_input("Coef", 1.0, 30.0)
            sem = st.radio("Semestre", ["S1", "S2"], horizontal=True)
            if st.form_submit_button("Créer") and nom:
                st.session_state.ue_data[nom] = {"coef": coef, "semestre": sem, "categorie": cat, "grades": [], "sc": None}
                st.rerun()

    with c_edit:
        st.subheader("Modifier")
        if st.session_state.ue_data:
            ue = st.selectbox("Choisir UE", list(st.session_state.ue_data.keys()))
            data = st.session_state.ue_data[ue]
            
            c1, c2, c3, c4 = st.columns(4)
            data["coef"] = c1.number_input("Coef", 0.0, key="e_c", value=float(data["coef"]))
            data["semestre"] = c2.selectbox("Sem", ["S1", "S2"], index=0 if data.get("semestre")=="S1" else 1)
            data["categorie"] = c3.text_input("Catégorie", value=data.get("categorie", "Général"))
            data["sc"] = c4.number_input("Rattrapage", 0.0, 20.0, value=data.get("sc"))
            
            df = pd.DataFrame(data["grades"])
            if df.empty: df = pd.DataFrame(columns=["note", "poids"])
            edited = st.data_editor(df, num_rows="dynamic", key="editor")
            
            if st.button("💾 Sauvegarder"):
                clean = [g for g in edited.to_dict('records') if g['poids'] > 0]
                data["grades"] = clean
                st.session_state.ue_data[ue] = data
                st.toast("Sauvegardé !")
                st.rerun()

def ui_optimist():
    st.header("✨ Moyenne Optimiste (Sans 0)")
    st.info("Cette page calcule vos moyennes en ignorant totalement les notes égales à 0 (utile si le 0 est provisoire).")
    
    if not st.session_state.ue_data:
        st.warning("Ajoutez des UEs ou chargez un fichier.")
        return

    res = Calculator.compute_stats(st.session_state.ue_data)
    
    # Indicateurs
    c_main, c_det = st.columns()
    with c_main:
        st.metric("🎯 Moyenne Actuelle (sans 0)", f"{res.get('Actuelle_sans_0', 0):.2f}/20")
        
    with c_det:
        c1, c2 = st.columns(2)
        c1.metric("Semestre 1 (sans 0)", f"{res.get('S1_sans_0', 0):.2f}")
        c2.metric("Semestre 2 (sans 0)", f"{res.get('S2_sans_0', 0):.2f}")
        
        # Jauges
        for val, title, col in [(res.get('S1_sans_0', 0), "S1", "#3498db"), (res.get('S2_sans_0', 0), "S2", "#9b59b6")]:
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=val, title={'text': title},
                gauge={'axis': {'range': [0, 20]}, 'bar': {'color': col}, 'threshold': {'line': {'color': "green", 'width': 4}, 'thickness': 0.75, 'value': 10}}
            ))
            fig.update_layout(height=120, margin=dict(l=10,r=10,t=10,b=10))
            if title == "S1": c1.plotly_chart(fig, use_container_width=True) 
            else: c2.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Graphique général
    if res.get('details'):
        df = pd.DataFrame(res['details'])
        if 'Moyenne Sans 0' in df.columns:
            # Filtrer pour ne pas afficher les UEs sans notes non-nulles
            df_plot = df.dropna(subset=['Moyenne Sans 0'])
            if not df_plot.empty:
                st.subheader("📊 Détails des UEs (Moyenne > 0)")
                fig = px.bar(df_plot, x="Nom", y="Moyenne Sans 0", color="Catégorie", text="Moyenne Sans 0", hover_data=["Semestre", "Moyenne Actuelle"])
                fig.add_hline(y=10, line_dash="dash")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune note supérieure à 0 n'a été trouvée dans vos UEs.")