import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from supabase import create_client, Client

# ---------- CONFIGURATION PAGE ----------
st.set_page_config(page_title="Calculateur de Moyenne 🎓", layout="wide")

# ---------- CONNEXION SUPABASE (HTTP API) ----------
# Cette méthode marche à 100% sur Streamlit Cloud
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

def get_user_from_db(username, password):
    """Récupère l'utilisateur via l'API Supabase"""
    try:
        # On demande l'utilisateur qui a ce nom ET ce mot de passe
        response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        
        # Si la liste 'data' n'est pas vide, on a trouvé quelqu'un
        if response.data and len(response.data) > 0:
            user_row = response.data[0]
            user_data_raw = user_row.get("ue_data", {})
            return user_data_raw if isinstance(user_data_raw, dict) else json.loads(user_data_raw)
        return None
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return None

def save_user_data(username, password, data):
    """Sauvegarde via l'API (Upsert)"""
    try:
        # On prépare la donnée
        user_entry = {
            "username": username,
            "password": password,
            "ue_data": data # Supabase gère le JSON tout seul
        }
        # Upsert = Met à jour si existe, Crée sinon
        supabase.table("users").upsert(user_entry).execute()
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
    
    with st.form("login"):
        user = st.text_input("Identifiant (ex: matteo)")
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
        st.session_state.password = ""
        st.session_state.ue_data = {}
        st.rerun()
    st.divider()

# ... LA SUITE DU CODE NE CHANGE PAS (A PARTIR DU CSS) ...
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
    Une UE est comptée "Validée" SEULEMENT si la moyenne PESSIMISTE >= 10.
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

        # --- Détermination du statut de validation (Strict) ---
        est_validee_secure = moyenne_ue_pessimiste_sc >= 10
        if est_validee_secure:
            ue_validees += 1

        # --- Mise à Jour des Totaux Globaux ---

        # 1. Total Actuel (pour l'affichage de la moyenne Actuelle et le tableau de détails)
        if den_actuel > 0:
            total_points_actuel += moyenne_ue_actuelle_sc * coef
            total_coef_actuel += coef

            # Icône visuelle pour le tableau
            if est_validee_secure:
                icon_statut = "🔒 Validé"
            elif moyenne_ue_actuelle_sc >= 10:
                icon_statut = "⏳ En cours"
            else:
                icon_statut = "⚠️ Danger"

            ue_total += 1 # Compte les UEs avec au moins une note

            resultats_detail.append({
                "UE": nom,
                "Coef": coef,
                "Moyenne": round(moyenne_ue_actuelle_sc, 2), # Affiche la moyenne actuelle dans le tableau
                "Statut": icon_statut
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
st.title("Calculateur de Moyenne Étudiante 🎓")

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
        col3.metric("UE Validées", f"{valides}/{total_ues}", help="Une UE est validée si sa moyenne PESSIMISTE est ≥ 10")
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
            curr_data["coef"] = st.number_input(
                "Coefficient de l'UE", 
                min_value=1.0, 
                max_value=20.0, 
                value=float(curr_data.get("coef", 1.0)), 
                key=f"coef_{ue_select}"
            )
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

# === TAB 3: SIMULATION BASÉE SUR LA PERFORMANCE ===
with tab3:
    st.subheader("🔮 Simulation & Objectifs")
    st.markdown("""
    Ici, ne touchez pas à la moyenne finale directement. 
    **Estimez plutôt la note que vous pensez obtenir** sur les examens restants.
    """)

    if not st.session_state.ue_data:
        st.warning("Veuillez d'abord charger des données ou créer des UEs.")
    else:
        # --- 1. Préparation des données ---
        col_graph, col_sliders = st.columns([2, 1])
        
        with col_sliders:
            st.caption("🎯 **Vos objectifs par UE :**")
            
            simulated_results = []
            total_points_sim = 0
            total_coef_sim = 0
            
            for nom, details in st.session_state.ue_data.items():
                coef = details.get("coef", 1.0)
                grades = details.get("grades", [])
                sc = details.get("sc", None)
                
                # Calcul des poids
                poids_total = sum(g["poids"] for g in grades if g.get("poids") is not None)
                poids_rempli = sum(g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
                poids_manquant = poids_total - poids_rempli
                
                # Points déjà acquis
                points_acquis = sum(g["note"] * g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
                
                # --- CAS 1 : UE Terminée (Tout est noté) ---
                if poids_manquant <= 0.01:
                    # Calcul de la moyenne finale
                    moyenne_ue = points_acquis / poids_total if poids_total > 0 else 0
                    if sc: moyenne_ue = max(moyenne_ue, (moyenne_ue + sc)/2)
                    
                    # Affichage fixe (pas de slider)
                    st.success(f"🔒 **{nom}** : {moyenne_ue:.2f}/20 (Terminé)")
                    simulated_results.append({"UE": nom, "Note Finale": moyenne_ue, "Coef": coef, "Type": "Fixé"})
                    total_points_sim += moyenne_ue * coef
                    total_coef_sim += coef
                
                # --- CAS 2 : UE en cours (Calcul d'objectif) ---
                else:
                    # Calcul de la note nécessaire pour avoir 10/20 de moyenne UE
                    target_10 = (10.0 * poids_total - points_acquis) / poids_manquant
                    
                    # Affichage de l'aide à la décision
                    msg_target = ""
                    if target_10 <= 0:
                        msg_target = "✅ Validé (même avec 0)"
                        st.markdown(f"**{nom}** ({coef}) : {msg_target}")
                    elif target_10 > 20:
                        msg_target = f"💀 Impossible (Max: {(points_acquis + 20*poids_manquant)/poids_total:.2f})"
                        st.markdown(f"**{nom}** ({coef}) : {msg_target}")
                    else:
                        msg_target = f"🎯 Il faut **{target_10:.2f}** sur le reste"
                        st.markdown(f"**{nom}** ({coef}) : {msg_target}")

                    # Slider : "Quelle note pensez-vous avoir sur le reste ?"
                    note_sur_reste = st.slider(
                        f"Moyenne espérée sur les exams manquants ({nom})",
                        min_value=0.0, max_value=20.0, value=10.0, step=0.5,
                        key=f"sim_input_{nom}",
                        label_visibility="collapsed"
                    )
                    
                    # Calcul de la moyenne finale SIMULÉE
                    moyenne_simulee = (points_acquis + (note_sur_reste * poids_manquant)) / poids_total
                    if sc: moyenne_simulee = max(moyenne_simulee, (moyenne_simulee + sc)/2)
                    
                    simulated_results.append({"UE": nom, "Note Finale": moyenne_simulee, "Coef": coef, "Type": "Simulé"})
                    total_points_sim += moyenne_simulee * coef
                    total_coef_sim += coef
                    
                    st.divider()

        # --- 3. Graphique & Moyenne Globale ---
        moyenne_generale_sim = total_points_sim / total_coef_sim if total_coef_sim > 0 else 0.0
        
        with col_graph:
            # Grosse métrique centrale
            st.metric(
                "Moyenne Générale Projetée", 
                f"{moyenne_generale_sim:.2f}/20",
                delta="Si vous obtenez les notes choisies à droite"
            )
            
            if simulated_results:
                df_sim = pd.DataFrame(simulated_results)
                # Couleur : Vert si > 10, Orange si Simulé < 10, Rouge si Fixé < 10
                colors = []
                for _, row in df_sim.iterrows():
                    if row["Note Finale"] >= 10: colors.append("#2ecc71") # Vert
                    elif row["Type"] == "Simulé": colors.append("#f1c40f") # Jaune/Orange
                    else: colors.append("#e74c3c") # Rouge
                
                df_sim['Color'] = colors
                
                fig = px.bar(
                    df_sim, 
                    x="UE", 
                    y="Note Finale", 
                    text="Note Finale",
                    range_y=[0, 20],
                    title="Simulation des Moyennes Finales"
                )
                fig.update_traces(marker_color=df_sim['Color'], texttemplate='%{y:.2f}', textposition='outside')
                fig.add_hline(y=10, line_dash="dash", line_color="black", annotation_text="Validation")
                
                st.plotly_chart(fig, use_container_width=True)
# === TAB 4: RAW ===
with tab4:
    st.subheader("Détails des UEs (Moyenne Actuelle)")
    if details: st.dataframe(pd.DataFrame(details), use_container_width=True)
    st.subheader("Données JSON Brutes de Session")
    st.json(st.session_state.ue_data)