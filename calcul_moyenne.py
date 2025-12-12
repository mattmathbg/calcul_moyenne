import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import glob
import importlib.util
from supabase import create_client, Client

# ---------- CONFIGURATION PAGE ----------
st.set_page_config(page_title="Calculateur de Moyenne 🎓", layout="wide")

# ---------- CONNEXION SUPABASE (HTTP API) ----------
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error("Erreur de configuration Supabase. Vérifiez votre fichier .streamlit/secrets.toml")
        return None

supabase = init_connection()

def get_user_from_db(username, password):
    """Récupère l'utilisateur via l'API Supabase"""
    if not supabase: return None
    try:
        response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        
        if response.data and len(response.data) > 0:
            user_row = response.data[0]
            # Sécurité : Si le champ est null, on renvoie un dict vide
            user_data_raw = user_row.get("ue_data") or {}
            
            if isinstance(user_data_raw, str):
                try:
                    return json.loads(user_data_raw)
                except:
                    return {}
            return user_data_raw if isinstance(user_data_raw, dict) else {}
        return None
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return None

def save_user_data(username, password, data):
    """Sauvegarde via l'API (Upsert)"""
    if not supabase: return
    try:
        user_entry = {
            "username": username,
            "password": password,
            "ue_data": data 
        }
        supabase.table("users").upsert(user_entry).execute()
        # On ne met pas de st.success ici pour ne pas spammer l'interface, 
        # on gère les notifications dans l'UI
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")

# ---------- GESTION LOGIN (SESSION) ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.password = ""
    st.session_state.ue_data = {}

def login_page():
    st.markdown("## 🔐 Connexion Étudiant")
    st.info("Utilisez les identifiants Supabase configurés.")
    
    with st.form("login"):
        user = st.text_input("Identifiant")
        pwd = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Entrer")
        
    if submit:
        with st.spinner("Connexion en cours..."):
            user_data = get_user_from_db(user, pwd)
            
        if user_data is not None:
            st.session_state.logged_in = True
            st.session_state.username = user
            st.session_state.password = pwd
            st.session_state.ue_data = user_data
            st.success("Connexion réussie !")
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect.")

if not st.session_state.logged_in:
    login_page()
    st.stop()

with st.sidebar:
    st.write(f"👤 Connecté : **{st.session_state.username}**")
    if st.button("Déconnexion"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.password = ""
        st.session_state.ue_data = {}
        st.rerun()
    st.divider()

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

# ---------- FONCTIONS UTILITAIRES ----------

def normaliser_donnees(data_raw):
    """Nettoie et standardise les données."""
    if not data_raw: return {}
    data_propre = {}
    for ue, details in data_raw.items():
        nouvelle_ue = {
            "coef": float(details.get("coef", 1.0)),
            "sc": details.get("seconde_chance", details.get("sc", None)),
            "grades": []
        }
        
        raw_grades = details.get("grades", [])
        for g in raw_grades:
            note = None
            poids = None
            
            if isinstance(g, (list, tuple)) and len(g) >= 2:
                note, poids = g[0], g[1]
            elif isinstance(g, dict):
                note, poids = g.get("note"), g.get("poids")
                
            if note == '': note = None 
            # Check plus robuste pour les nombres (gère les floats)
            if isinstance(note, str):
                try:
                    note = float(note)
                except ValueError:
                    note = None
            
            nouvelle_ue["grades"].append({"note": note, "poids": poids})
                
        data_propre[ue] = nouvelle_ue
    return data_propre

def scanner_fichiers_locaux():
    """Scanne le dossier pour trouver les fichiers ue_data_*.py"""
    datasets = {}
    # Utilisation de glob qui nécessite l'import os et glob
    fichiers = glob.glob("ue_data_*.py")
    
    for filepath in fichiers:
        nom_fichier = os.path.basename(filepath)
        try:
            spec = importlib.util.spec_from_file_location("module", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            vars_module = {k: v for k, v in vars(module).items() if k.startswith("ue_data_")}
            if vars_module:
                datasets[nom_fichier] = vars_module
        except Exception as e:
            print(f"Erreur chargement {filepath}: {e}")
            
    return datasets

def reset_app():
    st.session_state.ue_data = {}
    save_user_data(st.session_state.username, st.session_state.password, {})
    st.toast("Application réinitialisée et sauvegardée !", icon="🗑️")

def calcul_metriques(data):
    """Calcule les stats et la moyenne pessimiste."""
    resultats_detail = []
    total_points_actuel = 0.0
    total_coef_actuel = 0.0
    total_points_pessimiste = 0.0
    total_coef_pessimiste = 0.0
    ue_validees = 0
    ue_total = 0

    if not data:
        return [], 0.0, 0.0, 0, 0, 0.0

    for nom, details in data.items():
        coef = details.get("coef", 1.0)
        grades = details.get("grades", [])
        sc = details.get("sc", None)

        num_actuel = sum(g["note"] * g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
        den_actuel = sum(g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
        
        moyenne_ue_actuelle = num_actuel / den_actuel if den_actuel > 0 else 0.0

        num_pessimiste = 0.0
        den_pessimiste = sum(g["poids"] for g in grades if g.get("poids") is not None)
        
        for g in grades:
            note = g.get("note")
            poids = g.get("poids")
            if poids is not None and poids > 0:
                if note is not None:
                    num_pessimiste += note * poids
                # Si note None -> 0
        
        moyenne_ue_pessimiste = num_pessimiste / den_pessimiste if den_pessimiste > 0 else 0.0
        
        # SC logic
        moyenne_ue_actuelle_sc = moyenne_ue_actuelle
        moyenne_ue_pessimiste_sc = moyenne_ue_pessimiste
        
        if sc is not None and isinstance(sc, (int, float)):
            moyenne_ue_actuelle_sc = max(moyenne_ue_actuelle, (moyenne_ue_actuelle + sc) / 2)
            moyenne_ue_pessimiste_sc = max(moyenne_ue_pessimiste, (moyenne_ue_pessimiste + sc) / 2)

        est_validee_secure = moyenne_ue_pessimiste_sc >= 10
        if est_validee_secure:
            ue_validees += 1

        if den_actuel > 0:
            total_points_actuel += moyenne_ue_actuelle_sc * coef
            total_coef_actuel += coef
            if est_validee_secure: icon_statut = "🔒 Validé"
            elif moyenne_ue_actuelle_sc >= 10: icon_statut = "⏳ En cours"
            else: icon_statut = "⚠️ Danger"

            ue_total += 1
            resultats_detail.append({
                "UE": nom,
                "Coef": coef,
                "Moyenne": round(moyenne_ue_actuelle_sc, 2),
                "Statut": icon_statut
            })
        elif den_pessimiste > 0:
            ue_total += 1

        if den_pessimiste > 0:
            total_points_pessimiste += moyenne_ue_pessimiste_sc * coef
            total_coef_pessimiste += coef
        
    moyenne_gen_actuelle = total_points_actuel / total_coef_actuel if total_coef_actuel > 0 else 0.0
    moyenne_gen_pessimiste = total_points_pessimiste / total_coef_pessimiste if total_coef_pessimiste > 0 else 0.0

    return resultats_detail, moyenne_gen_actuelle, moyenne_gen_pessimiste, ue_validees, ue_total, total_coef_pessimiste

# ---------- SIDEBAR (MENU) ----------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # --- SECTION GIT / FICHIERS LOCAUX ---
    st.subheader("📂 Fichiers locaux")
    datasets_locaux = scanner_fichiers_locaux()
    
    if datasets_locaux:
        fichier_choisi = st.selectbox("1. Fichier :", list(datasets_locaux.keys()))
        if fichier_choisi:
            vars_dispo = datasets_locaux[fichier_choisi]
            dataset_choisi = st.selectbox("2. Dataset :", list(vars_dispo.keys()))
            
            if st.button("Charger ce dataset"):
                raw_data = vars_dispo[dataset_choisi]
                st.session_state.ue_data = normaliser_donnees(raw_data)
                # Sauvegarde automatique après chargement
                save_user_data(st.session_state.username, st.session_state.password, st.session_state.ue_data)
                st.toast(f"Dataset '{dataset_choisi}' chargé et sauvegardé !", icon="🚀")
                st.rerun()
    else:
        st.caption("Aucun fichier 'ue_data_*.py' trouvé.")

    st.divider()

    # --- SECTION JSON ---
    with st.expander("💾 Sauvegarde JSON"):
        st.download_button("Export JSON", json.dumps(st.session_state.ue_data, indent=4), "notes.json")
        f = st.file_uploader("Import JSON", type="json")
        if f: 
            loaded_data = json.load(f)
            st.session_state.ue_data = normaliser_donnees(loaded_data)
            # Sauvegarde automatique après import
            save_user_data(st.session_state.username, st.session_state.password, st.session_state.ue_data)
            st.rerun()
            
        if st.button("Tout effacer", type="primary"): 
            reset_app()
            st.rerun()

# ---------- INTERFACE PRINCIPALE ----------
st.title("Calculateur de Moyenne Étudiante 🎓")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "📝 Saisie & UEs", "🔮 Simulation", "📋 Détails Raw"])

# === TAB 1: DASHBOARD ===
with tab1:
    details, moy_actuelle, moy_pessimiste, valides, total_ues, total_coef_pessimiste = calcul_metriques(st.session_state.ue_data)    
    if not st.session_state.ue_data:
        st.info("👈 Chargez un fichier ou ajoutez des UEs manuellement.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Moyenne Actuelle", f"{moy_actuelle:.2f}/20", 
                    delta=f"{moy_actuelle-10:.2f} vs val.", 
                    delta_color="normal" if moy_actuelle >= 10 else "inverse")
        col2.metric("Moyenne Pessimiste", f"{moy_pessimiste:.2f}/20", 
                    delta=f"{moy_pessimiste-10:.2f} vs val.", 
                    delta_color="normal" if moy_pessimiste >= 10 else "inverse")
        col3.metric("UE Validées", f"{valides}/{total_ues}")
        col4.metric("Coefficients Totaux", total_coef_pessimiste)

        c1, c2 = st.columns([1, 2])
        with c1:
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
        new_ue_sc = st.number_input("Note Seconde Chance (Optionnel)", 0.0, 20.0, None, step=0.5)
        
        if st.button("Créer l'UE"):
            if new_ue_name:
                st.session_state.ue_data[new_ue_name] = {"coef": new_ue_coef, "grades": [], "sc": new_ue_sc}
                # SAUVEGARDE
                save_user_data(st.session_state.username, st.session_state.password, st.session_state.ue_data)
                st.toast(f"UE {new_ue_name} ajoutée !", icon="✅")
                st.rerun()

    with c_edit:
        st.subheader("✏️ Modifier les notes")
        if st.session_state.ue_data:
            ue_select = st.selectbox("UE à modifier", list(st.session_state.ue_data.keys()))
            curr_data = st.session_state.ue_data[ue_select]
            
            # Paramètres UE
            new_coef = st.number_input("Coefficient", 1.0, 20.0, float(curr_data.get("coef", 1.0)), key=f"coef_{ue_select}")
            new_sc = st.number_input("Seconde Chance", 0.0, 20.0, curr_data.get("sc"), key=f"sc_{ue_select}")
            
            # Editeur
            df_grades = pd.DataFrame(curr_data["grades"])
            if df_grades.empty: df_grades = pd.DataFrame(columns=["note", "poids"])

            edited_df = st.data_editor(
                df_grades, num_rows="dynamic",
                column_config={
                    "note": st.column_config.NumberColumn("Note", min_value=0.0, max_value=20.0, step=0.5),
                    "poids": st.column_config.NumberColumn("Poids (0.0 à 1.0)", min_value=0.0, max_value=1.0, step=0.1)
                }, key=f"ed_{ue_select}"
            )

            if st.button("💾 Sauvegarder dans le Cloud"):
                clean_grades = []
                for item in edited_df.to_dict('records'):
                    # Nettoyage
                    p = item.get('poids')
                    n = item.get('note')
                    if p is not None and p > 0:
                        # Si n est NaN (pandas) ou None, on garde None
                        if pd.isna(n): n = None
                        clean_grades.append({"note": n, "poids": p})
                        
                # Mise à jour Session
                st.session_state.ue_data[ue_select]["grades"] = clean_grades
                st.session_state.ue_data[ue_select]["coef"] = new_coef
                st.session_state.ue_data[ue_select]["sc"] = new_sc
                
                # SAUVEGARDE DB
                save_user_data(st.session_state.username, st.session_state.password, st.session_state.ue_data)
                st.toast("Notes sauvegardées sur Supabase !", icon="✅")
                st.rerun()

# === TAB 3: SIMULATION ===
with tab3:
    st.subheader("🔮 Simulation & Objectifs")
    if not st.session_state.ue_data:
        st.warning("Aucune donnée chargée.")
    else:
        col_graph, col_sliders = st.columns([2, 1])
        with col_sliders:
            st.caption("🎯 **Objectifs par UE :**")
            simulated_results = []
            total_points_sim = 0
            total_coef_sim = 0
            
            for nom, details in st.session_state.ue_data.items():
                coef = details.get("coef", 1.0)
                grades = details.get("grades", [])
                sc = details.get("sc", None)
                
                poids_total = sum(g["poids"] or 0 for g in grades)
                # Gestion des poids/notes None
                points_acquis = sum((g["note"] or 0) * (g["poids"] or 0) for g in grades if g.get("note") is not None)
                poids_rempli = sum((g["poids"] or 0) for g in grades if g.get("note") is not None)
                
                poids_manquant = poids_total - poids_rempli
                
                if poids_manquant <= 0.01:
                    # UE Terminée
                    denom = poids_total if poids_total > 0 else 1
                    moyenne_ue = points_acquis / denom
                    if sc and isinstance(sc, (int, float)): moyenne_ue = max(moyenne_ue, (moyenne_ue + sc)/2)
                    
                    simulated_results.append({"UE": nom, "Note Finale": moyenne_ue, "Coef": coef, "Type": "Fixé"})
                    total_points_sim += moyenne_ue * coef
                    total_coef_sim += coef
                    st.success(f"**{nom}** : {moyenne_ue:.2f}/20 (Fini)")
                else:
                    # UE en cours
                    target_10 = (10.0 * poids_total - points_acquis) / poids_manquant
                    if target_10 <= 0: msg = "✅ Validé !"
                    elif target_10 > 20: msg = "💀 Impossible"
                    else: msg = f"🎯 Viser **{target_10:.2f}**"
                    
                    st.markdown(f"**{nom}** : {msg}")
                    
                    note_reste = st.slider(f"Note espérée {nom}", 0.0, 20.0, 10.0, 0.5, label_visibility="collapsed", key=f"sim_{nom}")
                    
                    moy_sim = (points_acquis + (note_reste * poids_manquant)) / poids_total if poids_total > 0 else 0
                    if sc and isinstance(sc, (int, float)): moy_sim = max(moy_sim, (moy_sim + sc)/2)
                    
                    simulated_results.append({"UE": nom, "Note Finale": moy_sim, "Coef": coef, "Type": "Simulé"})
                    total_points_sim += moy_sim * coef
                    total_coef_sim += coef
                    st.divider()

        with col_graph:
            moy_gen_sim = total_points_sim / total_coef_sim if total_coef_sim > 0 else 0.0
            st.metric("Moyenne Générale Projetée", f"{moy_gen_sim:.2f}/20")
            
            if simulated_results:
                df_sim = pd.DataFrame(simulated_results)
                df_sim['Color'] = df_sim.apply(lambda x: '#2ecc71' if x['Note Finale'] >= 10 else ('#f1c40f' if x['Type'] == 'Simulé' else '#e74c3c'), axis=1)
                
                fig = px.bar(df_sim, x="UE", y="Note Finale", text="Note Finale", range_y=[0, 20])
                fig.update_traces(marker_color=df_sim['Color'], texttemplate='%{y:.2f}')
                fig.add_hline(y=10, line_dash="dash", line_color="black")
                st.plotly_chart(fig, use_container_width=True)

# === TAB 4: RAW ===
with tab4:
    st.subheader("Données JSON Brutes")
    st.json(st.session_state.ue_data)